import json
import unittest
from pathlib import Path

import numpy as np

from benchmarks.run_gain_response import DEFAULT_CONFIG, run


class GainResponseBenchmarkTests(unittest.TestCase):
    def test_diagnostic_produces_coverage_and_unconditional_metrics(self):
        config = json.loads(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
        result = run(config, "synthetic_band_masks_v1", ["unit-test"])
        self.assertEqual("completed", result["probe_status"])
        self.assertEqual("synthetic_pipeline_diagnostic_only", result["evidence_class"])
        metrics = result["metrics"]
        self.assertEqual(metrics["eligible_measurements"], metrics["numeric_covered_measurements"])
        self.assertEqual(metrics["eligible_measurements"], metrics["actionable_covered_measurements"])
        self.assertEqual(metrics["actionable_coverage"], metrics["coverage"])
        self.assertIn("unconditional_mae_db", metrics)
        self.assertIn("attributed_anomaly_f1", metrics)
        self.assertEqual({"clean", "white_gaussian@20dB", "white_gaussian@5dB"},
                         set(result["metrics_by_noise"]))
        self.assertEqual(27, len(result["pair_metadata"]))

    def test_pair_metadata_contains_required_ground_truth(self):
        config = json.loads(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
        result = run(config, "synthetic_band_masks_v1", ["unit-test"])
        first = result["pair_metadata"][0]
        for field in (
            "asset_provenance", "split_id", "seed", "source_injected_gain_db",
            "common_gain_input_db", "centered_balance_db", "valid_source_mask", "noise",
        ):
            self.assertIn(field, first)

    def test_manifested_input_provenance_replaces_synthetic_identity(self):
        config = json.loads(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
        config["gain_grid_db"] = [0]
        config["noise_conditions"] = [{"kind": "none", "snr_db": None}]
        count = int(config["sample_rate_hz"] * config["duration_s"])
        time = np.arange(count, dtype=np.float64) / config["sample_rate_hz"]
        frequencies = {"bass": 100, "guitar": 500, "vocals": 1800, "drums": 5000}
        stems = {
            name: 0.1 * np.sin(2 * np.pi * frequency * time)
            for name, frequency in frequencies.items()
        }
        result = run(
            config,
            "synthetic_band_masks_v1",
            ["unit-test-manifested"],
            input_stems=stems,
            input_provenance={
                "dataset_id": "manifested-test-v1",
                "recording_id": "recording-1",
                "license_or_permission": "unit-test generated",
            },
            input_split_identity={
                "split_id": "manifested-test-v1:test",
                "dataset_id": "manifested-test-v1",
                "recording_id": "recording-1",
                "parent_group_id": "song-1",
                "split": "test",
                "all_augmentations_grouped": True,
            },
        )
        self.assertEqual("manifested_multitrack", result["asset_mode"])
        self.assertEqual("manifested_multitrack_probe", result["evidence_class"])
        self.assertEqual(
            "recording-1", result["metadata"]["asset_provenance"][0]["recording_id"]
        )
        self.assertEqual(
            "manifested-test-v1:test", result["pair_metadata"][0]["split_id"]
        )


if __name__ == "__main__":
    unittest.main()
