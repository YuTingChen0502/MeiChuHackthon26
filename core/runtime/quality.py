"""Quality metadata and hard gates shared by confidence, incidents, and verification."""

from __future__ import annotations


def pcm_clipped_fraction(samples) -> float:
    """Conservative digital-rail gate including PCM16's positive full-scale value.

    PCM16 +32767 decodes below 1.0; testing only abs(x) >= 1 misses its rail.
    This is a transport quality guard, not a measurement of analog clipping.
    """
    if not samples:
        raise ValueError("clipping requires a nonempty PCM span")
    rail = 32767 / 32768
    return sum(abs(value) >= rail for value in samples) / len(samples)


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
