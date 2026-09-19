import copy
import unittest

from analyzers.calibration_metadata import lookup_bin, validate_calibration
from analyzers.tests.bundle_fixtures import MODEL, GROUPS
from training.calibration import evaluate_candidate, fit_candidate


def fixture(split="calibration"):
    feature = {"name": "raw_score", "unit": "score"}
    event = "joint_anomaly_numeric_correct"
    document = {
        "record_type": "CalibrationRows", "schema_version": "1.0", "model": MODEL,
        "runtime_artifact_sha256": "b" * 64, "git_sha": "a" * 40,
        "dataset_manifest_sha256": "d" * 64, "split_groups": GROUPS,
        "material_class": "synthetic", "example_only": True, "operating_envelope_id": "test-only",
        "label_procedure": "unit-test labels only", "score_features": {event: feature},
        "rows": [
            {"sample_id": str(i), "split": split, "parent_group_id": GROUPS[split][0],
             "probability_event": event, "eligible": True, "attribution_correct": True,
             "target_within_normal_envelope": False, "target_balance_db": 3,
             "predicted_balance_db": pred, "score": score}
            for i, (pred, score) in enumerate(((3, 0.2), (-3, 0.3), (2, 0.8), (3, 0.9)))
        ],
    }
    config = {"magnitude_tolerance_db": 2, "interval_mass": 0.9,
              "mappings": {event: {"score_feature": feature, "score_edges": [0, 0.5, 1]}}}
    return document, config


class CalibrationEntrypointTests(unittest.TestCase):
    def fit(self, document=None, config=None):
        d, c = fixture()
        return fit_candidate(document or d, config or c, rows_sha256="e"*64, config_sha256="f"*64)

    def test_fit_is_unaccepted_candidate_with_measured_bins(self):
        candidate = self.fit()
        mapping = candidate["mappings"]["joint_anomaly_numeric_correct"]
        self.assertEqual([0.5, 1.0], [b["probability"] for b in mapping["bins"]])
        self.assertTrue(candidate["example_only"])
        self.assertEqual("candidate", candidate["status"])
        self.assertEqual(4, candidate["metrics"]["fitted_count"])
        self.assertEqual(1.0, lookup_bin(mapping, 1)["probability"])
        self.assertIsNone(lookup_bin(mapping, 1.01))
        self.assertIsNone(lookup_bin(mapping, float("nan")))

    def test_heldout_evaluation_and_missing_event_abstention(self):
        d, _ = fixture("test")
        candidate = self.fit()
        d["rows"][0]["probability_event"] = "normal_within_envelope"
        result = evaluate_candidate(candidate, d)
        self.assertEqual(3, result["metrics"]["evaluated_count"])
        self.assertEqual(0.75, result["metrics"]["coverage"])

    def test_fitting_cannot_use_test_or_overlapping_groups(self):
        d, c = fixture("test")
        with self.assertRaisesRegex(ValueError, "wrong split"):
            self.fit(d, c)
        d, c = fixture()
        d["split_groups"] = copy.deepcopy(GROUPS)
        d["split_groups"]["test"] = GROUPS["calibration"]
        with self.assertRaisesRegex(ValueError, "leakage"):
            self.fit(d, c)

    def test_unsupported_rows_do_not_fabricate_calibration(self):
        d, c = fixture()
        for row in d["rows"]:
            row["eligible"] = False
        with self.assertRaisesRegex(ValueError, "No supported"):
            self.fit(d, c)

    def test_score_identity_and_material_drift_rejected(self):
        d, c = fixture()
        c = copy.deepcopy(c)
        c["mappings"]["joint_anomaly_numeric_correct"]["score_feature"]["unit"] = "different"
        with self.assertRaisesRegex(ValueError, "score name"):
            self.fit(d, c)
        d, _ = fixture("test")
        d["material_class"] = "real_recorded"
        with self.assertRaisesRegex(ValueError, "material"):
            evaluate_candidate(self.fit(), d)

    def test_overlapping_bins_rejected(self):
        candidate = self.fit()
        candidate["mappings"]["joint_anomaly_numeric_correct"]["bins"][1]["lower"] = 0.4
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            validate_calibration(candidate, model=MODEL, artifact_sha256="b"*64)


if __name__ == "__main__":
    unittest.main()
