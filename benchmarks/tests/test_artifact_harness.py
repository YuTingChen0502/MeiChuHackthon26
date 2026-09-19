import copy
import tempfile
import unittest
from pathlib import Path

from analyzers.bundles import BackendRegistry
from analyzers.tests.bundle_fixtures import MODEL, TestBackend, config, context, registry, window, write_bundle
from benchmarks.compare_artifacts import compare
from benchmarks.evaluate_artifact import evaluate
from benchmarks.export_parity import compare_outputs, export_artifact
from training.prepare_calibration_rows import prepare_rows


class ArtifactHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.m = write_bundle(self.bundle)
        self.cases = [{
            "case_id": "unit-only", "split": "test", "parent_group_id": "test-parent",
            "reference_windows": [window("reference")], "observation": window(),
            "instrument_config": config(), "target": context()["target"],
            "comparison_regime": "matched_excerpt",
            "labels": {x: {"raw_source_delta_db": 0, "balance_deviation_db": 0,
                           "attribution_evaluable": True} for x in ("guitar", "bass", "drums")},
        }]
        self.provenance = {
            "git_sha": "a"*40, "config_sha256": "c"*64,
            "dataset_manifest_sha256": self.m["dataset"]["manifest_sha256"],
            "split_groups": self.m["dataset"]["split_groups"], "material_class": "synthetic",
            "example_only": True, "seed": 1, "gain_intervention": {}, "noise_type": "none",
            "snr_db": None, "augmentation": [], "label_procedure": "unit-test-only",
            "environment": {"runtime": "unit-test"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def report(self):
        return evaluate(self.bundle, registry=registry(), cases=self.cases,
                        provenance=self.provenance,
                        thresholds={"alert_db": 3, "missing_prediction_penalty_db": 6})

    def test_evaluation_records_identity_pcm_hashes_and_denominators(self):
        report = self.report()
        self.assertEqual(MODEL, report["model"])
        self.assertEqual(3, report["metrics"]["eligible_count"])
        self.assertEqual(64, len(report["outputs"][0]["pcm_sha256"]))
        self.assertTrue(report["example_only"])
        self.assertEqual("unit-test-only", report["experiment"]["label_procedure"])

    def test_missing_provenance_and_wrong_split_rejected(self):
        del self.provenance["label_procedure"]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.report()
        self.provenance["label_procedure"] = "fixture"
        self.cases[0]["parent_group_id"] = "train-parent"
        with self.assertRaisesRegex(ValueError, "wrong grouped split"):
            self.report()

    def test_parity_detects_numerical_drift_and_population_mismatch(self):
        reference = self.report()
        changed = copy.deepcopy(reference)
        self.assertTrue(compare_outputs(reference, changed, atol_db=0)["metrics"]["passed"])
        changed["outputs"][0]["evidence"]["measurements"][0]["source_level_delta_db"] = 1
        self.assertFalse(compare_outputs(reference, changed, atol_db=0.01)["metrics"]["passed"])
        changed["outputs"][0]["pcm_sha256"] = "f"*64
        with self.assertRaisesRegex(ValueError, "inputs differ"):
            compare_outputs(reference, changed, atol_db=0)

    def test_parity_cannot_upgrade_synthetic_provenance(self):
        reference = self.report()
        changed = copy.deepcopy(reference)
        changed["material_class"] = "real_recorded"
        with self.assertRaisesRegex(ValueError, "populations"):
            compare_outputs(reference, changed, atol_db=0)

    def test_comparison_requires_matching_labels_and_never_selects_winner(self):
        a = self.report()
        b = copy.deepcopy(a)
        b["model"]["model_bundle_id"] = "second-test-model"
        result = compare([a, b])
        self.assertEqual("NOT_SELECTED", result["decision"])
        b["rows"][0]["true_balance_db"] = 4
        with self.assertRaisesRegex(ValueError, "labels"):
            compare([a, b])

    def test_calibration_bridge_keeps_all_explicit_labels_and_raw_scores(self):
        report = self.report()
        event = "joint_anomaly_numeric_correct"
        labels = [{"pair_id": "unit-only", "instrument_id": instrument, "probability_event": event,
                   "eligible": True, "attribution_correct": True, "target_within_normal_envelope": True}
                  for instrument in ("guitar", "bass", "drums")]
        settings = {"operating_envelope_id": "unit-only", "label_procedure": "explicit test truth",
                    "score_features": {event: {"name": "raw_score", "unit": "score"}}}
        rows = prepare_rows(report, labels, settings)
        self.assertEqual(3, len(rows["rows"]))
        self.assertEqual(0.8, rows["rows"][0]["score"])
        self.assertTrue(rows["example_only"])
        with self.assertRaisesRegex(ValueError, "full measured population"):
            prepare_rows(report, labels[:-1], settings)

    def test_export_only_publishes_selected_file_and_unaccepted_receipt(self):
        r = BackendRegistry()
        def exporter(backend, stage):
            (stage / "unused-cache.bin").write_bytes(b"do-not-copy")
            artifact = stage / "runtime.bin"
            artifact.write_bytes(b"unit-test-export-not-model")
            return artifact
        r.register("test-only-adapter", lambda b: TestBackend(b, {}), exporter=exporter)
        receipt = export_artifact(self.bundle, registry=r, destination=self.root / "export")
        self.assertFalse(receipt["parity_accepted"])
        self.assertEqual({"runtime.bin", "export-receipt.json"},
                         {p.name for p in (self.root / "export").iterdir()})
        self.assertEqual([], list(self.root.glob(".export-*")))
        with self.assertRaisesRegex(ValueError, "overwrite"):
            export_artifact(self.bundle, registry=r, destination=self.root / "export")

    def test_exporter_cannot_publish_outside_staging(self):
        r = BackendRegistry()
        r.register("test-only-adapter", lambda b: TestBackend(b, {}),
                   exporter=lambda b, p: self.root / "outside.bin")
        with self.assertRaisesRegex(ValueError, "inside staging"):
            export_artifact(self.bundle, registry=r, destination=self.root / "export")
        self.assertFalse((self.root / "export").exists())
        self.assertEqual([], list(self.root.glob(".export-*")))


if __name__ == "__main__":
    unittest.main()
