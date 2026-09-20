"""PA workflow orchestration over shared Core sensing/profile components."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from threading import Event, RLock

from core.contracts.validation import (
    PUBLIC,
    baseline_binding,
    event_binding,
    reference_binding,
    validate_command_binding,
    validate_event,
    validate_record,
    validate_snapshot,
)
from core.contracts.guided import GUIDED, validate_probe_request
from core.profiles.baselines import BaselineStore, build_baseline_profile
from core.runtime.deviation import FrameBuilder
from core.runtime.quality import pcm_clipped_fraction, quality_is_usable, quality_state
from core.runtime.timing import analysis_timing_profile

from .policy import PersistentAnomalyPolicy, recommendation_for
from .experimental_hints import adjustment_hints


def _synchronized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


def _persisted(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            if self._deletion_requested.is_set():
                raise SessionCommandError("unknown_session", "Session was deleted.", http_status=404)
            pre_state = self.export_state()
            try:
                result = method(self, *args, **kwargs)
                if self._deletion_requested.is_set():
                    raise SessionCommandError("unknown_session", "Session was deleted.", http_status=404)
                if self._persistence_callback is not None:
                    self._persistence_callback(self.export_state())
                return result
            except Exception:
                self.restore_state(pre_state)
                raise
    return wrapper


class SessionCommandError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 409, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.retryable = retryable


from .live_reference import LiveReferencePolicy


class PASession(LiveReferencePolicy):
    def __init__(
        self,
        *,
        session_id: str,
        project_id: str,
        song_id: str,
        song_name: str,
        instrument_config: dict,
        reference_profile: dict,
        source: dict,
        capture_fingerprint: dict,
        analyzer,
        baseline_store: BaselineStore | None = None,
        monotonic_clock=time.monotonic,
        wall_clock=None,
        settling_policy_s: float = 0.5,
        persistence_frames: int = 2,
        event_retention: int = 128,
        capture_runtime_verified: bool = True,
        frame_retention: int = 128,
        capture_profile_enforced: bool = True,
        analysis_sample_rate_hz: int | None = None,
        workflow_policy: str = "legacy_baseline_v1",
        analysis_timing_profile_id: str = "strict_v1",
    ) -> None:
        validate_record(reference_profile, PUBLIC, "ReferenceProfile")
        self.workflow_policy = workflow_policy
        self._analysis_timing = analysis_timing_profile(analysis_timing_profile_id)
        self.session_id = session_id
        self.instrument_config = copy.deepcopy(instrument_config)
        self.reference = copy.deepcopy(reference_profile)
        self.source = copy.deepcopy(source)
        self.capture_fingerprint = copy.deepcopy(capture_fingerprint)
        self.capture_runtime_verified = capture_runtime_verified
        self.capture_profile_enforced = capture_profile_enforced
        self.analysis_sample_rate_hz = analysis_sample_rate_hz or capture_fingerprint["native_sample_rate_hz"]
        self.analyzer = analyzer
        self.baseline_store = baseline_store or BaselineStore()
        self.monotonic_clock = monotonic_clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.settling_policy_s = settling_policy_s
        self.persistence_frames = persistence_frames
        self.event_retention = event_retention
        if frame_retention < 1:
            raise ValueError("frame_retention must be positive")
        self.frame_retention = frame_retention
        self._lock = RLock()
        self._deletion_requested = Event()
        self._persistence_callback = None
        model = analyzer.capabilities()["model"]
        self._model_identity = copy.deepcopy(model)
        self._baseline_model_identity = None
        self.execution = {
            "model_bundle_id": model["model_bundle_id"],
            "frontend_id": model["frontend_id"],
            "execution_profile_id": model["execution_profile_id"],
            "provider": analyzer.capabilities()["provider"],
        }
        self.song = {
            "record_type": "SongState",
            "schema_version": "1.0",
            "song_id": song_id,
            "project_id": project_id,
            "name": song_name,
            "instrument_config_version": instrument_config["instrument_config_version"],
            "configured_families": [item["family"] for item in instrument_config["instruments"]],
            "unsupported_families": ([] if "attempted_families" in analyzer.capabilities() else
                [item["family"] for item in instrument_config["instruments"]
                 if item["family"] not in analyzer.capabilities().get("supported_families", ())]),
            "reference_id": reference_profile["reference_id"],
            "baseline_id": None,
            "workflow_state": "REHEARSAL",
        }
        self.state_version = 0
        self.event_sequence = 0
        self.session_mode = "rehearsal"
        self.incident_state = "none"
        self.baseline = None
        self.incident = None
        self.adjustment = None
        self.latest_frame = None
        self.recommendations: list[dict] = []
        self.latest_verification = None
        self.suspension_reasons: list[str] = []
        self._events: list[dict] = []
        self._audit_records: list[dict] = []
        self._audit_total = 0
        self._frames: list[dict] = []
        self._frame_audio_hashes: dict[str, str] = {}
        # Non-persisted, bounded rehearsal PCM for explicit baseline preparation.
        self._baseline_windows = {}
        self._baseline_pcm_samples = 0
        self._baseline_pcm_limit = 1_000_000
        self._probe = {"mode":"idle", "instrument_id":None, "probe_id":None, "not_before_monotonic_s":None}
        self._guided_frame_ids = set()
        self._frame_sequence = 0
        self._incident_counter = 0
        self._adjustment_counter = 0
        self._verification_counter = 0
        self._incident_before_balance: float | None = None
        self._verification_armed = False
        self._require_fresh_after_resume = False
        self._detector = PersistentAnomalyPolicy(required_frames=persistence_frames)
        self._frame_builder = FrameBuilder(calibration_policy=getattr(analyzer, "calibration_policy", None))
        self._init_capture()
        if self.live_reference:
            self.session_mode = "live"
            self.song["workflow_state"] = "LIVE_MONITORING"
        validate_snapshot(self.snapshot())

    def _target(self) -> dict:
        target = {"target_kind": "reference", "reference": reference_binding(self.reference), "baseline": None}
        if self.session_mode == "live" and not self.live_reference:
            target = {
                "target_kind": "baseline",
                "reference": reference_binding(self.reference),
                "baseline": baseline_binding(self.baseline),
            }
        return target

    def _context(self, window, *, purpose: str, probe_instrument_id: str | None) -> dict:
        context_asset = (
            self.baseline["model_specific_context_asset"]
            if self.session_mode == "live" and not self.live_reference
            else self.reference["model_specific_context_asset"]
        )
        return {
            "record_type": "AnalyzerContext",
            "schema_version": "1.0",
            "observation": window.identity(),
            "model": copy.deepcopy(self.analyzer.capabilities()["model"]),
            "instrument_config": copy.deepcopy(self.instrument_config),
            "target": self._target(),
            "comparison_regime": (
                self.baseline["comparison_regime"] if self.session_mode == "live" and not self.live_reference else self.reference["comparison_regime"]
            ),
            "model_specific_context_asset": context_asset,
            "observation_purpose": purpose,
            "probe_instrument_id": probe_instrument_id,
        }

    @_synchronized
    def snapshot(self) -> dict:
        snapshot_now = self.monotonic_clock()
        expired = bool(self.live_reference and self.latest_frame and self.capture["frame_fresh"] and
            snapshot_now > self.latest_frame["capture_end_monotonic_s"] + self._analysis_timing["result_max_age_s"])
        result = {
            "record_type": "SessionSnapshot",
            "schema_version": "1.0",
            "session_id": self.session_id,
            "state_version": self.state_version,
            "event_sequence": self.event_sequence,
            "session_mode": self.session_mode,
            "incident_state": self.incident_state,
            "song": copy.deepcopy(self.song),
            "source": copy.deepcopy(self.source),
            "execution": copy.deepcopy(self.execution),
            "active_reference": copy.deepcopy(self.reference),
            "active_baseline": copy.deepcopy(self.baseline),
            "incident": copy.deepcopy(self.incident),
            "adjustment": copy.deepcopy(self.adjustment),
            "latest_frame": copy.deepcopy(self.latest_frame),
            "recommendations": copy.deepcopy(self.recommendations),
            "latest_verification": copy.deepcopy(self.latest_verification),
            "suspension_reasons": list(self.suspension_reasons),
        }
        if self.live_reference:
            timing=copy.deepcopy(self._analysis_timing);timing["snapshot_monotonic_s"]=snapshot_now
            capture=copy.deepcopy(self.capture)
            if expired:
                capture.update(frame_fresh=False,state="listening",reason_codes=["stale_evidence"])
                result["recommendations"]=[];result["latest_verification"]=None
            result.update(workflow_policy=self.workflow_policy,capture=capture,
                perception=self._perception(snapshot_now,expired),analysis_timing=timing)
        validate_snapshot(result)
        return result

    def set_persistence_callback(self, callback) -> None:
        with self._lock:
            self._persistence_callback = callback

    def expire_live_evidence(self, now: float) -> bool:
        """Retire over-age evidence during the controller's durable monitor tick."""
        frame=self.latest_frame
        if (not self.live_reference or not frame or not self.capture["frame_fresh"] or
                now <= frame["capture_end_monotonic_s"] + self._analysis_timing["result_max_age_s"]):
            return False
        self.latest_frame=None;self._current_masks={};self._current_hints={};self._hint_expires_monotonic_s=None
        self.capture.update(frame_fresh=False,state="listening",reason_codes=["stale_evidence"])
        self.recommendations=[];self.latest_verification=None;self._detector.reset();self._verification_armed=False
        return True

    def reset_analysis_persistence(self) -> None:
        """Prevent persistence from bridging intentionally omitted inference work."""
        self._detector.reset()

    def suppress_for_capture_gap(self) -> bool:
        """Withhold current evidence immediately while preserving human workflow state."""
        changed=bool(self.latest_frame or self._current_masks or self._current_hints or self.recommendations
            or self.capture["frame_fresh"] or "capture_dropout" not in self.capture["reason_codes"])
        self.latest_frame=None;self._current_masks={};self._current_hints={};self._hint_expires_monotonic_s=None
        self.recommendations=[];self.capture.update(frame_fresh=False,state="listening",reason_codes=["capture_dropout"])
        self._detector.reset()
        return changed

    @contextmanager
    def command_transaction(self):
        """Hold the session lock across mutation, durable commit, or rollback."""
        with self._lock:
            yield

    @_synchronized
    def export_state(self) -> dict:
        return {
            "state_format": "pa-session-state-v1",
            "workflow_policy": self.workflow_policy,
            "capture": copy.deepcopy(self.capture),
            "current_masks": copy.deepcopy(self._current_masks),
            "current_hints": copy.deepcopy(self._current_hints),
            "hint_expires_monotonic_s": self._hint_expires_monotonic_s,
            "analysis_timing": copy.deepcopy(self._analysis_timing),
            "switch_previous": copy.deepcopy(self._switch_previous),
            "switch_paused": self._switch_paused,
            "session_id": self.session_id,
            "instrument_config": copy.deepcopy(self.instrument_config),
            "reference": copy.deepcopy(self.reference),
            "source": copy.deepcopy(self.source),
            "capture_fingerprint": copy.deepcopy(self.capture_fingerprint),
            "capture_runtime_verified": self.capture_runtime_verified,
            "capture_profile_enforced": self.capture_profile_enforced,
            "analysis_sample_rate_hz": self.analysis_sample_rate_hz,
            "baseline_records": self.baseline_store.records(),
            "analyzer_capabilities": self.analyzer.capabilities(),
            "model_identity": copy.deepcopy(self._model_identity),
            "baseline_model_identity": copy.deepcopy(self._baseline_model_identity),
            "execution": copy.deepcopy(self.execution),
            "song": copy.deepcopy(self.song),
            "state_version": self.state_version,
            "event_sequence": self.event_sequence,
            "session_mode": self.session_mode,
            "incident_state": self.incident_state,
            "baseline": copy.deepcopy(self.baseline),
            "incident": copy.deepcopy(self.incident),
            "adjustment": copy.deepcopy(self.adjustment),
            "latest_frame": copy.deepcopy(self.latest_frame),
            "recommendations": copy.deepcopy(self.recommendations),
            "latest_verification": copy.deepcopy(self.latest_verification),
            "suspension_reasons": list(self.suspension_reasons),
            "events": copy.deepcopy(self._events),
            "audit_records": copy.deepcopy(self._audit_records),
            "audit_total": self._audit_total,
            "frames": copy.deepcopy(self._frames),
            "frame_audio_hashes": dict(self._frame_audio_hashes),
            "probe": copy.deepcopy(self._probe),
            "guided_frame_ids": sorted(self._guided_frame_ids),
            "frame_sequence": self._frame_sequence,
            "incident_counter": self._incident_counter,
            "adjustment_counter": self._adjustment_counter,
            "verification_counter": self._verification_counter,
            "incident_before_balance": self._incident_before_balance,
            "verification_armed": self._verification_armed,
            "require_fresh_after_resume": self._require_fresh_after_resume,
            "detector_state": self._detector.export_state(),
            "settling_policy_s": self.settling_policy_s,
            "persistence_frames": self.persistence_frames,
            "event_retention": self.event_retention,
            "frame_retention": self.frame_retention,
        }

    @classmethod
    def from_state(
        cls,
        state: dict,
        *,
        analyzer,
        baseline_store: BaselineStore,
        monotonic_clock=time.monotonic,
        wall_clock=None,
        analysis_timing_profile_id: str | None = None,
    ):
        if state.get("state_format") != "pa-session-state-v1":
            raise ValueError("unsupported persisted session state")
        if analysis_timing_profile_id is not None:
            state=copy.deepcopy(state)
            state["analysis_timing"]=analysis_timing_profile(analysis_timing_profile_id)
        song = state["song"]
        session = cls(
            workflow_policy=state.get("workflow_policy","legacy_baseline_v1"),
            session_id=state["session_id"],
            project_id=song["project_id"],
            song_id=song["song_id"],
            song_name=song["name"],
            instrument_config=state["instrument_config"],
            reference_profile=state["reference"],
            source=state["source"],
            capture_fingerprint=state["capture_fingerprint"],
            analyzer=analyzer,
            baseline_store=baseline_store,
            monotonic_clock=monotonic_clock,
            wall_clock=wall_clock,
            settling_policy_s=state["settling_policy_s"],
            persistence_frames=state["persistence_frames"],
            event_retention=state["event_retention"],
            capture_runtime_verified=state.get("capture_runtime_verified", False),
            analysis_timing_profile_id=(analysis_timing_profile_id or
                state.get("analysis_timing", {}).get("profile_id", "strict_v1")),
        )
        session.restore_state(state)
        return session

    @_synchronized
    def restore_state(self, state: dict) -> None:
        """Replace mutable state exactly, including immutable-baseline history.

        Command handling uses this only to restore a pre-command snapshot when its
        durable transaction fails. It deliberately does not invoke persistence.
        """
        if state.get("state_format") != "pa-session-state-v1":
            raise ValueError("unsupported persisted session state")
        if state.get("session_id") != self.session_id:
            raise ValueError("persisted state belongs to a different session")
        self.workflow_policy=state.get("workflow_policy","legacy_baseline_v1")
        self.capture=copy.deepcopy(state.get("capture",self.capture))
        self._current_masks=copy.deepcopy(state.get("current_masks",{}))
        self._current_hints=copy.deepcopy(state.get("current_hints",{}))
        self._hint_expires_monotonic_s=state.get("hint_expires_monotonic_s")
        self._analysis_timing=analysis_timing_profile(
            state.get("analysis_timing", self._analysis_timing).get("profile_id", "strict_v1"))
        self._switch_previous=copy.deepcopy(state.get("switch_previous"))
        self._switch_paused=state.get("switch_paused",False)
        self.instrument_config = copy.deepcopy(state["instrument_config"])
        self.reference = copy.deepcopy(state["reference"])
        self.source = copy.deepcopy(state["source"])
        self.capture_fingerprint = copy.deepcopy(state["capture_fingerprint"])
        self.capture_runtime_verified = state.get("capture_runtime_verified", False)
        self.execution = copy.deepcopy(state["execution"])
        self._model_identity = copy.deepcopy(state.get("model_identity", self._model_identity))
        self._baseline_model_identity = copy.deepcopy(state.get("baseline_model_identity"))
        self.analysis_sample_rate_hz = state.get("analysis_sample_rate_hz", state["capture_fingerprint"]["native_sample_rate_hz"])
        self.song = copy.deepcopy(state["song"])
        self.state_version = state["state_version"]
        self.event_sequence = state["event_sequence"]
        self.session_mode = state["session_mode"]
        self.incident_state = state["incident_state"]
        self.baseline = copy.deepcopy(state["baseline"])
        baseline_records = state.get("baseline_records")
        if baseline_records is None:
            baseline_records = [] if self.baseline is None else [self.baseline]
        self.baseline_store.replace_records(copy.deepcopy(baseline_records))
        self.incident = copy.deepcopy(state["incident"])
        self.adjustment = copy.deepcopy(state["adjustment"])
        self.latest_frame = copy.deepcopy(state["latest_frame"])
        self.recommendations = copy.deepcopy(state["recommendations"])
        self.latest_verification = copy.deepcopy(state["latest_verification"])
        self.suspension_reasons = list(state["suspension_reasons"])
        self._events = copy.deepcopy(state["events"])
        self._audit_records = copy.deepcopy(state.get("audit_records", []))
        for index, record in enumerate(self._audit_records, 1):
            record.setdefault("audit_index", index)
        self._audit_total = state.get("audit_total", len(self._audit_records))
        self._frames = copy.deepcopy(state["frames"])
        self._frame_audio_hashes = dict(state["frame_audio_hashes"])
        self._probe = copy.deepcopy(state.get("probe", {"mode":"idle", "instrument_id":None, "probe_id":None, "not_before_monotonic_s":None}))
        self._guided_frame_ids = set(state.get("guided_frame_ids", []))
        self._frame_sequence = state["frame_sequence"]
        self._incident_counter = state["incident_counter"]
        self._adjustment_counter = state["adjustment_counter"]
        self._verification_counter = state["verification_counter"]
        self._incident_before_balance = state["incident_before_balance"]
        self._verification_armed = state["verification_armed"]
        self._require_fresh_after_resume = state["require_fresh_after_resume"]
        self.settling_policy_s = state["settling_policy_s"]
        self.persistence_frames = state["persistence_frames"]
        self.event_retention = state["event_retention"]
        self.frame_retention = state.get("frame_retention", 128)
        self.capture_profile_enforced = state.get("capture_profile_enforced", True)
        self._detector = PersistentAnomalyPolicy(required_frames=self.persistence_frames)
        self._detector.restore_state(state.get("detector_state", {}))
        validate_snapshot(self.snapshot())

    @_synchronized
    def audit_records(self) -> list[dict]:
        return copy.deepcopy(self._audit_records)

    def _audit(self, kind: str, payload: dict, *, evidence_frames=None) -> None:
        if evidence_frames is None:
            bound = payload.get("event") or payload
            ids = bound.get("evidence_frame_ids", [])
            evidence_frames = [frame for frame in self._frames if frame["frame_id"] in ids]
        self._audit_total += 1
        self._audit_records.append(dict(
            audit_index=self._audit_total, kind=kind, state_version=self.state_version,
            event_sequence=self.event_sequence, payload=copy.deepcopy(payload),
            evidence_frames=copy.deepcopy(evidence_frames),
            audio_hashes={frame["frame_id"]: self._frame_audio_hashes[frame["frame_id"]]
                          for frame in evidence_frames if frame["frame_id"] in self._frame_audio_hashes}))
        # Durable APIs archive these immutable records in the same SQLite transaction.
        # Standalone sessions retain their whole audit until a durable sink is attached.
        if self._persistence_callback is not None:
            self._audit_records = self._audit_records[-128:]

    @_persisted
    def suspend_for_input(self, reason: str) -> None:
        if self.song["workflow_state"] == "STOPPED":
            return
        if self.live_reference:
            self._clear_source_evidence(reason)
            self.capture.update(state="unavailable",frame_fresh=False,reason_codes=[reason])
        self.song["workflow_state"] = "SUSPENDED"
        self.suspension_reasons = [reason]
        self.recommendations = []
        self._verification_armed = False
        self._detector.reset()
        self._transition()

    @_persisted
    def suspend_for_runtime_restart(self) -> None:
        if self.song["workflow_state"] == "STOPPED":
            return
        reason="runtime_restart_requires_reopen" if self.live_reference else "runtime_restart_requires_new_session"
        if self.live_reference:
            self.capture["source_generation"]+=1
            self._clear_source_evidence(reason)
            self.capture.update(state="unavailable",frame_fresh=False,switch_result="failed" if self.capture["switch_result"]=="pending" else self.capture["switch_result"],reason_codes=[reason])
        self.song["workflow_state"] = "SUSPENDED"
        self.suspension_reasons = [reason]
        self.recommendations = []
        self._verification_armed = False
        self._detector.reset()
        self._transition()

    def _append_event(self, payload: dict) -> dict:
        self.event_sequence += 1
        event = {
            "record_type": "SessionEvent",
            "schema_version": "1.0",
            "session_id": self.session_id,
            "event_sequence": self.event_sequence,
            "state_version": self.state_version,
            "payload": copy.deepcopy(payload),
        }
        validate_event(event)
        self._events.append(event)
        if len(self._events) > self.event_retention:
            self._events = self._events[-self.event_retention :]
        return copy.deepcopy(event)

    def _transition(self) -> dict:
        if self.session_mode != "rehearsal" or self.song["workflow_state"] != "REHEARSAL" or self.adjustment is not None:
            self._cancel_probe()
        self.state_version += 1
        # A snapshot event must carry its own newly allocated cursor.
        self.event_sequence += 1
        payload = self.snapshot()
        event = {
            "record_type": "SessionEvent",
            "schema_version": "1.0",
            "session_id": self.session_id,
            "event_sequence": self.event_sequence,
            "state_version": self.state_version,
            "payload": payload,
        }
        validate_event(event)
        self._events.append(event)
        if len(self._events) > self.event_retention:
            self._events = self._events[-self.event_retention :]
        return payload

    def _cancel_probe(self):
        if self._probe["mode"] != "idle":
            self._probe = {"mode":"idle", "instrument_id":None, "probe_id":None, "not_before_monotonic_s":None}
            self._detector.reset()

    @_synchronized
    def probe_state(self):
        state = {"record_type":"RehearsalProbeState", "schema_version":"1.0", "session_id":self.session_id,
                 "state_version":self.state_version, **copy.deepcopy(self._probe)}
        validate_record(state, GUIDED, "RehearsalProbeState")
        return state

    @_synchronized
    def apply_probe(self, command):
        if self.live_reference:
            raise SessionCommandError("legacy_action_unavailable","Guided rehearsal is unavailable in Live reference.")
        try:
            validate_probe_request(command, self.snapshot())
        except ValueError as exc:
            if self.song["workflow_state"] == "SUSPENDED":
                raise SessionCommandError("probe_input_unavailable", "Resume a healthy rehearsal input first.", http_status=503) from exc
            raise SessionCommandError("probe_state_conflict", str(exc)) from exc
        instrument = command["instrument_id"]
        if instrument is not None and instrument not in {item["instrument_id"] for item in self.instrument_config["instruments"]}:
            raise SessionCommandError("invalid_probe_instrument", "Instrument is not configured.", http_status=422)
        self._probe = {"mode":command["mode"], "instrument_id":instrument,
                       "probe_id":f"probe:{uuid.uuid4().hex}" if command["mode"] != "idle" else None,
                       "not_before_monotonic_s":self.monotonic_clock() if command["mode"] != "idle" else None}
        self._detector.reset()
        self._transition()
        return self.snapshot()

    @staticmethod
    def _audio_hash(window) -> str:
        digest = hashlib.sha256()
        for value in window.samples:
            digest.update(struct.pack("<f", value))
        return f"sha256:{digest.hexdigest()}"

    @_persisted
    def observe_window(
        self,
        window,
        *,
        purpose: str | None = None,
        probe_instrument_id: str | None = None,
        quality: dict | None = None,
        max_age_s: float | None = None,
        clock_uncertainty_s: float = 0.0,
        _prepared_evidence=None,
        _inference_started=None,
    ) -> dict:
        if self.song["workflow_state"] == "STOPPED":
            raise SessionCommandError("session_stopped", "Stopped sessions cannot accept audio.")
        if "runtime_restart_requires_new_session" in self.suspension_reasons:
            raise SessionCommandError(
                "new_session_required",
                "Application restart changed the clock; start a new session before supplying audio.",
            )
        if window.session_id != self.session_id:
            raise ValueError("window belongs to another session")
        if window.clock_id != self.source["clock_id"]:
            raise ValueError("window clock differs from the session clock")
        if (window.input_kind != self.source["input_kind"] or
                window.input_asset_or_device_id != self.source["input_asset_or_device_id"]):
            raise ValueError("window source differs from the session source")
        model = self.analyzer.capabilities()["model"]
        if model != self._model_identity or any(model[key] != self.execution[key] for key in ("model_bundle_id", "frontend_id", "execution_profile_id")):
            raise ValueError("runtime model/profile changed; create a revalidated session")
        if self.capture_profile_enforced and window.sample_rate_hz != self.analysis_sample_rate_hz:
            raise ValueError("capture sample rate changed; revalidate the input profile")
        if quality and quality["dropout"] and self._probe["mode"] != "idle":
            self._cancel_probe()
            self._transition()
        if self._probe["mode"] != "idle":
            if window.start_monotonic_s - clock_uncertainty_s < self._probe["not_before_monotonic_s"]:
                return None
            purpose = "guided_probe" if self._probe["mode"] == "instrument" else "rehearsal"
            probe_instrument_id = self._probe["instrument_id"]
        if purpose is None:
            purpose = "verification" if self._verification_armed else ("live" if self.session_mode == "live" else "rehearsal")
        context = self._context(window, purpose=purpose, probe_instrument_id=probe_instrument_id)
        begin = self.monotonic_clock() if _inference_started is None else _inference_started
        evidence = self.analyzer.analyze(window, context) if _prepared_evidence is None else _prepared_evidence
        quality = copy.deepcopy(quality or quality_state())
        # Recheck freshness after inference: a fast capture callback does not make
        # a slow model result current at publication.
        if max_age_s is not None and self.monotonic_clock() - window.capture_end_monotonic_s > max_age_s:
            quality["stale"] = True
            if "stale_evidence" not in quality["reason_codes"]:
                quality["reason_codes"].append("stale_evidence")
        clipped = max(window.input_clipped_fraction, pcm_clipped_fraction(window.samples))
        quality["clipped_fraction"] = max(quality["clipped_fraction"], clipped)
        if not any(window.samples):
            quality["comparability"] = "weak"
        self._frame_sequence += 1
        frame = self._frame_builder.build(
            context=context,
            evidence=evidence,
            quality=quality,
            frame_id=f"frame:{self.session_id}:{self._frame_sequence}",
            sequence=self._frame_sequence,
            published_monotonic_s=self.monotonic_clock(),
            inference_wall_ms=max(0, (self.monotonic_clock() - begin) * 1000),
        )
        if self.live_reference:
            self._current_masks={row["instrument_id"]:copy.deepcopy(row) for row in evidence["measurements"]}
            self._current_hints=adjustment_hints(context=context,evidence=evidence,frame=frame,
                anomaly_threshold_db=self._frame_builder.anomaly_threshold_db)
            result_age=self._analysis_timing["result_max_age_s"] if max_age_s is None else max_age_s
            self._hint_expires_monotonic_s=min(
                frame["published_monotonic_s"]+self._analysis_timing["hint_hold_s"],
                window.capture_end_monotonic_s+result_age)
            for hint in self._current_hints.values():
                hint["expires_monotonic_s"]=self._hint_expires_monotonic_s
            fresh=not frame["quality"]["stale"] and not frame["quality"]["dropout"]
            self.capture.update(analysis_run_id=window.analysis_run_id,state="active" if fresh else "listening",
                frame_fresh=fresh)
            if fresh:
                self.capture["reason_codes"]=[reason for reason in self.capture["reason_codes"]
                    if reason!="capture_dropout"]
        self.latest_frame = copy.deepcopy(frame)
        self._frames.append(copy.deepcopy(frame))
        if purpose == "guided_probe":
            self._guided_frame_ids.add(frame["frame_id"])
        if not evidence["example_only"] and self.session_mode == "rehearsal":
            self._baseline_windows[frame["frame_id"]] = window
            self._baseline_pcm_samples += len(window.samples)
            while self._baseline_pcm_samples > self._baseline_pcm_limit:
                oldest = next(iter(self._baseline_windows))
                self._baseline_pcm_samples -= len(self._baseline_windows.pop(oldest).samples)
        self._frame_audio_hashes[frame["frame_id"]] = self._audio_hash(window)
        while len(self._frames) > self.frame_retention:
            retired = self._frames.pop(0)
            self._guided_frame_ids.discard(retired["frame_id"])
            self._frame_audio_hashes.pop(retired["frame_id"], None)
        self._append_event(frame)

        if self.song["workflow_state"] == "SUSPENDED":
            # Paused sessions may continue publishing diagnostics, but cannot advance
            # persistence, open incidents, or emit corrective recommendations.
            return copy.deepcopy(frame)
        if self._require_fresh_after_resume:
            if quality_is_usable(frame["quality"]):
                self._require_fresh_after_resume = False
            return copy.deepcopy(frame)
        if self._verification_armed and self.adjustment is not None:
            if self.incident is None:
                self._consider_proactive_recheck(frame, window.start_monotonic_s, clock_uncertainty_s=clock_uncertainty_s)
            else:
                self._consider_verification(frame, window.start_monotonic_s, clock_uncertainty_s=clock_uncertainty_s)
            return copy.deepcopy(frame)
        if (
            self.incident is not None
            and self.incident["event"]["state"] in ("resolved", "dismissed")
            and quality_is_usable(frame["quality"])
        ):
            # Current pointers are retired only on fresh usable monitoring audio.
            # Their immutable event/snapshot history remains in the audit stream.
            self.incident = None
            self.adjustment = None
            self.incident_state = "none"
            self.recommendations = []
            self._incident_before_balance = None
            self._detector.reset()
            self._transition()
        if self.incident is None:
            candidate = self._detector.observe(frame)
            if candidate is not None:
                state, evidence_ids = candidate
                self._open_incident(state, evidence_ids, frame)
        return copy.deepcopy(frame)

    def _open_incident(self, state: dict, evidence_ids: list[str], frame: dict) -> None:
        self._incident_counter += 1
        event = {
            "record_type": "AnomalyEvent",
            "schema_version": "1.0",
            "event_id": f"event:{self.session_id}:{self._incident_counter}",
            "session_id": self.session_id,
            "instrument_ids": [state["instrument_id"]],
            "direction": state["status"],
            "onset_monotonic_s": frame["capture_end_monotonic_s"],
            "confirmed_monotonic_s": frame["capture_end_monotonic_s"],
            "baseline_id": self.baseline["baseline_id"] if self.baseline is not None and self.session_mode == "live" else None,
            "reference_id": self.reference["reference_id"],
            "evidence_frame_ids": evidence_ids,
            "state": "active",
            "confidence": copy.deepcopy(state["confidence"]),
        }
        validate_record(event, PUBLIC, "AnomalyEvent")
        self.incident = {"event": event, "event_version": 1, "target": self._target()}
        self._incident_before_balance = state["balance_deviation_db"]
        self.incident_state = "active"
        self.song["workflow_state"] = "LIVE_ANOMALY" if self.session_mode == "live" else "ANOMALY_DETECTED"
        recommendation = recommendation_for(
            event=event, state=state, now_monotonic_s=self.monotonic_clock()
        )
        validate_record(recommendation, PUBLIC, "Recommendation")
        self.recommendations = [recommendation]
        self._audit("incident_opened", self.incident)
        self._transition()
        self._append_event(event)
        self._append_event(recommendation)

    def _consider_verification(self, frame: dict, window_start_monotonic_s: float, *, clock_uncertainty_s: float = 0.0) -> None:
        cutoff = self.adjustment["verification_not_before_monotonic_s"]
        if cutoff is None or window_start_monotonic_s - clock_uncertainty_s < cutoff:
            return
        instrument_id = self.incident["event"]["instrument_ids"][0]
        state = next(item for item in frame["instruments"] if item["instrument_id"] == instrument_id)
        observable = (
            quality_is_usable(frame["quality"])
            and state["activity"] == "active"
            and not state["confidence"]["abstained"]
        )
        reasons = [] if observable else list(state["confidence"]["reasons"] or frame["quality"]["reason_codes"])
        if not reasons and not observable:
            reasons = ["source_not_observable"]
        after = state["balance_deviation_db"] if observable else None
        if not observable:
            outcome = "inconclusive"
        elif state["status"] == "normal":
            outcome = "recovered"
        elif self._incident_before_balance is not None and abs(after) < abs(self._incident_before_balance):
            outcome = "partial"
        else:
            outcome = "not_recovered"
        self._verification_counter += 1
        verification = {
            "record_type": "VerificationResult",
            "schema_version": "1.0",
            "verification_id": f"verification:{self.session_id}:{self._verification_counter}",
            "event_id": self.incident["event"]["event_id"],
            "adjustment_id": self.adjustment["adjustment_id"],
            "baseline_id": self.baseline["baseline_id"] if self.baseline is not None and self.session_mode == "live" else None,
            "baseline_version": self.baseline["version"] if self.baseline is not None and self.session_mode == "live" else None,
            "adjustment_completed_monotonic_s": self.adjustment["completed_monotonic_s"],
            "first_evidence_sample_start_monotonic_s": window_start_monotonic_s,
            "evidence_frame_ids": [frame["frame_id"]],
            "instrument_id": instrument_id,
            "before_balance_db": self._incident_before_balance,
            "after_balance_db": after,
            "source_observable": observable,
            "outcome": outcome,
            "reason_codes": reasons,
        }
        validate_record(verification, PUBLIC, "VerificationResult")
        self.latest_verification = verification
        self._verification_armed = False
        self.incident["event_version"] += 1
        if outcome == "recovered":
            self.incident["event"]["state"] = "resolved"
            self.incident_state = "resolved"
            self.recommendations = []
            self.song["workflow_state"] = "LIVE_MONITORING" if self.session_mode == "live" else "REHEARSAL"
        elif outcome == "inconclusive":
            self.incident["event"]["state"] = "inconclusive"
            self.incident_state = "inconclusive"
        else:
            self.incident["event"]["state"] = "active"
            self.incident_state = "active"
            self.song["workflow_state"] = "LIVE_ANOMALY" if self.session_mode == "live" else "ANOMALY_DETECTED"
        self._audit("verification", verification)
        self._audit("incident_revised", self.incident)
        if outcome in ("recovered", "partial", "not_recovered"):
            # The completed attempt remains immutable in audit/verification history,
            # while a remaining active incident may enter another correction loop.
            self.adjustment = None
        self._transition()
        self._append_event(verification)

    def _consider_proactive_recheck(self, frame: dict, window_start_monotonic_s: float, *, clock_uncertainty_s: float = 0.0) -> None:
        cutoff = self.adjustment["verification_not_before_monotonic_s"]
        if cutoff is None or window_start_monotonic_s - clock_uncertainty_s < cutoff:
            return
        # A proactive rehearsal adjustment has no anomaly event and therefore must
        # not invent a VerificationResult. It still waits for a fully post-cutoff,
        # usable observation before returning to rehearsal.
        if not quality_is_usable(frame["quality"]):
            return
        self._verification_armed = False
        self.adjustment = None
        self.incident_state = "none"
        self.song["workflow_state"] = "REHEARSAL"
        self._transition()

    @_synchronized
    def apply_command(self, command: dict) -> dict:
        try:
            validate_command_binding(command, self.snapshot())
        except ValueError as exc:
            raise SessionCommandError("stale_or_invalid_binding", str(exc), retryable=True) from exc
        action = command["action"]
        if self.live_reference and action == "switch_microphone":
            self._accept_source_switch(command)
            return self.snapshot()
        self._authorize_action(action)
        if self.live_reference:
            self._live_lifecycle_command(action)
        if action == "accept_baseline":
            self._accept_baseline(command["payload"])
        elif action == "start_adjustment":
            self._start_adjustment()
        elif action == "complete_adjustment":
            self._complete_adjustment(command["payload"]["adjustment_id"])
        elif action == "recheck":
            self._recheck(command["payload"]["adjustment_id"])
        elif action == "start_live":
            self._start_live()
        elif action == "dismiss":
            self._dismiss()
        elif action == "pause":
            self._pause()
        elif action == "resume":
            self._resume()
        elif action == "stop":
            self._stop()
        else:
            raise SessionCommandError("unsupported_action", f"Unsupported action: {action}", http_status=422)
        return self.snapshot()

    def _authorize_action(self, action: str) -> None:
        workflow = self.song["workflow_state"]
        if workflow == "STOPPED":
            raise SessionCommandError("session_stopped", "STOPPED is terminal for this session.")
        if workflow == "SUSPENDED":
            if action in ("resume", "stop") or (self.live_reference and action=="pause"):
                return
            raise SessionCommandError(
                "session_suspended",
                "Suspended sessions accept only resume or stop.",
            )
        if action in ("accept_baseline", "start_live"):
            if self.adjustment is not None:
                raise SessionCommandError(
                    "unresolved_adjustment",
                    "Complete and verify or cancel the current human adjustment first.",
                )
            if self.incident is not None and self.incident["event"]["state"] not in (
                "resolved",
                "dismissed",
            ):
                raise SessionCommandError(
                    "unresolved_incident",
                    "Resolve or dismiss the current incident first.",
                )

    def _start_adjustment(self) -> None:
        if self.song["workflow_state"] == "STOPPED" or self.adjustment is not None:
            raise SessionCommandError("invalid_state", "An adjustment cannot start in the current state.")
        self._adjustment_counter += 1
        self.adjustment = {
            "adjustment_id": f"adjustment:{self.session_id}:{self._adjustment_counter}",
            "event": event_binding(self.incident),
            "target": self._target(),
            "clock_id": self.source["clock_id"],
            "started_monotonic_s": self.monotonic_clock(),
            "completed_monotonic_s": None,
            "verification_not_before_monotonic_s": None,
        }
        if self.incident is not None:
            self.incident["event"]["state"] = "acknowledged"
            self.incident["event_version"] += 1
            self._audit("incident_revised", self.incident)
        self.incident_state = "adjusting"
        self.song["workflow_state"] = "PA_ADJUSTING"
        self._audit("adjustment_started", self.adjustment)
        self._transition()

    def _complete_adjustment(self, adjustment_id: str) -> None:
        if self.adjustment is None or self.adjustment["adjustment_id"] != adjustment_id:
            raise SessionCommandError("invalid_adjustment", "Adjustment identity is not current.")
        if self.adjustment["completed_monotonic_s"] is not None:
            raise SessionCommandError("invalid_state", "Adjustment is already complete.")
        completed = self.monotonic_clock()
        self.adjustment["completed_monotonic_s"] = completed
        self.adjustment["verification_not_before_monotonic_s"] = completed + self.settling_policy_s
        self.incident_state = "verifying"
        self.song["workflow_state"] = "VERIFY_RECOVERY" if self.session_mode == "live" else "RECHECK"
        self._audit("adjustment_completed", self.adjustment)
        self._transition()

    def _recheck(self, adjustment_id: str | None) -> None:
        if adjustment_id is None:
            if (self.session_mode != "rehearsal" and not self.live_reference) or self.adjustment is not None:
                raise SessionCommandError("invalid_state", "A free recheck is rehearsal-only.")
            self._detector.reset()
            self.song["workflow_state"] = "LIVE_MONITORING" if self.live_reference else "REHEARSAL"
            self._transition()
            return
        if self.adjustment is None or self.adjustment["adjustment_id"] != adjustment_id:
            raise SessionCommandError("invalid_adjustment", "Adjustment identity is not current.")
        if self.adjustment["completed_monotonic_s"] is None:
            raise SessionCommandError("invalid_state", "Complete the adjustment first.")
        self._verification_armed = True
        self.incident_state = "verifying"
        self.song["workflow_state"] = "VERIFY_RECOVERY" if self.session_mode == "live" else "RECHECK"
        self._transition()

    def _accept_baseline(self, payload: dict) -> None:
        if self.analyzer.capabilities()["model"] != self._model_identity:
            raise SessionCommandError("incompatible_profile", "Model identity changed; reanalyze in a new session.")
        if self.session_mode != "rehearsal":
            raise SessionCommandError("baseline_immutable_live", "Baseline acceptance is forbidden during Live.")
        if self.incident is not None and self.incident["event"]["state"] not in ("resolved", "dismissed"):
            raise SessionCommandError("unresolved_incident", "Resolve or dismiss the current incident first.")
        interval = payload["interval"]
        selected = [
            frame
            for frame in self._frames
            if frame["analysis_run_id"] == interval["analysis_run_id"]
            and frame["clock_id"] == interval["clock_id"]
            and frame["sample_rate_hz"] == interval["sample_rate_hz"]
            and frame["sample_start"] >= interval["sample_start"]
            and frame["sample_end"] <= interval["sample_end"]
        ]
        selected.sort(key=lambda item: item["sample_start"])
        if not selected or selected[0]["sample_start"] != interval["sample_start"] or selected[-1]["sample_end"] != interval["sample_end"]:
            raise SessionCommandError("invalid_baseline_interval", "Selected interval lacks complete fresh frame coverage.", http_status=422)
        for left, right in zip(selected, selected[1:]):
            if right["sample_start"] > left["sample_end"]:
                raise SessionCommandError("invalid_baseline_interval", "Selected interval crosses a gap.", http_status=422)
        if any(frame["frame_id"] in self._guided_frame_ids for frame in selected):
            raise SessionCommandError("baseline_requires_full_band", "Choose a full-band rehearsal interval.", http_status=422)
        next_version = 1 if self.baseline is None else self.baseline["version"] + 1
        baseline_id = self.baseline["baseline_id"] if self.baseline else f"baseline:{self.session_id}"
        try:
            preparation = {}
            if not self.analyzer.capabilities().get("example_only", False):
                policy = getattr(self.analyzer, "calibration_policy", None)
                if policy is None:
                    raise ValueError("approved baseline calibration unavailable")
                if any(frame["frame_id"] not in self._baseline_windows for frame in selected):
                    raise ValueError("baseline PCM expired; capture a new rehearsal interval")
                prepared = self.analyzer.prepare_reference(
                    (self._baseline_windows[frame["frame_id"]] for frame in selected), self.instrument_config)
                preparation = {"prepared_context_asset": prepared["model_specific_context_asset"],
                               "normal_envelopes": policy.normal_envelopes(self.instrument_config)}
            profile = build_baseline_profile(
                baseline_id=baseline_id,
                version=next_version,
                song=self.song,
                instrument_config=self.instrument_config,
                reference=self.reference,
                accepted_by=payload["accepted_by"],
                accepted_at=self.wall_clock(),
                execution=self.execution,
                taxonomy_id=self.analyzer.capabilities()["model"]["taxonomy_id"],
                capture=self.capture_fingerprint,
                source_audio_hashes=[self._frame_audio_hashes[item["frame_id"]] for item in selected],
                frames=selected,
                reference_difference_accepted=payload["reference_difference_accepted"],
                acceptance_note=payload["acceptance_note"],
                **preparation,
            )
            self.baseline_store.save(profile)
        except ValueError as exc:
            raise SessionCommandError("baseline_quality_rejected", str(exc), http_status=422) from exc
        self.baseline = self.baseline_store.get(baseline_id, next_version)
        self._baseline_model_identity = copy.deepcopy(self._model_identity)
        self._audit("baseline_accepted", self.baseline, evidence_frames=selected)
        self.song["baseline_id"] = baseline_id
        self.song["workflow_state"] = "REHEARSAL"
        self.incident = None
        self.adjustment = None
        self.incident_state = "none"
        self.recommendations = []
        self.latest_verification = None
        self.latest_frame = None
        self._detector.reset()
        self._transition()

    def _start_live(self) -> None:
        if self.session_mode != "rehearsal" or self.baseline is None:
            raise SessionCommandError("invalid_state", "Live requires an accepted rehearsal baseline.")
        if not self.capture_runtime_verified:
            raise SessionCommandError(
                "capture_not_runtime_verified",
                "Live requires a runtime-verified capture device/profile.",
            )
        if self._baseline_model_identity != self._model_identity or self.analyzer.capabilities()["model"] != self._model_identity:
            raise SessionCommandError("incompatible_profile", "Baseline requires the exact accepted five-ID model identity.")
        expected = self.execution
        for key in ("model_bundle_id", "frontend_id", "execution_profile_id"):
            if self.baseline[key] != expected[key]:
                raise SessionCommandError("incompatible_profile", f"Baseline {key} is incompatible.")
        if self.baseline["taxonomy_id"] != self.analyzer.capabilities()["model"]["taxonomy_id"]:
            raise SessionCommandError("incompatible_profile", "Baseline taxonomy is incompatible.")
        self.session_mode = "live"
        self.song["workflow_state"] = "LIVE_MONITORING"
        self.incident = None
        self.adjustment = None
        self.incident_state = "none"
        self.recommendations = []
        self.latest_verification = None
        self.latest_frame = None
        self._detector.reset()
        self._transition()

    def _dismiss(self) -> None:
        if self.incident is None:
            raise SessionCommandError("invalid_state", "There is no incident to dismiss.")
        self.incident["event"]["state"] = "dismissed"
        self.incident["event_version"] += 1
        self.incident_state = "dismissed"
        self.recommendations = []
        self._audit("incident_revised", self.incident)
        self._transition()

    def _pause(self) -> None:
        self.song["workflow_state"] = "SUSPENDED"
        self.suspension_reasons = ["operator_paused"]
        self.recommendations = []
        self._verification_armed = False
        self._detector.reset()
        self._transition()

    def _resume(self) -> None:
        if self.song["workflow_state"] != "SUSPENDED":
            raise SessionCommandError("invalid_state", "Session is not suspended.")
        if "runtime_restart_requires_new_session" in self.suspension_reasons:
            raise SessionCommandError(
                "new_session_required",
                "Application restart changed the clock; start a new session instead.",
            )
        if self.adjustment is not None:
            if self.adjustment["completed_monotonic_s"] is None:
                self.song["workflow_state"] = "PA_ADJUSTING"
            else:
                self.song["workflow_state"] = (
                    "VERIFY_RECOVERY" if self.session_mode == "live" else "RECHECK"
                )
        elif self.incident is not None and self.incident["event"]["state"] not in (
            "resolved",
            "dismissed",
        ):
            self.song["workflow_state"] = (
                "LIVE_ANOMALY" if self.session_mode == "live" else "ANOMALY_DETECTED"
            )
        else:
            self.song["workflow_state"] = (
                "LIVE_MONITORING" if self.session_mode == "live" else "REHEARSAL"
            )
        self.suspension_reasons = []
        self._require_fresh_after_resume = True
        self._transition()

    def _stop(self) -> None:
        self.song["workflow_state"] = "STOPPED"
        self.suspension_reasons = []
        self.recommendations = []
        self._detector.reset()
        self._transition()

    @_persisted
    def _resync_event(self) -> list[dict]:
        self.event_sequence += 1
        payload = self.snapshot()
        event = {
            "record_type": "SessionEvent", "schema_version": "1.0",
            "session_id": self.session_id, "event_sequence": self.event_sequence,
            "state_version": self.state_version, "payload": payload,
        }
        validate_event(event)
        self._events.append(event)
        self._events = self._events[-self.event_retention:]
        return [copy.deepcopy(event)]

    @_synchronized
    def events_after(self, after_sequence: int) -> list[dict]:
        if after_sequence < 0:
            raise ValueError("event cursor cannot be negative")
        if self._events and after_sequence < self._events[0]["event_sequence"] - 1:
            return self._resync_event()
        # Ordinary subscriptions are read-only. Only a retention-gap resync mutates
        # the cursor and requires a durable transaction.
        return [copy.deepcopy(item) for item in self._events if item["event_sequence"] > after_sequence]



def canonical_command(command: dict) -> str:
    return json.dumps(command, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
