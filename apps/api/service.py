"""Concrete in-process L2 setup/upload/job/session application facade.

The first checkpoint intentionally keeps transport separate. These methods define
the request/response payloads that a later loopback HTTP/WebSocket adapter delegates
to without duplicating workflow logic.
"""

from __future__ import annotations

import hashlib
import io
import wave
from pathlib import Path

from core.audio import FileAudioInput, SharedAudioPipeline
from core.profiles import BaselineStore, ReferenceBuilder
from core.runtime import FakeInstrumentAnalyzer
from roles.pa import PASession

from .commands import CommandHandler, JsonCommandLedger


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
        analyzer_factory=FakeInstrumentAnalyzer,
        monotonic_clock=None,
        wall_clock=None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = SharedAudioPipeline(
            window_size_samples=window_size_samples, hop_size_samples=hop_size_samples
        )
        self.analyzer_factory = analyzer_factory
        self.monotonic_clock = monotonic_clock
        self.wall_clock = wall_clock
        self.projects: dict[str, dict] = {}
        self.songs: dict[str, dict] = {}
        self.assets: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.references: dict[str, dict] = {}
        self.sessions: dict[str, PASession] = {}
        self.handlers: dict[str, CommandHandler] = {}
        self._counters = {name: 0 for name in ("project", "song", "asset", "job", "reference", "session")}

    def _id(self, kind: str) -> str:
        self._counters[kind] += 1
        return f"{kind}-{self._counters[kind]}"

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

    def audio_devices(self) -> tuple[int, dict]:
        return 200, {"devices": [], "discovery_status": "not_connected_in_checkpoint"}

    def create_project(self, request: dict) -> tuple[int, dict]:
        name = request.get("name")
        if not isinstance(name, str) or not name.strip():
            raise APIError(422, "invalid_project", "Project name is required.")
        project_id = self._id("project")
        record = {"project_id": project_id, "name": name.strip()}
        self.projects[project_id] = record
        return 201, dict(record)

    def create_song(self, request: dict) -> tuple[int, dict]:
        project_id, name, instruments = (
            request.get("project_id"), request.get("name"), request.get("instruments")
        )
        if project_id not in self.projects:
            raise APIError(422, "unknown_project", "Project does not exist.")
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
        record = {
            "song_id": song_id,
            "project_id": project_id,
            "name": name.strip(),
            "instrument_config": {"instrument_config_version": 1, "instruments": normalized},
            "supported_families": families,
            "unsupported_families": [],
            "reference_id": None,
        }
        self.songs[song_id] = record
        return 201, {key: value for key, value in record.items() if key != "instrument_config"} | {
            "instrument_config": record["instrument_config"]
        }

    def upload_audio(self, content: bytes, *, filename: str) -> tuple[int, dict]:
        if not content:
            raise APIError(422, "empty_upload", "Audio upload is empty.")
        sample_rate, samples, channels = _decode_pcm16_wav(content)
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
        return 201, {
            "asset_id": asset_id,
            "content_hash": digest,
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "duration_s": len(samples) / sample_rate,
        }

    def start_reference_job(self, song_id: str, request: dict) -> tuple[int, dict]:
        song = self.songs.get(song_id)
        asset = self.assets.get(request.get("asset_id"))
        if song is None or asset is None:
            raise APIError(422, "unknown_song_or_asset", "Song and audio asset must exist.")
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
        return 202, dict(job)

    def run_reference_job(self, job_id: str) -> tuple[int, dict]:
        job = self.jobs.get(job_id)
        if job is None:
            raise APIError(404, "unknown_job", "Reference job does not exist.")
        if job["status"] == "completed":
            return 200, dict(job)
        song, asset = self.songs[job["song_id"]], self.assets[job["asset_id"]]
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
            )
        except Exception as exc:
            job.update(status="failed", progress=1.0, error=str(exc), retryable=False)
            return 200, dict(job)
        self.references[profile["reference_id"]] = profile
        song["reference_id"] = profile["reference_id"]
        job.update(status="completed", progress=1.0, error=None, retryable=False)
        return 200, dict(job)

    def get_job(self, job_id: str) -> tuple[int, dict]:
        if job_id not in self.jobs:
            raise APIError(404, "unknown_job", "Job does not exist.")
        return 200, dict(self.jobs[job_id])

    def create_session(self, request: dict) -> tuple[int, dict]:
        song = self.songs.get(request.get("song_id"))
        if song is None or song["reference_id"] not in self.references:
            raise APIError(409, "reference_not_ready", "A completed reference profile is required.")
        source = request.get("source")
        capture = request.get("capture_fingerprint")
        if not isinstance(source, dict) or set(source) != {"input_kind", "input_asset_or_device_id", "clock_id"}:
            raise APIError(422, "invalid_source", "Session source binding is incomplete.")
        if not isinstance(capture, dict):
            raise APIError(422, "invalid_capture", "Capture fingerprint is required.")
        session_id = self._id("session")
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
            reference_profile=self.references[song["reference_id"]],
            source=source,
            capture_fingerprint=capture,
            analyzer=analyzer,
            baseline_store=BaselineStore(),
            **kwargs,
        )
        ledger = JsonCommandLedger(self.storage_dir / "sessions" / session_id / "commands.json")
        self.sessions[session_id] = session
        self.handlers[session_id] = CommandHandler(session=session, ledger=ledger)
        return 201, session.snapshot()

    def get_session(self, session_id: str) -> tuple[int, dict]:
        if session_id not in self.sessions:
            raise APIError(404, "unknown_session", "Session does not exist.")
        return 200, self.sessions[session_id].snapshot()

    def post_action(self, session_id: str, command: dict) -> tuple[int, dict]:
        if session_id not in self.handlers or command.get("session_id") != session_id:
            raise APIError(422, "session_mismatch", "URL and command session IDs must match.")
        response = self.handlers[session_id].handle(command)
        return response["http_status"], response

    def accept_baseline(self, session_id: str, command: dict) -> tuple[int, dict]:
        if command.get("action") != "accept_baseline":
            raise APIError(422, "wrong_endpoint", "Baseline endpoint requires accept_baseline.")
        return self.post_action(session_id, command)

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
