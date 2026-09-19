"""Minimal direct-estimator shape; intentionally no premature training policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from analyzers.evidence import source_deltas_evidence


@dataclass(frozen=True)
class DirectEstimatorConfig:
    model_bundle_id: str = "direct-efficientat-scaffold-v1"
    encoder_candidate: str = "EfficientAT-mn10_as-or-mn05_as"
    frontend_id: str = "pending-checkpoint-frontend"
    taxonomy_id: str = "pa-known-instruments-v1"
    level_scale_id: str = "shared-pcm-scale-v1"


def raw_level_features(signal: np.ndarray) -> np.ndarray:
    """Retain scale evidence instead of relying on unit-normalized embeddings."""

    array = np.asarray(signal, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("Expected a non-empty mono window")
    rms = np.sqrt(np.mean(np.square(array)))
    peak = np.max(np.abs(array))
    return np.array(
        [20.0 * np.log10(max(rms, 1e-12)), 20.0 * np.log10(max(peak, 1e-12))],
        dtype=np.float64,
    )


def pair_fusion_features(reference: np.ndarray, observation: np.ndarray) -> np.ndarray:
    ref = raw_level_features(reference)
    obs = raw_level_features(observation)
    return np.concatenate([ref, obs, obs - ref, obs * ref])


class DirectEstimatorScaffold:
    """Contract-shaped placeholder that abstains until an adapted head exists."""

    def __init__(self, config: DirectEstimatorConfig | None = None) -> None:
        self.config = config or DirectEstimatorConfig()

    def analyze(
        self,
        reference: np.ndarray,
        observation: np.ndarray,
        context: Mapping[str, object],
        *,
        matched_context_window_id: str | None,
    ) -> dict[str, object]:
        _ = pair_fusion_features(reference, observation)
        instruments = context["instrument_config"]["instruments"]  # type: ignore[index]
        unavailable = {item["instrument_id"]: None for item in instruments}
        reasons = {
            item["instrument_id"]: ["direct_estimator_not_fitted"] for item in instruments
        }
        return source_deltas_evidence(
            context,
            source_deltas_db=unavailable,
            reason_codes=reasons,
            matched_context_window_id=matched_context_window_id,
        )

