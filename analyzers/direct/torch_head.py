"""Small portable pair-fusion head for direct-estimator training probes.

The audio encoder is intentionally outside this module.  The head accepts paired
frame/clip features plus explicit scale-sensitive features, so EfficientAT and future
encoders can be compared without changing output semantics or the training objective.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class DirectObjectiveWeights:
    level: float = 1.0
    activity: float = 0.25
    event: float = 0.25
    common: float = 0.5
    consistency: float = 0.25


class DirectPairFusionHead(nn.Module):
    """One-hidden-layer head; capacity choices remain an open experiment."""

    def __init__(
        self,
        *,
        embedding_dim: int,
        scale_feature_dim: int,
        source_count: int,
        hidden_dim: int = 64,
    ) -> None:
        super().__init__()
        if min(embedding_dim, scale_feature_dim, source_count, hidden_dim) <= 0:
            raise ValueError("All direct-head dimensions must be positive")
        self.embedding_dim = embedding_dim
        self.scale_feature_dim = scale_feature_dim
        self.source_count = source_count
        fused_dim = embedding_dim * 4 + scale_feature_dim
        self.fusion = nn.Sequential(
            nn.Linear(fused_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
        )
        self.source_delta = nn.Linear(hidden_dim, source_count)
        self.activity = nn.Linear(hidden_dim, source_count)
        self.event = nn.Linear(hidden_dim, source_count)
        self.common_gain = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        reference_embedding: Tensor,
        observation_embedding: Tensor,
        scale_features: Tensor,
    ) -> dict[str, Tensor]:
        if reference_embedding.shape != observation_embedding.shape:
            raise ValueError("Reference and observation embedding shapes must match")
        if reference_embedding.ndim != 2 or reference_embedding.shape[1] != self.embedding_dim:
            raise ValueError("Expected embeddings shaped [batch, embedding_dim]")
        if scale_features.ndim != 2 or scale_features.shape != (
            reference_embedding.shape[0], self.scale_feature_dim
        ):
            raise ValueError("Expected scale features shaped [batch, scale_feature_dim]")
        fused = torch.cat(
            (
                reference_embedding,
                observation_embedding,
                observation_embedding - reference_embedding,
                observation_embedding * reference_embedding,
                scale_features,
            ),
            dim=1,
        )
        hidden = self.fusion(fused)
        return {
            "source_delta_db": self.source_delta(hidden),
            "activity_logit": self.activity(hidden),
            "event_logit": self.event(hidden),
            "common_gain_db": self.common_gain(hidden).squeeze(1),
        }


def _masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    numeric_mask = mask.to(dtype=values.dtype)
    return (values * numeric_mask).sum() / numeric_mask.sum().clamp_min(1.0)


def direct_multitask_loss(
    outputs: Mapping[str, Tensor],
    *,
    raw_source_delta_db: Tensor,
    valid_source_mask: Tensor,
    activity_target: Tensor,
    event_target: Tensor,
    common_gain_db: Tensor,
    common_gain_valid_mask: Tensor,
    pair_valid_mask: Tensor,
    consistency_pairs: Tensor | None = None,
    weights: DirectObjectiveWeights = DirectObjectiveWeights(),
) -> dict[str, Tensor]:
    """Compute the initial masked objective without letting null labels leak NaNs."""

    predicted_delta = outputs["source_delta_db"]
    source_mask = valid_source_mask.bool() & pair_valid_mask.bool().unsqueeze(1)
    safe_delta_target = torch.where(source_mask, raw_source_delta_db, predicted_delta.detach())
    level_values = F.smooth_l1_loss(predicted_delta, safe_delta_target, reduction="none")
    level_loss = _masked_mean(level_values, source_mask)

    activity_values = F.binary_cross_entropy_with_logits(
        outputs["activity_logit"], activity_target.to(predicted_delta.dtype), reduction="none"
    )
    activity_mask = pair_valid_mask.bool().unsqueeze(1).expand_as(activity_values)
    activity_loss = _masked_mean(activity_values, activity_mask)

    event_values = F.binary_cross_entropy_with_logits(
        outputs["event_logit"], event_target.to(predicted_delta.dtype), reduction="none"
    )
    event_loss = _masked_mean(event_values, source_mask)

    common_prediction = outputs["common_gain_db"]
    common_mask = common_gain_valid_mask.bool() & pair_valid_mask.bool()
    safe_common_target = torch.where(common_mask, common_gain_db, common_prediction.detach())
    common_values = F.smooth_l1_loss(
        common_prediction, safe_common_target, reduction="none"
    )
    common_loss = _masked_mean(common_values, common_mask)

    consistency_loss = predicted_delta.sum() * 0.0
    if consistency_pairs is not None and consistency_pairs.numel() > 0:
        if consistency_pairs.ndim != 2 or consistency_pairs.shape[1] != 2:
            raise ValueError("consistency_pairs must be shaped [pair_count, 2]")
        left, right = consistency_pairs[:, 0].long(), consistency_pairs[:, 1].long()
        normalized = predicted_delta - common_prediction.unsqueeze(1)
        consistency_mask = source_mask[left] & source_mask[right]
        consistency_values = F.smooth_l1_loss(
            normalized[left], normalized[right], reduction="none"
        )
        consistency_loss = _masked_mean(consistency_values, consistency_mask)

    total = (
        weights.level * level_loss
        + weights.activity * activity_loss
        + weights.event * event_loss
        + weights.common * common_loss
        + weights.consistency * consistency_loss
    )
    return {
        "total": total,
        "level": level_loss,
        "activity": activity_loss,
        "event": event_loss,
        "common": common_loss,
        "consistency": consistency_loss,
    }
