import json
import unittest
from pathlib import Path

from benchmarks.run_gain_response import DEFAULT_CONFIG, run


class GainResponseBenchmarkTests(unittest.TestCase):
    def test_diagnostic_produces_coverage_and_unconditional_metrics(self):
        config = json.loads(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
        result = run(config, "synthetic_band_masks_v1", ["unit-test"])
        self.assertEqual("completed", result["probe_status"])
        self.assertEqual("synthetic_pipeline_diagnostic_only", result["evidence_class"])
        metrics = result["metrics"]
        self.assertEqual(metrics["eligible_measurements"], metrics["covered_measurements"])
        self.assertIn("unconditional_mae_db", metrics)
        self.assertIn("attributed_anomaly_f1", metrics)
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


if __name__ == "__main__":
    unittest.main()
