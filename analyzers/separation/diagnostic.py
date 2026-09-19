"""Synthetic-only mixed-audio separator used to falsify benchmark plumbing.

This is not a product candidate.  It uses fixed non-overlapping bands that match
the generated synthetic smoke assets and must never be reported as HTDemucs or
rights-cleared music feasibility evidence.
"""

from __future__ import annotations

import numpy as np

from analyzers.separation.base import SeparationResult


SYNTHETIC_BANDS_HZ = {
    "bass": (40.0, 240.0),
    "guitar": (280.0, 1100.0),
    "vocals": (1200.0, 3200.0),
    "drums": (3600.0, 7600.0),
}


class SyntheticBandSeparator:
    backend_id = "synthetic_band_masks_v1"
    checkpoint_id = "none-deterministic-dsp"

    def separate(self, mixture: np.ndarray, sample_rate_hz: int) -> SeparationResult:
        signal = np.asarray(mixture, dtype=np.float64)
        if signal.ndim != 1:
            raise ValueError("Synthetic diagnostic expects mono audio")
        spectrum = np.fft.rfft(signal)
        frequency = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate_hz)
        sources = {}
        for name, (low, high) in SYNTHETIC_BANDS_HZ.items():
            mask = (frequency >= low) & (frequency < high)
            sources[name] = np.fft.irfft(spectrum * mask, n=signal.size)
        return SeparationResult(
            sources=sources,
            sample_rate_hz=sample_rate_hz,
            backend_id=self.backend_id,
            checkpoint_id=self.checkpoint_id,
        )

