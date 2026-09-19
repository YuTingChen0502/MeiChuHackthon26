"""Input adapters acquire PCM only; semantic processing is deliberately absent."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .types import AudioChunk, InputKind


class _MemoryAudioInput:
    def __init__(
        self,
        *,
        input_kind: InputKind,
        input_asset_or_device_id: str,
        clock_id: str,
        sample_rate_hz: int,
        samples: Iterable[float],
        origin_monotonic_s: float,
        chunk_size_samples: int | None = None,
    ) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        values = tuple(float(value) for value in samples)
        if not values:
            raise ValueError("audio input cannot be empty")
        self.input_kind = input_kind
        self.input_asset_or_device_id = input_asset_or_device_id
        self.clock_id = clock_id
        self.sample_rate_hz = sample_rate_hz
        self.samples = values
        self.origin_monotonic_s = float(origin_monotonic_s)
        self.chunk_size_samples = chunk_size_samples or min(1024, len(values))
        if self.chunk_size_samples <= 0:
            raise ValueError("chunk_size_samples must be positive")

    def chunks(self) -> Iterator[AudioChunk]:
        for start in range(0, len(self.samples), self.chunk_size_samples):
            values = self.samples[start : start + self.chunk_size_samples]
            end = start + len(values)
            yield AudioChunk(
                input_kind=self.input_kind,
                input_asset_or_device_id=self.input_asset_or_device_id,
                clock_id=self.clock_id,
                sample_rate_hz=self.sample_rate_hz,
                sample_start=start,
                capture_end_monotonic_s=self.origin_monotonic_s + end / self.sample_rate_hz,
                samples=values,
            )


class FileAudioInput(_MemoryAudioInput):
    """Uploaded/replayed PCM mapped onto the current session clock."""

    def __init__(self, **kwargs) -> None:
        super().__init__(input_kind="uploaded_file", **kwargs)


class MicAudioInput(_MemoryAudioInput):
    """A deterministic microphone adapter used by the local runtime and tests."""

    def __init__(self, **kwargs) -> None:
        super().__init__(input_kind="live_microphone", **kwargs)
