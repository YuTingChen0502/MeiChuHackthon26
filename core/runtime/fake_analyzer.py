"""Deterministic analyzer test double implementing the frozen evidence boundary.

Every response is conspicuously identified as simulated via model/provider metadata
and the contract-required ``example_only`` flag. It is not an accuracy claim.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field

from core.contracts.validation import validate_analyzer_pair


@dataclass(frozen=True)
class FakeEvidenceSpec:
    deltas_db: dict[str, float] = field(default_factory=dict)
    source_levels_db: dict[str, tuple[float, float]] = field(default_factory=dict)
    inactive: frozenset[str] = frozenset()
    unsupported: frozenset[str] = frozenset()
    invalid_reasons: dict[str, str] = field(default_factory=dict)
    raw_error_scale_db: float | None = 0.5
    matched_context_window_id: str = "fake-matched-context"


class FakeInstrumentAnalyzer:
    """Scripted fake that never inspects fixture labels from PCM or filenames."""

    MODEL = {
        "model_bundle_id": "fake-instrument-analyzer-v1-simulated",
        "frontend_id": "shared-pcm-frontend-v1",
        "taxonomy_id": "configured-families-v1",
        "execution_profile_id": "fake-cpu-fp32-v1",
        "level_scale_id": "pcm-float-rms-v1",
    }

    def __init__(self, specs: list[FakeEvidenceSpec] | None = None) -> None:
        self._specs = deque(specs or [])
        self.closed = False

    def capabilities(self) -> dict:
        return {
            "provider": "fake-simulated",
            "example_only": True,
            "supported_families": ["guitar", "bass", "drums", "vocals", "piano"],
            "evidence_modes": ["source_level_deltas", "source_levels"],
            "model": copy.deepcopy(self.MODEL),
        }

    def prepare_reference(self, windows, instrument_config: dict) -> dict:
        material = list(windows)
        if not material:
            raise ValueError("reference preparation requires at least one audio window")
        return {
            "model_specific_context_asset": (
                f"fake-simulated-reference-context:{material[0].analysis_run_id}"
            ),
            "window_count": len(material),
            "example_only": True,
        }

    def queue(self, *specs: FakeEvidenceSpec) -> None:
        self._specs.extend(specs)

    def analyze(self, window, context: dict) -> dict:
        if self.closed:
            raise RuntimeError("analyzer is closed")
        if not self._specs:
            raise RuntimeError("FakeInstrumentAnalyzer has no scripted evidence")
        spec = self._specs.popleft()
        use_levels = bool(spec.source_levels_db)
        measurements = []
        for configured in context["instrument_config"]["instruments"]:
            instrument_id = configured["instrument_id"]
            common = {
                "instrument_id": instrument_id,
                "family": configured["family"],
                "reason_codes": [],
                "uncertainty_features": [],
            }
            if instrument_id in spec.unsupported:
                common.update(
                    activity="unsupported",
                    observability="not_observable",
                    validity="invalid",
                    reason_codes=["unsupported_source"],
                )
                numeric = (None, None) if use_levels else None
            elif instrument_id in spec.inactive:
                common.update(
                    activity="inactive",
                    observability="not_observable",
                    validity="invalid",
                    reason_codes=["source_inactive"],
                )
                numeric = (None, None) if use_levels else None
            elif instrument_id in spec.invalid_reasons:
                common.update(
                    activity="unknown",
                    observability="unknown",
                    validity="invalid",
                    reason_codes=[spec.invalid_reasons[instrument_id]],
                )
                numeric = (None, None) if use_levels else None
            else:
                common.update(activity="active", observability="observable", validity="valid")
                if spec.raw_error_scale_db is not None:
                    common["uncertainty_features"] = [
                        {
                            "name": "raw_error_scale_db",
                            "value": spec.raw_error_scale_db,
                            "unit": "dB",
                        }
                    ]
                numeric = (
                    spec.source_levels_db.get(instrument_id, (-20.0, -20.0))
                    if use_levels
                    else spec.deltas_db.get(instrument_id, 0.0)
                )
            if use_levels:
                common["source_level_db"], common["target_source_level_db"] = numeric
            else:
                common["source_level_delta_db"] = numeric
            measurements.append(common)

        evidence = {
            "record_type": "AnalyzerEvidence",
            "schema_version": "1.0",
            "example_only": True,
            "observation": copy.deepcopy(context["observation"]),
            "model": copy.deepcopy(context["model"]),
            "instrument_config_version": context["instrument_config"][
                "instrument_config_version"
            ],
            "target": copy.deepcopy(context["target"]),
            "comparison_regime": context["comparison_regime"],
            "model_specific_context_asset": context["model_specific_context_asset"],
            "matched_context_window_id": (
                spec.matched_context_window_id
                if context["comparison_regime"] == "matched_excerpt"
                else None
            ),
            "evidence_mode": "source_levels" if use_levels else "source_level_deltas",
            "units": "dBFS_rms" if use_levels else "dB",
            "measurements": measurements,
        }
        validate_analyzer_pair(context, evidence)
        return evidence

    def close(self) -> None:
        self.closed = True
