"""Runtime application service behind the loopback HTTP/WebSocket transport."""

from __future__ import annotations

import copy
import hashlib
import io
import wave
from pathlib import Path
from threading import RLock

from jsonschema import ValidationError

from core.audio import FileAudioInput, SharedAudioPipeline
from core.contracts.validation import SETUP, validate_record
from core.profiles import BaselineStore, ReferenceBuilder
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer
from core.audio.native import NativeMicAudioInput, SoundDeviceBackend
from core.runtime.worker import AudioWorker
from core.runtime.real_analyzer import RealAnalyzerAdapter
from roles.pa import PASession

from .commands import CommandHandler
from .persistence import SQLiteCommandLedger, SQLiteRuntimeStore


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def _decode_pcm16_wav(content: bytes) -> tuple[int, tuple[float, ...], int]:
    try:
        with wave.open(io.BytesIO(content), "rb") as reader:
            channels = reader.getnchannels()
            sample_rate = reader.getframerate()
            sample_width = reader.getsampwidth()
            frames = reader.getnframes()
            raw = reader.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise APIError(422, "invalid_audio", "Only valid PCM WAV uploads are accepted.") from exc
    if len(raw) != frames * channels * sample_width:
        raise APIError(422, "truncated_audio", "WAV data does not contain the declared complete frames.")
    if sample_width != 2 or channels < 1:
        raise APIError(422, "unsupported_audio_format", "Checkpoint supports 16-bit PCM WAV input.")
    values = [int.from_bytes(raw[index : index + 2], "little", signed=True) / 32768.0 for index in range(0, len(raw), 2)]
    mono = tuple(
        sum(values[index : index + channels]) / channels
        for index in range(0, len(values), channels)
    )
    if not mono:
        raise APIError(422, "empty_audio", "Uploaded WAV contains no samples.")
    return sample_rate, mono, channels


