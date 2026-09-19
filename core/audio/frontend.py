"""Deterministic bounded PCM frontend shared by file and native inputs.

Mono input is amplitude preserving. Rate conversion uses a normalized 32-tap
Hann-windowed sinc low-pass; phase kernels are cached for one rational rate pair.
No gain normalization, denoising, or instrument semantics occur here.
"""
import math
from dataclasses import replace


class AudioFrontend:
    ID = "mono-sinc32-v1"

    def __init__(self, sample_rate_hz=None):
        if sample_rate_hz is not None and (type(sample_rate_hz) is not int or sample_rate_hz <= 0):
            raise ValueError("positive canonical sample rate required")
        self.sample_rate_hz = sample_rate_hz

    def chunks(self, chunks):
        first = previous = None
        buffer = []
        offset = output = 0
        origin = 0.0
        kernels = {}
        for chunk in chunks:
            if not chunk.samples or chunk.sample_rate_hz <= 0 or not all(math.isfinite(x) for x in chunk.samples):
                raise ValueError("invalid frontend PCM")
            target = self.sample_rate_hz or chunk.sample_rate_hz
            if target == chunk.sample_rate_hz:
                yield chunk
                continue
            if first is None:
                first = chunk
                offset = chunk.sample_start
                output = math.ceil(offset * target / chunk.sample_rate_hz)
                origin = chunk.capture_end_monotonic_s - chunk.sample_end / chunk.sample_rate_hz
            elif (chunk.clock_id != first.clock_id or chunk.sample_rate_hz != first.sample_rate_hz or
                  chunk.input_kind != first.input_kind or chunk.input_asset_or_device_id != first.input_asset_or_device_id or
                  chunk.sample_start != previous.sample_end or
                  abs(chunk.capture_end_monotonic_s - origin - chunk.sample_end/chunk.sample_rate_hz) > 1/chunk.sample_rate_hz):
                raise ValueError("frontend run discontinuity")
            buffer.extend(chunk.samples)
            # Output only when the entire right half of the filter is available.
            # Discard incomplete tails instead of inventing post-disconnect audio.
            values = []
            start = output
            while (output * chunk.sample_rate_hz) // target + 16 < offset + len(buffer):
                center, phase = divmod(output * chunk.sample_rate_hz, target)
                if phase not in kernels:
                    fraction = phase / target
                    cutoff = min(1.0, target/chunk.sample_rate_hz) * .94
                    weights = []
                    for tap in range(-15, 17):
                        distance = tap - fraction
                        sinc = cutoff if distance == 0 else math.sin(math.pi*cutoff*distance)/(math.pi*distance)
                        weights.append(sinc * (.5 + .5*math.cos(math.pi*distance/16)))
                    total = sum(weights)
                    kernels[phase] = tuple(w/total for w in weights)
                # Constant extension only at the beginning, never across gaps.
                value = sum(buffer[max(0, center+tap-offset)] * weight
                            for tap, weight in zip(range(-15,17), kernels[phase]))
                values.append(value)
                output += 1
            if values:
                yield replace(chunk, sample_rate_hz=target, sample_start=start,
                              capture_end_monotonic_s=origin+output/target, samples=tuple(values))
            keep_from = max(offset, (output*chunk.sample_rate_hz)//target-15)
            del buffer[:keep_from-offset]
            offset = keep_from
            previous = chunk
