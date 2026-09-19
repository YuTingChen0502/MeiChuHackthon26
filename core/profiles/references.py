"""Uploaded ideal-reference preparation through the shared audio path."""

from __future__ import annotations

import hashlib
import struct

from core.contracts.validation import PUBLIC, validate_record


class ReferenceBuilder:
    def __init__(self, *, pipeline, analyzer) -> None:
        self.pipeline = pipeline
        self.analyzer = analyzer

    @staticmethod
    def _audio_hash(audio_input) -> str:
        digest = hashlib.sha256()
        for value in audio_input.samples:
            digest.update(struct.pack("<f", value))
        return f"sha256:{digest.hexdigest()}"

    def build(
        self,
        *,
        audio_input,
        session_id: str,
        analysis_run_id: str,
        reference_id: str,
        song_id: str,
        instrument_config: dict,
    ) -> dict:
        windows = list(
            self.pipeline.iter_windows(
                audio_input, session_id=session_id, analysis_run_id=analysis_run_id
            )
        )
        prepared = self.analyzer.prepare_reference(windows, instrument_config)
        duration_s = len(audio_input.samples) / audio_input.sample_rate_hz
        coverage = [
            {
                "instrument_id": item["instrument_id"],
                "valid_active_seconds": duration_s,
                "qualified_nonoverlap_windows": len(windows),
                "status": "adequate",
            }
            for item in instrument_config["instruments"]
        ]
        model = self.analyzer.capabilities()["model"]
        profile = {
            "record_type": "ReferenceProfile",
            "schema_version": "1.0",
            "reference_id": reference_id,
            "song_id": song_id,
            "source_asset_hash": self._audio_hash(audio_input),
            "model_bundle_id": model["model_bundle_id"],
            "frontend_id": model["frontend_id"],
            "taxonomy_id": model["taxonomy_id"],
            "instrument_config_version": instrument_config["instrument_config_version"],
            "duration_s": duration_s,
            "coverage": coverage,
            "context_policy": "fixed_target_with_comparability_gate",
            "model_specific_context_asset": prepared["model_specific_context_asset"],
            "limitations": ["Simulated fake-analyzer reference; example only."],
            "comparison_regime": "matched_excerpt",
        }
        validate_record(profile, PUBLIC, "ReferenceProfile")
        return profile
