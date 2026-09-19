"""Canonical gain-label arithmetic for controlled PA analyzer pairs.

The oracle keeps source injection, common gain, centered balance, and validity
separate.  It never converts an inactive source into a large negative dB value.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Mapping


@dataclass(frozen=True)
class GainLabels:
    source_injected_gain_db: dict[str, float]
    raw_source_delta_db: dict[str, float | None]
    common_mode_gain_db: float | None
    centered_balance_db: dict[str, float | None]
    valid_source_mask: dict[str, bool]


def compute_gain_labels(
    source_injected_gain_db: Mapping[str, float],
    *,
    common_gain_db: float = 0.0,
    active_sources: Mapping[str, bool] | None = None,
) -> GainLabels:
    """Compute source and centered labels using the frozen median convention.

    ``source_injected_gain_db`` excludes the separately recorded common gain.
    The raw source delta is their sum.  Only active sources participate in the
    median and receive numerical regression labels.
    """

    injected = {name: float(value) for name, value in source_injected_gain_db.items()}
    if not injected:
        raise ValueError("At least one configured source is required")
    active = (
        {name: True for name in injected}
        if active_sources is None
        else {name: bool(active_sources.get(name, False)) for name in injected}
    )
    raw = {
        name: common_gain_db + gain if active[name] else None
        for name, gain in injected.items()
    }
    active_values = [value for value in raw.values() if value is not None]
    center = float(median(active_values)) if active_values else None
    centered = {
        name: (value - center if value is not None and center is not None else None)
        for name, value in raw.items()
    }
    return GainLabels(
        source_injected_gain_db=injected,
        raw_source_delta_db=raw,
        common_mode_gain_db=center,
        centered_balance_db=centered,
        valid_source_mask=active,
    )

