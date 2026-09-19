"""Helpers that bind backend-neutral measurements to the frozen evidence schema."""

from __future__ import annotations

from typing import Mapping


def source_levels_evidence(
    context: Mapping[str, object],
    *,
    observed_levels_dbfs: Mapping[str, float | None],
    target_levels_dbfs: Mapping[str, float | None],
    reason_codes: Mapping[str, list[str]] | None = None,
    uncertainty_features: Mapping[str, list[dict[str, object]]] | None = None,
    matched_context_window_id: str | None,
    example_only: bool = False,
) -> dict[str, object]:
    """Create source-level evidence, never downstream InstrumentState."""

    reasons = reason_codes or {}
    uncertainty = uncertainty_features or {}
    measurements: list[dict[str, object]] = []
    instruments = context["instrument_config"]["instruments"]  # type: ignore[index]
    for instrument in instruments:
        instrument_id = instrument["instrument_id"]
        observed = observed_levels_dbfs.get(instrument_id)
        target = target_levels_dbfs.get(instrument_id)
        valid = observed is not None and target is not None
        item_reasons = list(reasons.get(instrument_id, []))
        if not valid and not item_reasons:
            item_reasons = ["measurement_unavailable"]
        measurements.append(
            {
                "instrument_id": instrument_id,
                "family": instrument["family"],
                "activity": "active" if valid else "unknown",
                "observability": "observable" if valid else "unknown",
                "validity": "valid" if valid else "invalid",
                "reason_codes": item_reasons,
                "uncertainty_features": list(uncertainty.get(instrument_id, [])),
                "source_level_db": observed if valid else None,
                "target_source_level_db": target if valid else None,
            }
        )
    return {
        "record_type": "AnalyzerEvidence",
        "schema_version": "1.0",
        "example_only": example_only,
        "observation": context["observation"],
        "model": context["model"],
        "instrument_config_version": context["instrument_config"]["instrument_config_version"],  # type: ignore[index]
        "target": context["target"],
        "comparison_regime": context["comparison_regime"],
        "model_specific_context_asset": context["model_specific_context_asset"],
        "matched_context_window_id": matched_context_window_id,
        "evidence_mode": "source_levels",
        "units": "dBFS_rms",
        "measurements": measurements,
    }


def source_deltas_evidence(
    context: Mapping[str, object],
    *,
    source_deltas_db: Mapping[str, float | None],
    reason_codes: Mapping[str, list[str]] | None = None,
    uncertainty_features: Mapping[str, list[dict[str, object]]] | None = None,
    matched_context_window_id: str | None,
    example_only: bool = False,
) -> dict[str, object]:
    """Create already-conditioned source deltas (before Core centering)."""

    reasons = reason_codes or {}
    uncertainty = uncertainty_features or {}
    measurements: list[dict[str, object]] = []
    instruments = context["instrument_config"]["instruments"]  # type: ignore[index]
    for instrument in instruments:
        instrument_id = instrument["instrument_id"]
        delta = source_deltas_db.get(instrument_id)
        valid = delta is not None
        item_reasons = list(reasons.get(instrument_id, []))
        if not valid and not item_reasons:
            item_reasons = ["measurement_unavailable"]
        measurements.append(
            {
                "instrument_id": instrument_id,
                "family": instrument["family"],
                "activity": "active" if valid else "unknown",
                "observability": "observable" if valid else "unknown",
                "validity": "valid" if valid else "invalid",
                "reason_codes": item_reasons,
                "uncertainty_features": list(uncertainty.get(instrument_id, [])),
                "source_level_delta_db": delta if valid else None,
            }
        )
    return {
        "record_type": "AnalyzerEvidence",
        "schema_version": "1.0",
        "example_only": example_only,
        "observation": context["observation"],
        "model": context["model"],
        "instrument_config_version": context["instrument_config"]["instrument_config_version"],  # type: ignore[index]
        "target": context["target"],
        "comparison_regime": context["comparison_regime"],
        "model_specific_context_asset": context["model_specific_context_asset"],
        "matched_context_window_id": matched_context_window_id,
        "evidence_mode": "source_level_deltas",
        "units": "dB",
        "measurements": measurements,
    }

