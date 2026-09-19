import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analyzers.separation.diagnostic import SyntheticBandSeparator
from benchmarks.compare_paired_probes import compare
from benchmarks.paired_probe import ScriptedDirectPredictor, SeparationPredictor, run_pairs
from benchmarks.tests.cp2_fixtures import make_inputs
from training.multitrack_assets import sha256_file
from training.pair_plan import build_pair_plan


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _, _, _, mp, cp, _ = make_inputs(self.root)
        plan = build_pair_plan(mp, cp, git_commit="a" * 40)
        self.report = run_pairs(mp, self.root, plan, SeparationPredictor(SyntheticBandSeparator()),
                                {"alert_db": 3, "missing_prediction_penalty_db": 12})
        self.report["git_commit"] = "a" * 40

    def tearDown(self):
        self.tmp.cleanup()

    def test_matched_report_requires_lead_decision(self):
        result = compare(self.report, copy.deepcopy(self.report))
        self.assertEqual("AWAITING_LEAD_DECISION", result["status"])

    def test_changed_pcm_and_missing_rows_cannot_be_compared(self):
        changed = copy.deepcopy(self.report)
        changed["pair_records"][0]["metadata"]["reference_mix_sha256_f64le"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Actual PCM"):
            compare(self.report, changed)
        changed = copy.deepcopy(self.report)
        changed["rows"].pop()
        with self.assertRaisesRegex(ValueError, "populations"):
            compare(self.report, changed)

    def test_identically_missing_rows_are_still_rejected(self):
        changed = copy.deepcopy(self.report)
        changed["rows"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            compare(changed, copy.deepcopy(changed))

    def test_changed_config_or_thresholds_are_not_matched_evidence(self):
        changed = copy.deepcopy(self.report)
        changed["plan"]["config_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Pair plans"):
            compare(self.report, changed)
        changed = copy.deepcopy(self.report)
        changed["thresholds"]["alert_db"] = 4
        with self.assertRaisesRegex(ValueError, "thresholds"):
            compare(self.report, changed)


@unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch unavailable")
class DirectArtifactTests(unittest.TestCase):
    def setUp(self):
        import torch
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "test-only.pt"
        self.manifest = self.root / "model.json"
        class TestOnlyPairedModule(torch.nn.Module):
            def forward(self, reference, observation):
                delta = observation.mean(dim=1, keepdim=True) - reference.mean(dim=1, keepdim=True)
                return delta, torch.ones_like(delta, dtype=torch.bool)
        model = torch.jit.trace(TestOnlyPairedModule(), (torch.ones(1, 80), torch.ones(1, 80)))
        model.save(str(self.artifact))
        self.identity = {
            "artifact_sha256": sha256_file(self.artifact), "model_id": "test-only-no-pretraining",
            "frontend_id": "test-only-mean", "pretrained_checkpoint_sha256": "a" * 64,
            "training_git_sha": "b" * 40, "families": ["guitar"], "sample_rate_hz": 16000,
        }
        self.manifest.write_text(json.dumps(self.identity), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_exported_pair_signature_runs_on_cpu_and_abstains_for_unsupported_family(self):
        predictor = ScriptedDirectPredictor(self.artifact, self.manifest)
        output = predictor.predict(np.zeros(80), np.ones(80), 16000,
                                   {"guitar": "guitar", "bass": "bass"})
        self.assertAlmostEqual(1, output["guitar"])
        self.assertIsNone(output["bass"])

    def test_artifact_hash_and_rate_mismatch_are_rejected(self):
        predictor = ScriptedDirectPredictor(self.artifact, self.manifest)
        with self.assertRaisesRegex(ValueError, "sample rate"):
            predictor.predict(np.zeros(80), np.ones(80), 8000, {"guitar": "guitar"})
        self.identity["artifact_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(self.identity), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            ScriptedDirectPredictor(self.artifact, self.manifest)


if __name__ == "__main__":
    unittest.main()
