"""PA workflow orchestration over shared Core sensing/profile components."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import time
from datetime import datetime, timezone
from functools import wraps
from threading import RLock

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
from core.profiles.baselines import BaselineStore, build_baseline_profile
from core.runtime.deviation import FrameBuilder
from core.runtime.quality import quality_is_usable, quality_state

from .policy import PersistentAnomalyPolicy, recommendation_for


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
            result = method(self, *args, **kwargs)
            if self._persistence_callback is not None:
                self._persistence_callback(self.export_state())
            return result
    return wrapper


class SessionCommandError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 409, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.retryable = retryable


class PASession:
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
    ) -> None:
        validate_record(reference_profile, PUBLIC, "ReferenceProfile")
        self.session_id = session_id
        self.instrument_config = copy.deepcopy(instrument_config)
        self.reference = copy.deepcopy(reference_profile)
        self.source = copy.deepcopy(source)
        self.capture_fingerprint = copy.deepcopy(capture_fingerprint)
        self.analyzer = analyzer
        self.baseline_store = baseline_store or BaselineStore()
        self.monotonic_clock = monotonic_clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.settling_policy_s = settling_policy_s
        self.persistence_frames = persistence_frames
        self.event_retention = event_retention
        self._lock = RLock()
        self._persistence_callback = None
        model = analyzer.capabilities()["model"]
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
            "unsupported_families": [],
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
        self._frames: list[dict] = []
        self._frame_audio_hashes: dict[str, str] = {}
        self._frame_sequence = 0
        self._incident_counter = 0
        self._adjustment_counter = 0
        self._verification_counter = 0
        self._incident_before_balance: float | None = None
        self._verification_armed = False
        self._require_fresh_after_resume = False
        self._detector = PersistentAnomalyPolicy(required_frames=persistence_frames)
        self._frame_builder = FrameBuilder()
        validate_snapshot(self.snapshot())

    def _target(self) -> dict:
        target = {"target_kind": "reference", "reference": reference_binding(self.reference), "baseline": None}
        if self.session_mode == "live":
            target = {
                "target_kind": "baseline",
                "reference": reference_binding(self.reference),
                "baseline": baseline_binding(self.baseline),
            }
        return target

    def _context(self, window, *, purpose: str, probe_instrument_id: str | None) -> dict:
        context_asset = (
            self.baseline["model_specific_context_asset"]
            if self.session_mode == "live"
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
                self.baseline["comparison_regime"] if self.session_mode == "live" else self.reference["comparison_regime"]
            ),
            "model_specific_context_asset": context_asset,
            "observation_purpose": purpose,
            "probe_instrument_id": probe_instrument_id,
        }

    @_synchronized
    def snapshot(self) -> dict:
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
        validate_snapshot(result)
        return result

    def set_persistence_callback(self, callback) -> None:
        with self._lock:
            self._persistence_callback = callback

    @_synchronized
    def export_state(self) -> dict:
        return {
            "state_format": "pa-session-state-v1",
            "session_id": self.session_id,
            "instrument_config": copy.deepcopy(self.instrument_config),
            "reference": copy.deepcopy(self.reference),
            "source": copy.deepcopy(self.source),
            "capture_fingerprint": copy.deepcopy(self.capture_fingerprint),
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
            "frames": copy.deepcopy(self._frames),
            "frame_audio_hashes": dict(self._frame_audio_hashes),
            "frame_sequence": self._frame_sequence,
            "incident_counter": self._incident_counter,
            "adjustment_counter": self._adjustment_counter,
            "verification_counter": self._verification_counter,
            "incident_before_balance": self._incident_before_balance,
            "verification_armed": self._verification_armed,
            "require_fresh_after_resume": self._require_fresh_after_resume,
            "settling_policy_s": self.settling_policy_s,
            "persistence_frames": self.persistence_frames,
            "event_retention": self.event_retention,
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
    ):
        if state.get("state_format") != "pa-session-state-v1":
            raise ValueError("unsupported persisted session state")
        song = state["song"]
        session = cls(
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
        )
        with session._lock:
            session.execution = copy.deepcopy(state["execution"])
            session.song = copy.deepcopy(song)
            session.state_version = state["state_version"]
            session.event_sequence = state["event_sequence"]
            session.session_mode = state["session_mode"]
            session.incident_state = state["incident_state"]
            session.baseline = copy.deepcopy(state["baseline"])
            if session.baseline is not None:
                session.baseline_store.save(session.baseline)
            session.incident = copy.deepcopy(state["incident"])
            session.adjustment = copy.deepcopy(state["adjustment"])
            session.latest_frame = copy.deepcopy(state["latest_frame"])
            session.recommendations = copy.deepcopy(state["recommendations"])
            session.latest_verification = copy.deepcopy(state["latest_verification"])
            session.suspension_reasons = list(state["suspension_reasons"])
            session._events = copy.deepcopy(state["events"])
            session._audit_records = copy.deepcopy(state.get("audit_records", []))
            session._frames = copy.deepcopy(state["frames"])
            session._frame_audio_hashes = dict(state["frame_audio_hashes"])
            session._frame_sequence = state["frame_sequence"]
            session._incident_counter = state["incident_counter"]
            session._adjustment_counter = state["adjustment_counter"]
            session._verification_counter = state["verification_counter"]
            session._incident_before_balance = state["incident_before_balance"]
            session._verification_armed = state["verification_armed"]
            session._require_fresh_after_resume = state["require_fresh_after_resume"]
            session._detector.reset()
            validate_snapshot(session.snapshot())
        return session

    @_synchronized
    def audit_records(self) -> list[dict]:
        return copy.deepcopy(self._audit_records)

    def _audit(self, kind: str, payload: dict) -> None:
        self._audit_records.append(
            {
                "kind": kind,
                "state_version": self.state_version,
                "event_sequence": self.event_sequence,
                "payload": copy.deepcopy(payload),
            }
        )

    @_persisted
    def suspend_for_runtime_restart(self) -> None:
        if self.song["workflow_state"] == "STOPPED":
            return
        self.song["workflow_state"] = "SUSPENDED"
        self.suspension_reasons = ["runtime_restart_requires_new_session"]
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
        if purpose is None:
            purpose = "verification" if self._verification_armed else ("live" if self.session_mode == "live" else "rehearsal")
        context = self._context(window, purpose=purpose, probe_instrument_id=probe_instrument_id)
        evidence = self.analyzer.analyze(window, context)
        self._frame_sequence += 1
        frame = self._frame_builder.build(
            context=context,
            evidence=evidence,
            quality=quality or quality_state(),
            frame_id=f"frame:{self.session_id}:{self._frame_sequence}",
            sequence=self._frame_sequence,
            published_monotonic_s=self.monotonic_clock(),
        )
        self.latest_frame = copy.deepcopy(frame)
        self._frames.append(copy.deepcopy(frame))
        self._frame_audio_hashes[frame["frame_id"]] = self._audio_hash(window)
        self._append_event(frame)

        if self._verification_armed and self.adjustment is not None:
            if self.incident is None:
                self._consider_proactive_recheck(frame, window.start_monotonic_s)
            else:
                self._consider_verification(frame, window.start_monotonic_s)
            return copy.deepcopy(frame)
        if self.song["workflow_state"] == "SUSPENDED":
            # Paused sessions may continue publishing diagnostics, but cannot advance
            # persistence, open incidents, or emit corrective recommendations.
            return copy.deepcopy(frame)
        if self._require_fresh_after_resume:
            self._require_fresh_after_resume = False
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
            "baseline_id": self.baseline["baseline_id"] if self.session_mode == "live" else None,
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

    def _consider_verification(self, frame: dict, window_start_monotonic_s: float) -> None:
        cutoff = self.adjustment["verification_not_before_monotonic_s"]
        if cutoff is None or window_start_monotonic_s < cutoff:
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
            "baseline_id": self.baseline["baseline_id"] if self.session_mode == "live" else None,
            "baseline_version": self.baseline["version"] if self.session_mode == "live" else None,
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
        self._transition()
        self._append_event(verification)

    def _consider_proactive_recheck(self, frame: dict, window_start_monotonic_s: float) -> None:
        cutoff = self.adjustment["verification_not_before_monotonic_s"]
        if cutoff is None or window_start_monotonic_s < cutoff:
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
        if self.song["workflow_state"] == "STOPPED":
            raise SessionCommandError("session_stopped", "STOPPED is terminal for this session.")
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
            if self.session_mode != "rehearsal" or self.adjustment is not None:
                raise SessionCommandError("invalid_state", "A free recheck is rehearsal-only.")
            self._detector.reset()
            self.song["workflow_state"] = "REHEARSAL"
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
            if right["sample_start"] != left["sample_end"]:
                raise SessionCommandError("invalid_baseline_interval", "Selected interval crosses a gap.", http_status=422)
        next_version = 1 if self.baseline is None else self.baseline["version"] + 1
        baseline_id = self.baseline["baseline_id"] if self.baseline else f"baseline:{self.session_id}"
        try:
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
            )
            self.baseline_store.save(profile)
        except ValueError as exc:
            raise SessionCommandError("baseline_quality_rejected", str(exc), http_status=422) from exc
        self.baseline = self.baseline_store.get(baseline_id, next_version)
        self._audit("baseline_accepted", self.baseline)
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
        if self.song["workflow_state"] == "STOPPED":
            raise SessionCommandError("invalid_state", "Stopped session cannot pause.")
        self.song["workflow_state"] = "SUSPENDED"
        self.suspension_reasons = ["operator_paused"]
        self.recommendations = []
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
        self.song["workflow_state"] = "LIVE_MONITORING" if self.session_mode == "live" else "REHEARSAL"
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
    def events_after(self, after_sequence: int) -> list[dict]:
        if after_sequence < 0:
            raise ValueError("event cursor cannot be negative")
        if self._events and after_sequence < self._events[0]["event_sequence"] - 1:
            # Retention gap: publish one authoritative snapshot event instead of
            # silently returning a discontinuous suffix.
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
            self._events = self._events[-self.event_retention :]
            return [copy.deepcopy(event)]
        return [copy.deepcopy(item) for item in self._events if item["event_sequence"] > after_sequence]


def canonical_command(command: dict) -> str:
    return json.dumps(command, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
