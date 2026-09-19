"""Incremental, amplitude-preserving framing shared by all audio inputs."""
from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from .types import AudioChunk, AudioWindow
from .frontend import AudioFrontend


class SharedAudioPipeline:
    def __init__(self, *, window_size_samples: int, hop_size_samples: int | None = None, sample_rate_hz: int | None = None) -> None:
        self.frontend = AudioFrontend(sample_rate_hz)
        self.window_size_samples = window_size_samples
        self.hop_size_samples = window_size_samples if hop_size_samples is None else hop_size_samples
        if not 0 < self.hop_size_samples <= self.window_size_samples:
            raise ValueError("require 0 < hop_size_samples <= window_size_samples")

    def iter_windows(self, audio_input, *, session_id: str, analysis_run_id: str) -> Iterator[AudioWindow]:
        yield from self.windows_from_chunks(audio_input.chunks(), session_id=session_id,
                                            analysis_run_id=analysis_run_id)

    def windows_from_chunks(self, chunks: Iterable[AudioChunk], *, session_id: str,
                            analysis_run_id: str) -> Iterator[AudioWindow]:
        # At most one window of PCM is retained, irrespective of stream duration.
        first = None
        samples = []
        clipping = []
        expected_start = 0
        window_start = 0
        origin = 0.0
        for chunk in self.frontend.chunks(chunks):
            if (chunk.sample_rate_hz <= 0 or chunk.sample_start < 0 or not chunk.samples
                    or not math.isfinite(chunk.capture_end_monotonic_s)
                    or not all(math.isfinite(value) for value in chunk.samples)):
                raise ValueError("invalid PCM, sample span or clock")
            if first is None:
                first = chunk
                expected_start = window_start = chunk.sample_start
                origin = chunk.capture_end_monotonic_s - chunk.sample_end / chunk.sample_rate_hz
            if (chunk.input_kind, chunk.input_asset_or_device_id, chunk.clock_id, chunk.sample_rate_hz) != (
                    first.input_kind, first.input_asset_or_device_id, first.clock_id, first.sample_rate_hz):
                raise ValueError("audio run changed source, clock, or sample rate")
            if chunk.sample_start != expected_start:
                raise ValueError("audio run contains a gap or overlap")
            expected_time = origin + chunk.sample_end / chunk.sample_rate_hz
            if abs(chunk.capture_end_monotonic_s - expected_time) > 1.0 / chunk.sample_rate_hz:
                raise ValueError("audio run contains a clock discontinuity")
            expected_start = chunk.sample_end
            offset = 0
            while offset < len(chunk.samples):
                take = min(self.window_size_samples - len(samples), len(chunk.samples) - offset)
                samples.extend(chunk.samples[offset:offset + take])
                clipping.extend([chunk.input_clipped_fraction]*take)
                offset += take
                if len(samples) == self.window_size_samples:
                    end = window_start + self.window_size_samples
                    yield AudioWindow(
                        window_id=f"{analysis_run_id}:{window_start}:{end}", session_id=session_id,
                        analysis_run_id=analysis_run_id, input_kind=first.input_kind,
                        input_asset_or_device_id=first.input_asset_or_device_id, clock_id=first.clock_id,
                        sample_rate_hz=first.sample_rate_hz, sample_start=window_start, sample_end=end,
                        capture_end_monotonic_s=origin + end / first.sample_rate_hz, samples=tuple(samples),
                        input_clipped_fraction=max(clipping))
                    del samples[:self.hop_size_samples]
                    del clipping[:self.hop_size_samples]
                    window_start += self.hop_size_samples
