"""Source-level extraction from amplitude-preserving separator tensors."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class GainResponse:
    raw_source_delta_db: dict[str, float | None]
    common_mode_gain_db: float | None
    centered_balance_db: dict[str, float | None]
    numeric_valid_mask: dict[str, bool]
    reliable_configured_source_count: int
    balance_identifiable: bool


def rms_dbfs(signal: np.ndarray, *, activity_floor_dbfs: float = -70.0) -> float | None:
    array = np.asarray(signal, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.square(array))))
    if rms <= 0.0:
        return None
    level = 20.0 * np.log10(rms)
    return float(level) if level >= activity_floor_dbfs else None


def gain_response(
    reference_sources: Mapping[str, np.ndarray],
    observation_sources: Mapping[str, np.ndarray],
    *,
    configured_sources: Iterable[str],
    activity_floor_dbfs: float = -70.0,
    minimum_reliable_sources: int = 3,
) -> GainResponse:
    """Estimate configured-source changes and center only when identifiable.

    Separator-only outputs (for example HTDemucs ``piano`` and ``other`` when
    they are not configured product instruments) never enter the common-mode
    median. Numerical source deltas remain available for diagnostics when fewer
    than ``minimum_reliable_sources`` survive, but centered balance is withheld.
    """

    names = tuple(configured_sources)
    if not names or len(set(names)) != len(names):
        raise ValueError("configured_sources must be non-empty and unique")
    if minimum_reliable_sources < 1:
        raise ValueError("minimum_reliable_sources must be positive")
    raw: dict[str, float | None] = {}
    for name in names:
        reference = reference_sources.get(name)
        observation = observation_sources.get(name)
        if reference is None or observation is None:
            raw[name] = None
            continue
        ref_level = rms_dbfs(reference, activity_floor_dbfs=activity_floor_dbfs)
        obs_level = rms_dbfs(observation, activity_floor_dbfs=activity_floor_dbfs)
        raw[name] = None if ref_level is None or obs_level is None else obs_level - ref_level
    numeric_valid = {name: value is not None for name, value in raw.items()}
    values = [value for value in raw.values() if value is not None]
    identifiable = len(values) >= minimum_reliable_sources
    common = float(median(values)) if identifiable else None
    centered = {
        name: (value - common if value is not None and common is not None else None)
        for name, value in raw.items()
    }
    return GainResponse(
        raw_source_delta_db=raw,
        common_mode_gain_db=common,
        centered_balance_db=centered,
        numeric_valid_mask=numeric_valid,
        reliable_configured_source_count=len(values),
        balance_identifiable=identifiable,
    )
