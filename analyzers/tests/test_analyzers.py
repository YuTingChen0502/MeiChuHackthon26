import unittest

import numpy as np

from analyzers.direct.scaffold import DirectEstimatorScaffold, pair_fusion_features
from analyzers.evidence import source_levels_evidence
from analyzers.separation.diagnostic import SyntheticBandSeparator
from analyzers.separation.htdemucs import HTDemucs6sSeparator
from analyzers.separation.levels import gain_response, rms_dbfs
from core.contracts.validation import validate_analyzer_pair


def context():
    return {
        "record_type": "AnalyzerContext",
        "schema_version": "1.0",
        "observation": {
            "window_id": "window-1",
            "session_id": "session-1",
            "analysis_run_id": "run-1",
            "input_kind": "uploaded_file",
            "input_asset_or_device_id": "asset-1",
            "clock_id": "clock-1",
            "sample_rate_hz": 16000,
            "sample_start": 0,
            "sample_end": 16000,
            "capture_end_monotonic_s": 1.0,
        },
        "model": {
            "model_bundle_id": "test-model",
            "frontend_id": "test-front",
            "taxonomy_id": "test-taxonomy",
            "execution_profile_id": "cpu-fp64",
            "level_scale_id": "shared-pcm-v1",
        },
        "instrument_config": {
            "instrument_config_version": 1,
            "instruments": [
                {"instrument_id": "bass", "family": "bass"},
                {"instrument_id": "guitar", "family": "guitar"},
            ],
        },
        "target": {
            "target_kind": "reference",
            "reference": {"reference_id": "reference-1", "source_asset_hash": "sha256:test"},
            "baseline": None,
        },
        "comparison_regime": "matched_excerpt",
        "model_specific_context_asset": "context-asset-1",
        "observation_purpose": "rehearsal",
        "probe_instrument_id": None,
    }


class AnalyzerFoundationTests(unittest.TestCase):
    def test_source_level_adapter_matches_frozen_contract(self):
        ctx = context()
        evidence = source_levels_evidence(
            ctx,
            observed_levels_dbfs={"bass": -20.0, "guitar": None},
            target_levels_dbfs={"bass": -22.0, "guitar": None},
            reason_codes={"guitar": ["source_inactive"]},
            matched_context_window_id="matched-1",
        )
        validate_analyzer_pair(ctx, evidence)
        guitar = evidence["measurements"][1]
        self.assertEqual("invalid", guitar["validity"])
        self.assertIsNone(guitar["source_level_db"])

    def test_direct_scaffold_abstains_with_contract_valid_evidence(self):
        ctx = context()
        evidence = DirectEstimatorScaffold().analyze(
            np.ones(16000), np.ones(16000), ctx,
            matched_context_window_id="matched-1",
        )
        validate_analyzer_pair(ctx, evidence)
        self.assertTrue(all(item["validity"] == "invalid" for item in evidence["measurements"]))

    def test_pair_features_retain_common_gain(self):
        reference = np.ones(100)
        observation = reference * 10 ** (4 / 20)
        features = pair_fusion_features(reference, observation)
        self.assertAlmostEqual(4.0, features[3] - features[1], places=10)

    def test_synthetic_separator_measures_one_source_gain_from_mixtures(self):
        sample_rate = 16000
        time = np.arange(sample_rate, dtype=np.float64) / sample_rate
        bass = 0.1 * np.sin(2 * np.pi * 100 * time)
        guitar = 0.1 * np.sin(2 * np.pi * 500 * time)
        reference = bass + guitar
        observation = bass + guitar * 10 ** (4 / 20)
        separator = SyntheticBandSeparator()
        ref = separator.separate(reference, sample_rate)
        obs = separator.separate(observation, sample_rate)
        raw, common, centered = gain_response(ref.sources, obs.sources)
        self.assertAlmostEqual(4.0, raw["guitar"], places=8)
        self.assertAlmostEqual(0.0, raw["bass"], places=8)
        # Four configured diagnostic bands include two inactive outputs. They are
        # masked by the activity floor and do not bias the two-source median.
        self.assertAlmostEqual(2.0, common, places=8)
        self.assertAlmostEqual(2.0, centered["guitar"], places=8)

    def test_silence_has_no_numeric_level(self):
        self.assertIsNone(rms_dbfs(np.zeros(100)))

    def test_htdemucs_runtime_status_is_explicit(self):
        status = HTDemucs6sSeparator.runtime_status()
        self.assertEqual(status["available"], not status["missing_modules"])


if __name__ == "__main__":
    unittest.main()

