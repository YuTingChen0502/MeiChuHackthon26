import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from analyzers.separation.diagnostic import SyntheticBandSeparator
from benchmarks.audit_real_audio import audit_pairs
from benchmarks.paired_metrics import summarize
from benchmarks.paired_probe import SeparationPredictor, run_pairs
from benchmarks.readiness_environment import require_exact_source
from benchmarks.tests.cp2_fixtures import make_inputs
from training.asset_readiness import audit_assets
from training.multitrack_assets import sha256_file
from training.pair_plan import build_pair_plan


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.manifest, self.config, self.review, self.mp, self.cp, self.rp) = make_inputs(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.mp.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.cp.write_text(json.dumps(self.config), encoding="utf-8")
        self.review["manifest_sha256"] = sha256_file(self.mp)
        self.rp.write_text(json.dumps(self.review), encoding="utf-8")

    def audit(self):
        return audit_assets(self.mp, self.root, self.rp)

    def plan(self):
        return build_pair_plan(self.mp, self.cp, git_commit="a" * 40)

    def test_review_never_accepts_gate_a_and_reports_four_split_counts(self):
        report = self.audit()
        self.assertEqual("READY_FOR_LEAD_REVIEW", report["status"])
        self.assertFalse(report["gate_a_accepted"])
        self.assertEqual(16, len(report["assets"]))
        self.assertEqual(1, report["split_identity"]["test"]["recordings"])

    def test_pending_training_permission_does_not_erase_evaluation_permission(self):
        self.review["permissions"]["training"] = {"status": "pending", "evidence": None}
        self.review["permissions"]["publication"] = {"status": "denied", "evidence": "test-only"}
        self.save()
        report = self.audit()
        self.assertEqual("READY_FOR_LEAD_REVIEW", report["status"])
        self.assertEqual("pending", report["permissions"]["training"])
        self.assertEqual("denied", report["permissions"]["publication"])

    def test_conflicting_publication_assertions_are_blocked(self):
        self.manifest["provenance"]["allowed_publication_status"] = "private_eval_only"
        self.save()
        self.assertIn("publication_permission_conflicts_with_manifest", self.audit()["blockers"])

    def test_synthetic_and_pending_evaluation_block_real_readiness(self):
        self.review["material_class"] = "synthetic"
        self.review["permissions"]["evaluation"]["status"] = "pending"
        self.save()
        report = self.audit()
        self.assertIn("real_recorded_material_not_supplied", report["blockers"])
        self.assertIn("evaluation_permission_not_allowed", report["blockers"])

    def test_permission_review_cannot_be_reused_for_changed_manifest(self):
        self.manifest["provenance"]["origin"] = "changed"
        self.mp.write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            self.audit()

    def test_renamed_group_cannot_hide_identical_pcm_between_splits(self):
        original = self.manifest["recordings"][0]["stems"][0]
        duplicate = self.manifest["recordings"][1]["stems"][0]
        (self.root / duplicate["relative_path"]).write_bytes(
            (self.root / original["relative_path"]).read_bytes())
        duplicate["sha256"] = original["sha256"]
        self.save()
        report = self.audit()
        self.assertIn("duplicate_non_silent_pcm_across_splits", report["blockers"])

    def test_full_read_catches_truncation_after_valid_header(self):
        stem = self.manifest["recordings"][0]["stems"][0]
        path = self.root / stem["relative_path"]
        path.write_bytes(path.read_bytes()[:-100])
        stem["sha256"] = sha256_file(path)
        self.save()
        with self.assertRaisesRegex(ValueError, "Truncated"):
            self.audit()

    def test_missing_calibration_split_is_explicit(self):
        self.manifest["recordings"] = [
            item for item in self.manifest["recordings"] if item["split"] != "calibration"]
        self.save()
        self.assertIn("missing_grouped_splits:calibration", self.audit()["blockers"])

    def test_pair_audit_checks_arithmetic_and_identical_audio_hashes(self):
        plan = self.plan()
        first = audit_pairs(self.mp, self.root, plan)
        second = audit_pairs(self.mp, self.root, plan)
        self.assertEqual(first, second)
        self.assertEqual("PASS", first["status"])
        self.assertEqual(10, first["pair_count"])

    def test_pair_audit_flags_clipping_without_normalizing_it_away(self):
        self.config["shared_scale"] = 1.0
        self.config["single_source_gain_grid_db"] = [24]
        self.save()
        report = audit_pairs(self.mp, self.root, self.plan())
        self.assertEqual("BLOCKED", report["status"])
        self.assertGreater(report["failed_pairs"], 0)

    def test_probe_passes_only_mixtures_rate_and_configuration(self):
        class RecordingPredictor:
            identity = {"backend": "test-only-all-abstain"}
            def predict(inner, reference, observation, rate, instruments):
                self.assertEqual((800,), reference.shape)
                self.assertEqual((800,), observation.shape)
                self.assertEqual(16000, rate)
                self.assertEqual({"bass", "guitar", "vocals", "drums"}, set(instruments))
                return {key: None for key in instruments}
        result = run_pairs(self.mp, self.root, self.plan(), RecordingPredictor(),
                           {"alert_db": 3, "missing_prediction_penalty_db": 12})
        self.assertFalse(result["calibrated"])
        self.assertEqual(0.0, result["metrics"]["raw_coverage"])
        self.assertEqual(12, result["metrics"]["penalized_raw_mae_db"])
        self.assertEqual(0.0, result["metrics"]["attributed_alert_recall_including_abstentions"])

    def test_separator_and_direct_like_predictor_share_pairs_and_labels(self):
        separator = SeparationPredictor(SyntheticBandSeparator())
        first = run_pairs(self.mp, self.root, self.plan(), separator,
                          {"alert_db": 3, "missing_prediction_penalty_db": 12})
        class EmptyPredictor:
            identity = {"backend": "test-only"}
            def predict(self, reference, observation, rate, instruments):
                return {key: None for key in instruments}
        second = run_pairs(self.mp, self.root, self.plan(), EmptyPredictor(),
                           {"alert_db": 3, "missing_prediction_penalty_db": 12})
        self.assertEqual(
            [r["metadata"] for r in first["pair_records"]],
            [r["metadata"] for r in second["pair_records"]])
        self.assertEqual(
            [r["true_raw_db"] for r in first["rows"]],
            [r["true_raw_db"] for r in second["rows"]])

    def test_nonfinite_predictor_output_fails_loudly(self):
        class BadPredictor:
            identity = {"backend": "invalid"}
            def predict(self, reference, observation, rate, instruments):
                return {key: float("nan") for key in instruments}
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            run_pairs(self.mp, self.root, self.plan(), BadPredictor(),
                      {"alert_db": 3, "missing_prediction_penalty_db": 12})

    def test_source_guard_rejects_dirty_tree_before_launch(self):
        with patch("benchmarks.readiness_environment.source_identity",
                   return_value={"git_commit": "a" * 40, "worktree_clean": False}):
            with self.assertRaisesRegex(ValueError, "clean"):
                require_exact_source("a" * 40, self.cp, sha256_file(self.cp), self.root)

    def test_source_guard_rejects_wrong_sha_and_config_hash(self):
        with patch("benchmarks.readiness_environment.source_identity",
                   return_value={"git_commit": "a" * 40, "worktree_clean": True}):
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                require_exact_source("b" * 40, self.cp, sha256_file(self.cp), self.root)
            with patch("benchmarks.readiness_environment.subprocess.check_call"):
                with self.assertRaisesRegex(ValueError, "config SHA"):
                    require_exact_source("a" * 40, self.cp, "0" * 64, self.root)


class MetricTests(unittest.TestCase):
    def row(self, name, truth, pred):
        return {"pair_id": "pair", "instrument_id": name, "true_raw_db": truth,
                "true_balance_db": truth, "predicted_raw_db": pred,
                "predicted_balance_db": pred}

    def test_wrong_sign_counts_as_false_positive_and_missed_correct_alert(self):
        result = summarize([self.row("guitar", 4, -4)], alert_db=3, missing_penalty_db=12)
        self.assertEqual((0, 1, 1), tuple(result[k] for k in (
            "attributed_alert_tp", "attributed_alert_fp", "attributed_alert_fn")))
        self.assertEqual(0, result["sign_accuracy"])

    def test_inactive_false_alert_is_retained_in_precision_denominator(self):
        result = summarize([self.row("guitar", 4, 4), self.row("bass", None, 6)],
                           alert_db=3, missing_penalty_db=12)
        self.assertEqual(0.5, result["attributed_alert_precision"])
        self.assertEqual(1, result["ineligible_numeric_balance_outputs"])

    def test_raw_coverage_is_distinct_from_balance_coverage(self):
        row = self.row("guitar", 4, 4)
        row["true_balance_db"] = row["predicted_balance_db"] = None
        result = summarize([row], alert_db=3, missing_penalty_db=12)
        self.assertEqual(1, result["raw_coverage"])
        self.assertIsNone(result["balance_coverage"])
        self.assertIsNone(result["eligible_frame_coverage"])

    def test_duplicate_rows_are_not_extra_evidence(self):
        row = self.row("guitar", 4, 4)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            summarize([row, row], alert_db=3, missing_penalty_db=12)

    def test_ambiguous_attribution_is_reported_without_assuming_normal(self):
        row = self.row("guitar", None, 4)
        row["attribution_evaluable"] = False
        result = summarize([row], alert_db=3, missing_penalty_db=12)
        self.assertEqual(1, result["ambiguous_attribution_measurements"])
        self.assertEqual(1, result["ineligible_numeric_balance_outputs"])
        self.assertIsNone(result["attributed_alert_precision"])

    def test_abstentions_have_explicit_penalty_and_no_false_normal(self):
        result = summarize([self.row("guitar", 4, None)], alert_db=3, missing_penalty_db=12)
        self.assertEqual(1, result["balance_abstentions"])
        self.assertEqual(12, result["penalized_balance_mae_db"])
        self.assertIsNone(result["balance_mae_db"])
        self.assertEqual(0, result["attributed_alert_recall_including_abstentions"])


if __name__ == "__main__":
    unittest.main()
