"""Quality metadata and hard gates shared by confidence, incidents, and verification."""

from __future__ import annotations


def quality_state(
    *,
    clipped_fraction: float = 0.0,
    dropout: bool = False,
    stale: bool = False,
    comparability: str = "comparable",
    capture_compatible: bool = True,
    reason_codes: list[str] | None = None,
) -> dict:
    reasons = list(reason_codes or [])
    if clipped_fraction > 0 and "clipping" not in reasons:
        reasons.append("clipping")
    if dropout and "capture_dropout" not in reasons:
        reasons.append("capture_dropout")
    if stale and "stale_evidence" not in reasons:
        reasons.append("stale_evidence")
    if comparability != "comparable" and "not_comparable" not in reasons:
        reasons.append("not_comparable")
    if not capture_compatible and "capture_incompatible" not in reasons:
        reasons.append("capture_incompatible")
    return {
        "clipped_fraction": float(clipped_fraction),
        "dropout": bool(dropout),
        "stale": bool(stale),
        "comparability": comparability,
        "capture_compatible": bool(capture_compatible),
        "reason_codes": reasons,
        "snr_estimate_db": None,
        "snr_is_ground_truth": False,
    }


def hard_gate_reasons(quality: dict) -> list[str]:
    reasons = []
    if quality["clipped_fraction"] > 0:
        reasons.append("clipping")
    if quality["dropout"]:
        reasons.append("capture_dropout")
    if quality["stale"]:
        reasons.append("stale_evidence")
    if quality["comparability"] != "comparable":
        reasons.append("not_comparable")
    if not quality["capture_compatible"]:
        reasons.append("capture_incompatible")
    return reasons


def quality_is_usable(quality: dict) -> bool:
    return not hard_gate_reasons(quality)
