"""Backend-neutral source-separator boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

import numpy as np


@dataclass(frozen=True)
class SeparationResult:
    sources: Mapping[str, np.ndarray]
    sample_rate_hz: int
    backend_id: str
    checkpoint_id: str


class SourceSeparator(Protocol):
    backend_id: str
    checkpoint_id: str

    def separate(self, mixture: np.ndarray, sample_rate_hz: int) -> SeparationResult:
        """Separate a mixed waveform without side-channel labels."""