class RuntimeAPI:
    """Runtime-owned L2 application API, callable directly by a transport adapter."""

    def __init__(
        self,
        *,
        storage_dir: str | Path,
        window_size_samples: int,
        hop_size_samples: int | None = None,
        analyzer_factory=ContinuousFakeInstrumentAnalyzer,
        monotonic_clock=None,
        wall_clock=None,
        available_audio_devices: set[str] | None = None,
        managed_audio: bool | None = None,
        native_backend=None,
        max_upload_bytes: int = 128 * 1024 * 1024,
        max_audio_duration_s: float = 900.0,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = SharedAudioPipeline(
            window_size_samples=window_size_samples, hop_size_samples=hop_size_samples
        )
        def guarded_factory():
            analyzer = analyzer_factory()
            return analyzer if analyzer.capabilities()["example_only"] else RealAnalyzerAdapter(analyzer)
        self.analyzer_factory = guarded_factory
        self.monotonic_clock = monotonic_clock
        self.wall_clock = wall_clock
        self.available_audio_devices = set(available_audio_devices or ())
        # An explicit in-process device set retains CP1's injected Fake test seam.
        # The production launcher never supplies this set.
        self.managed_audio = available_audio_devices is None if managed_audio is None else managed_audio
        self.native_backend = native_backend
        self.native_error = None
        self.workers = {}
        self._lifecycle_lock = RLock()
        self.max_upload_bytes = max_upload_bytes
        self.max_audio_duration_s = max_audio_duration_s
        self._lock = RLock()
        self.projects: dict[str, dict] = {}
        self.songs: dict[str, dict] = {}
        self.assets: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.references: dict[str, dict] = {}
        self.sessions: dict[str, PASession] = {}
        self.handlers: dict[str, CommandHandler] = {}
        self._counters = {
            name: 0 for name in ("project", "song", "asset", "job", "reference", "session", "clock")
        }
        self._store = SQLiteRuntimeStore(self.storage_dir / "runtime.sqlite3")
        self._load_state()

    def _runtime_state_payload(self) -> dict:
        return {
            "state_format": "pa-runtime-api-state-v1",
            "counters": self._counters,
            "projects": self.projects,
            "songs": self.songs,
            "assets": self.assets,
            "jobs": self.jobs,
            "references": self.references,
        }

    def _save_state(self) -> None:
        with self._lock:
            self._store.save_runtime_state(self._runtime_state_payload())

    def _save_session_state(self, session_id: str, state: dict) -> None:
        if state["session_id"] != session_id:
            raise ValueError("session persistence identity mismatch")
        self._store.save_session(state)

    def _load_state(self) -> None:
        state = self._store.load_runtime_state()
        if state is not None:
            if state.get("state_format") != "pa-runtime-api-state-v1":
                raise ValueError("unsupported RuntimeAPI persisted state")
            self._counters = state["counters"]
            self._counters.setdefault("clock", 0)
            self.projects = state["projects"]
            self.songs = state["songs"]
            self.assets = state["assets"]
            self.jobs = state["jobs"]
            self.references = state["references"]
        for session_state in self._store.load_sessions():
            session_id = session_state["session_id"]
            baseline_store = BaselineStore()
            kwargs = {}
            if self.monotonic_clock is not None:
                kwargs["monotonic_clock"] = self.monotonic_clock
            if self.wall_clock is not None:
                kwargs["wall_clock"] = self.wall_clock
            session = PASession.from_state(
                session_state,
                analyzer=self.analyzer_factory(),
                baseline_store=baseline_store,
                **kwargs,
            )
            session.set_persistence_callback(
                lambda value, identifier=session_id: self._save_session_state(identifier, value)
            )
            self.sessions[session_id] = session
            ledger = SQLiteCommandLedger(self._store, session_id)
            self.handlers[session_id] = CommandHandler(session=session, ledger=ledger)
            session.suspend_for_runtime_restart()

    def _id(self, kind: str) -> str:
        with self._lock:
            self._counters[kind] += 1
            return f"{kind}-{self._counters[kind]}"

    @staticmethod
    def _validate(name: str, value: dict) -> None:
        try:
            validate_record(value, SETUP, name)
        except (ValidationError, ValueError) as exc:
            message = exc.message if isinstance(exc, ValidationError) else str(exc)
            raise APIError(422, "invalid_setup_payload", message) from exc

    def health(self) -> tuple[int, dict]:
        analyzer = self.analyzer_factory()
        capabilities = analyzer.capabilities()
        return 200, {
            "status": "ok",
            "provider": capabilities["provider"],
            "model_bundle_id": capabilities["model"]["model_bundle_id"],
            "example_only": capabilities["example_only"],
            "session_count": len(self.sessions),
        }

    def _native(self):
        if self.native_backend is None:
            try:
                self.native_backend = SoundDeviceBackend()
            except (ImportError, OSError) as exc:
                self.native_error = str(exc)
                raise APIError(503, "native_backend_unavailable", "Native audio backend is unavailable.") from exc
        return self.native_backend

    def audio_devices(self) -> tuple[int, dict]:
        if not self.managed_audio:
            return 200, {"devices": [{"device_id": value} for value in sorted(self.available_audio_devices)],
                         "discovery_status": "injected_example_only"}
        try:
            devices = self._native().discover()
            return 200, {"devices": [{"device_id": item.device_id} for item in devices],
                         "discovery_status": "available" if devices else "no_input_devices"}
        except Exception as exc:
            self.native_error = str(exc)
            return 200, {"devices": [], "discovery_status": "native_backend_unavailable"}

    def create_project(self, request: dict) -> tuple[int, dict]:
        self._validate("CreateProjectRequest", request)
        name = request.get("name")
        if not isinstance(name, str) or not name.strip():
            raise APIError(422, "invalid_project", "Project name is required.")
        project_id = self._id("project")
        record = {"project_id": project_id, "name": name.strip()}
        self._validate("ProjectResponse", record)
        self.projects[project_id] = record
        self._save_state()
        return 201, dict(record)

    def create_song(self, request: dict) -> tuple[int, dict]:
        self._validate("CreateSongRequest", request)
        project_id, name, instruments = (
            request.get("project_id"), request.get("name"), request.get("instruments")
        )
        if project_id not in self.projects:
            raise APIError(404, "unknown_project", "Project does not exist.")
        if not isinstance(name, str) or not name.strip() or not isinstance(instruments, list) or not instruments:
            raise APIError(422, "invalid_song", "Song name and instruments are required.")
        seen = set()
        normalized = []
        for item in instruments:
            if set(item) != {"instrument_id", "family"} or not item["instrument_id"] or not item["family"]:
                raise APIError(422, "invalid_instrument", "Each instrument needs exactly instrument_id and family.")
            if item["instrument_id"] in seen:
                raise APIError(422, "duplicate_instrument", "Instrument IDs must be unique.")
            seen.add(item["instrument_id"])
            normalized.append(dict(item))
        families = [item["family"] for item in normalized]
        if len(families) != len(set(families)):
            raise APIError(422, "duplicate_family", "V1 SongState requires unique configured families.")
        song_id = self._id("song")
        supported_set = set(self.analyzer_factory().capabilities().get("supported_families", ()))
        record = {
            "song_id": song_id,
            "project_id": project_id,
            "name": name.strip(),
            "instrument_config": {"instrument_config_version": 1, "instruments": normalized},
            "supported_families": [family for family in families if family in supported_set],
            "unsupported_families": [family for family in families if family not in supported_set],
            "reference_id": None,
            "pending_reference_job_id": None,
        }
        self.songs[song_id] = record
        self._save_state()
        response = {key: value for key, value in record.items() if key != "pending_reference_job_id"}
        self._validate("SongSetupResponse", response)
        return 201, response

    def upload_audio(self, content: bytes, *, filename: str) -> tuple[int, dict]:
        if not content:
            raise APIError(422, "empty_upload", "Audio upload is empty.")
        if len(content) > self.max_upload_bytes:
            raise APIError(413, "audio_too_large", "Audio upload exceeds the configured byte limit.")
        sample_rate, samples, channels = _decode_pcm16_wav(content)
        duration_s = len(samples) / sample_rate
        if duration_s > self.max_audio_duration_s:
            raise APIError(413, "audio_too_long", "Audio upload exceeds the configured duration limit.")
        asset_id = self._id("asset")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        self.assets[asset_id] = {
            "asset_id": asset_id,
            "filename": filename,
            "content_hash": digest,
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "samples": samples,
        }
        self._save_state()
        response = {
            "asset_id": asset_id,
            "content_hash": digest,
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "duration_s": duration_s,
        }
        self._validate("AudioAssetResponse", response)
        return 201, response

    def start_reference_job(self, song_id: str, request: dict) -> tuple[int, dict]:
        self._validate("StartReferenceRequest", request)
        song = self.songs.get(song_id)
        asset = self.assets.get(request.get("asset_id"))
        if song is None:
            raise APIError(404, "unknown_song", "Song does not exist.")
        if asset is None:
            raise APIError(404, "unknown_audio_asset", "Audio asset does not exist.")
        job_id = self._id("job")
        reference_id = self._id("reference")
        job = {
            "job_id": job_id,
            "kind": "reference_analysis",
            "status": "queued",
            "song_id": song_id,
            "asset_id": asset["asset_id"],
            "reference_id": reference_id,
            "progress": 0.0,
            "error": None,
            "retryable": False,
        }
        self.jobs[job_id] = job
        song["pending_reference_job_id"] = job_id
        self._save_state()
        self._validate("ReferenceJob", job)
        return 202, dict(job)

    def run_reference_job(self, job_id: str) -> tuple[int, dict]:
        job = self.jobs.get(job_id)
        if job is None:
            raise APIError(404, "unknown_job", "Reference job does not exist.")
        if job["status"] == "completed":
            return 200, dict(job)
        song, asset = self.songs[job["song_id"]], self.assets[job["asset_id"]]
        job.update(status="running", progress=0.1, error=None, retryable=False)
        self._save_state()
        analyzer = self.analyzer_factory()
        audio_input = FileAudioInput(
            input_asset_or_device_id=asset["asset_id"],
            clock_id=f"job-clock:{job_id}",
            sample_rate_hz=asset["sample_rate_hz"],
            samples=asset["samples"],
            origin_monotonic_s=0.0,
        )
        try:
            profile = ReferenceBuilder(pipeline=self.pipeline, analyzer=analyzer).build(
                audio_input=audio_input,
                session_id=f"reference-job:{job_id}",
                analysis_run_id=f"reference-run:{job_id}",
                reference_id=job["reference_id"],
                song_id=job["song_id"],
                instrument_config=song["instrument_config"],
                source_asset_hash=asset["content_hash"],
            )
        except Exception as exc:
            job.update(status="failed", progress=1.0, error=str(exc), retryable=False)
            self._save_state()
            self._validate("ReferenceJob", job)
            return 200, dict(job)
        self.references[profile["reference_id"]] = profile
        if song.get("pending_reference_job_id") == job_id:
            song["reference_id"] = profile["reference_id"]
        job.update(status="completed", progress=1.0, error=None, retryable=False)
        self._save_state()
        self._validate("ReferenceJob", job)
        return 200, dict(job)

    def get_job(self, job_id: str) -> tuple[int, dict]:
        if job_id not in self.jobs:
            raise APIError(404, "unknown_job", "Job does not exist.")
        job = dict(self.jobs[job_id])
        self._validate("ReferenceJob", job)
        return 200, job

    def create_session(self, request: dict) -> tuple[int, dict]:
        self._validate("CreateSessionRequest", request)
        song = self.songs.get(request.get("song_id"))
        reference_id = request.get("reference_id")
        reference = self.references.get(reference_id)
        if song is None:
            raise APIError(404, "unknown_song", "Song does not exist.")
        if reference is None:
            raise APIError(409, "reference_not_ready", "A completed reference profile is required.")
        if reference["song_id"] != song["song_id"] or song["reference_id"] != reference_id:
            raise APIError(409, "reference_not_selected", "Reference is not the selected completed revision.")
        model = self.analyzer_factory().capabilities()["model"]
        if any(reference[key] != model[key] for key in ("model_bundle_id", "frontend_id", "taxonomy_id")):
            raise APIError(409, "incompatible_reference", "Reanalyze the reference with the active model/frontend/taxonomy.")
        source = request.get("source")
        capture = copy.deepcopy(request.get("capture_fingerprint"))
        source_id = source["input_asset_or_device_id"]
        if capture["device_id"] != source_id:
            raise APIError(422, "capture_source_mismatch", "Capture device must match the selected source.")
        runtime_verified = False
        if source["input_kind"] == "uploaded_file":
            if source_id not in self.assets:
                raise APIError(404, "unknown_audio_asset", "Uploaded session source does not exist.")
        else:
            if self.managed_audio:
                try:
                    devices = self._native().discover()
                except Exception as exc:
                    raise APIError(503, "audio_device_unavailable", str(exc)) from exc
                if not any(item.device_id == source_id for item in devices):
                    raise APIError(503, "audio_device_unavailable", "Microphone is not available to this runtime.")
                if capture["channels"] != 1:
                    raise APIError(422, "unsupported_capture_channels", "Native capture currently requires mono.")
            elif source_id not in self.available_audio_devices:
                raise APIError(503, "audio_device_unavailable", "Microphone is not available to this runtime.")
            else:
                runtime_verified = bool(self.analyzer_factory().capabilities()["example_only"])
        if self.managed_audio:
            # Browser declarations cannot prove gain, enhancement, geometry or
            # physical provenance. Platform validation is a separate Lead gate.
            capture.update(gain_setting=None, enhancements_verified_disabled=None,
                           geometry_id=None, provenance="unverified")
            if source["input_kind"] == "uploaded_file":
                capture["native_sample_rate_hz"] = self.assets[source_id]["sample_rate_hz"]
                capture["channels"] = 1
        session_id = self._id("session")
        source_binding = dict(source)
        source_binding["clock_id"] = self._id("clock")
        analyzer = self.analyzer_factory()
        kwargs = {}
        if self.monotonic_clock is not None:
            kwargs["monotonic_clock"] = self.monotonic_clock
        if self.wall_clock is not None:
            kwargs["wall_clock"] = self.wall_clock
        session = PASession(
            session_id=session_id,
            project_id=song["project_id"],
            song_id=song["song_id"],
            song_name=song["name"],
            instrument_config=song["instrument_config"],
            reference_profile=reference,
            source=source_binding,
            capture_fingerprint=capture,
            analyzer=analyzer,
            baseline_store=BaselineStore(),
            capture_runtime_verified=runtime_verified,
            **kwargs,
        )
        ledger = SQLiteCommandLedger(self._store, session_id)
        session.set_persistence_callback(
            lambda value, identifier=session_id: self._save_session_state(identifier, value)
        )
        response = session.snapshot()
        self._validate("CreateSessionResponse", response)
        self._store.save_runtime_and_session(
            self._runtime_state_payload(), session.export_state()
        )
        self.sessions[session_id] = session
        self.handlers[session_id] = CommandHandler(session=session, ledger=ledger)
        if self.managed_audio:
            self._start_worker(session)
            response = session.snapshot()
        return 201, response

    def _start_worker(self, session):
        source = session.source
        clock = session.monotonic_clock
        try:
            if source["input_kind"] == "uploaded_file":
                asset = self.assets[source["input_asset_or_device_id"]]
                audio = FileAudioInput(input_asset_or_device_id=asset["asset_id"],
                    clock_id=source["clock_id"], sample_rate_hz=asset["sample_rate_hz"],
                    samples=asset["samples"], origin_monotonic_s=clock(),
                    chunk_size_samples=min(1024, self.pipeline.hop_size_samples))
            else:
                audio = NativeMicAudioInput(backend=self._native(),
                    device_id=source["input_asset_or_device_id"], clock_id=source["clock_id"],
                    sample_rate_hz=session.capture_fingerprint["native_sample_rate_hz"], clock=clock)
            def observe(window, quality, max_age):
                with session.command_transaction():
                    if session.song["workflow_state"] in ("SUSPENDED", "STOPPED"):
                        return
                    native = source["input_kind"] == "live_microphone"
                    if native and not session.capture_runtime_verified:
                        quality["capture_compatible"] = False
                        quality["reason_codes"].append("capture_not_runtime_verified")
                    session.observe_window(window, quality=quality, max_age_s=max_age,
                                           clock_uncertainty_s=0.05 if native else 0.0)
            def ended(reason):
                with session.command_transaction():
                    if session.song["workflow_state"] not in ("SUSPENDED", "STOPPED"):
                        session.suspend_for_input(reason)
            worker = AudioWorker(audio_input=audio, pipeline=self.pipeline,
                session_id=session.session_id, on_window=observe, on_end=ended, clock=clock,
                pace_file=source["input_kind"] == "uploaded_file")
            self.workers[session.session_id] = worker
            worker.start()
        except Exception as exc:
            failed = self.workers.pop(session.session_id, None)
            if failed is not None:
                failed.stop()
            session.suspend_for_input(f"audio_start_failed:{exc}")

    def close(self):
        with self._lifecycle_lock:
            for worker in self.workers.values():
                worker.stop()

    def get_session(self, session_id: str) -> tuple[int, dict]:
        if session_id not in self.sessions:
            raise APIError(404, "unknown_session", "Session does not exist.")
        return 200, self.sessions[session_id].snapshot()

    def post_action(self, session_id: str, command: dict) -> tuple[int, dict]:
        if session_id not in self.handlers or command.get("session_id") != session_id:
            raise APIError(422, "session_mismatch", "URL and command session IDs must match.")
        if command.get("action") == "accept_baseline":
            raise APIError(422, "wrong_endpoint", "accept_baseline must use the baseline endpoint.")
        with self._lifecycle_lock:
            response = self.handlers[session_id].handle(command)
            # Reconcile against current authoritative state, never a cached retry's
            # historical snapshot. Retrying resume after stop cannot restart capture.
            if self.managed_audio:
                session = self.sessions[session_id]
                state = session.snapshot()["song"]["workflow_state"]
                worker = self.workers.get(session_id)
                if state in ("SUSPENDED", "STOPPED"):
                    if worker is not None:
                        worker.stop()
                        self.workers.pop(session_id, None)
                elif worker is None or worker._finished.is_set():
                    if worker is not None:
                        worker.stop()
                    self._start_worker(session)
            return response["http_status"], response

    def accept_baseline(self, session_id: str, command: dict) -> tuple[int, dict]:
        if command.get("action") != "accept_baseline":
            raise APIError(422, "wrong_endpoint", "Baseline endpoint requires accept_baseline.")
        if session_id not in self.handlers or command.get("session_id") != session_id:
            raise APIError(422, "session_mismatch", "URL and command session IDs must match.")
        response = self.handlers[session_id].handle(command)
        return response["http_status"], response

    def connect_events(self, session_id: str, *, after_sequence: int | None = None) -> tuple[int, dict]:
        if session_id not in self.sessions:
            raise APIError(404, "unknown_session", "Session does not exist.")
        session = self.sessions[session_id]
        if after_sequence is None:
            snapshot = session.snapshot()
            return 200, {"snapshot": snapshot, "cursor": snapshot["event_sequence"], "events": []}
        events = session.events_after(after_sequence)
        return 200, {"snapshot": None, "cursor": events[-1]["event_sequence"] if events else after_sequence, "events": events}

    def runtime_session(self, session_id: str) -> PASession:
        """Worker-only hook for feeding shared-pipeline windows; never exposed to UI."""
        return self.sessions[session_id]
