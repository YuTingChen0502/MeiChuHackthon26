"""The one framing path shared by file replay, reference upload, and microphones."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator

from .types import AudioChunk, AudioWindow


class SharedAudioPipeline:
    def __init__(self, *, window_size_samples: int, hop_size_samples: int | None = None) -> None:
        if window_size_samples <= 0:
            raise ValueError("window_size_samples must be positive")
        self.window_size_samples = window_size_samples
        self.hop_size_samples = hop_size_samples or window_size_samples
        if self.hop_size_samples <= 0:
            raise ValueError("hop_size_samples must be positive")

    def iter_windows(self, audio_input, *, session_id: str, analysis_run_id: str) -> Iterator[AudioWindow]:
        yield from self.windows_from_chunks(
            audio_input.chunks(), session_id=session_id, analysis_run_id=analysis_run_id
        )

    def windows_from_chunks(
        self,
        chunks: Iterable[AudioChunk],
        *,
        session_id: str,
        analysis_run_id: str,
    ) -> Iterator[AudioWindow]:
        material = list(chunks)
        if not material:
            return
        first = material[0]
        samples: list[float] = []
        expected_start = first.sample_start
        for chunk in material:
            if (
                chunk.input_kind != first.input_kind
                or chunk.input_asset_or_device_id != first.input_asset_or_device_id
                or chunk.clock_id != first.clock_id
                or chunk.sample_rate_hz != first.sample_rate_hz
            ):
                raise ValueError("audio run changed source, clock, or sample rate")
            if chunk.sample_start != expected_start:
                raise ValueError("audio run contains a gap or overlap")
            if not all(math.isfinite(value) for value in chunk.samples):
                raise ValueError("PCM contains NaN or infinity")
            samples.extend(chunk.samples)
            expected_start = chunk.sample_end

        run_start = first.sample_start
        run_origin = first.capture_end_monotonic_s - len(first.samples) / first.sample_rate_hz
        for relative_start in range(
            0, len(samples) - self.window_size_samples + 1, self.hop_size_samples
        ):
            sample_start = run_start + relative_start
            sample_end = sample_start + self.window_size_samples
            capture_end = run_origin + (sample_end - run_start) / first.sample_rate_hz
            window_id = f"{analysis_run_id}:{sample_start}:{sample_end}"
            yield AudioWindow(
                window_id=window_id,
                session_id=session_id,
                analysis_run_id=analysis_run_id,
                input_kind=first.input_kind,
                input_asset_or_device_id=first.input_asset_or_device_id,
                clock_id=first.clock_id,
                sample_rate_hz=first.sample_rate_hz,
                sample_start=sample_start,
                sample_end=sample_end,
                capture_end_monotonic_s=capture_end,
                samples=tuple(samples[relative_start : relative_start + self.window_size_samples]),
            )
