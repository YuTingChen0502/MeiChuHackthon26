"""Source-level extraction from amplitude-preserving separator tensors."""

from __future__ import annotations

from statistics import median
from typing import Mapping

import numpy as np


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
    activity_floor_dbfs: float = -70.0,
) -> tuple[dict[str, float | None], float | None, dict[str, float | None]]:
    names = sorted(set(reference_sources) | set(observation_sources))
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
    values = [value for value in raw.values() if value is not None]
    common = float(median(values)) if values else None
    centered = {
        name: (value - common if value is not None and common is not None else None)
        for name, value in raw.items()
    }
    return raw, common, centered

