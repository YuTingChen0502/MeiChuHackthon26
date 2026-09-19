"""Backend-neutral audio records used before the analyzer boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


InputKind = Literal["uploaded_file", "live_microphone"]


@dataclass(frozen=True)
class AudioChunk:
    """A contiguous mono PCM chunk on one application-owned clock."""

    input_kind: InputKind
    input_asset_or_device_id: str
    clock_id: str
    sample_rate_hz: int
    sample_start: int
    capture_end_monotonic_s: float
    samples: tuple[float, ...]

    @property
    def sample_end(self) -> int:
        return self.sample_start + len(self.samples)


@dataclass(frozen=True)
class AudioWindow:
    """Exact analyzer PCM plus the frozen WindowIdentity metadata."""

    window_id: str
    session_id: str
    analysis_run_id: str
    input_kind: InputKind
    input_asset_or_device_id: str
    clock_id: str
    sample_rate_hz: int
    sample_start: int
    sample_end: int
    capture_end_monotonic_s: float
    samples: tuple[float, ...]

    def identity(self) -> dict:
        return {
            "window_id": self.window_id,
            "session_id": self.session_id,
            "analysis_run_id": self.analysis_run_id,
            "input_kind": self.input_kind,
            "input_asset_or_device_id": self.input_asset_or_device_id,
            "clock_id": self.clock_id,
            "sample_rate_hz": self.sample_rate_hz,
            "sample_start": self.sample_start,
            "sample_end": self.sample_end,
            "capture_end_monotonic_s": self.capture_end_monotonic_s,
        }

    @property
    def start_monotonic_s(self) -> float:
        return self.capture_end_monotonic_s - (
            (self.sample_end - self.sample_start) / self.sample_rate_hz
        )
