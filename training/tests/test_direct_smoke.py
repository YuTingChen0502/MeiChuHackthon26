import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None


@unittest.skipUnless(TORCH_AVAILABLE, "optional torch dependency is unavailable")
class DirectTrainingSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch

        from analyzers.direct.torch_head import (
            DirectObjectiveWeights,
            DirectPairFusionHead,
            direct_multitask_loss,
        )
        from training.direct_smoke import run_smoke

        cls.torch = torch
        cls.DirectObjectiveWeights = DirectObjectiveWeights
        cls.DirectPairFusionHead = DirectPairFusionHead
        cls.direct_multitask_loss = staticmethod(direct_multitask_loss)
        cls.run_smoke = staticmethod(run_smoke)

    def test_invalid_nan_label_is_fully_masked(self):
        torch = self.torch
        head = self.DirectPairFusionHead(
            embedding_dim=3, scale_feature_dim=2, source_count=2, hidden_dim=4
        )
        outputs = head(torch.ones(2, 3), torch.ones(2, 3), torch.ones(2, 2))
        targets = torch.tensor([[1.0, float("nan")], [0.0, 2.0]])
        mask = torch.tensor([[True, False], [True, True]])
        losses = self.direct_multitask_loss(
            outputs,
            raw_source_delta_db=targets,
            valid_source_mask=mask,
            activity_target=mask.float(),
            event_target=torch.zeros(2, 2),
            common_gain_db=torch.zeros(2),
            common_gain_valid_mask=torch.ones(2, dtype=torch.bool),
            pair_valid_mask=torch.ones(2, dtype=torch.bool),
            weights=self.DirectObjectiveWeights(),
        )
        self.assertTrue(torch.isfinite(losses["total"]))
        losses["total"].backward()
        self.assertTrue(any(parameter.grad is not None for parameter in head.parameters()))

    def test_cpu_smoke_records_gradient_and_weight_change(self):
        source = Path(__file__).parents[1] / "configs" / "direct_training_smoke_v1.json"
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config = json.loads(source.read_text(encoding="utf-8"))
            config["optimizer_steps"] = 3
            config_path.write_text(json.dumps(config), encoding="utf-8")
            report = self.run_smoke(config_path, requested_device="cpu")
        self.assertEqual("pass", report["status"])
        audit = report["optimizer_audit"]
        self.assertGreater(audit["nonzero_gradient_parameter_count"], 0)
        self.assertEqual(audit["trainable_parameter_count"], audit["changed_parameter_count"])
        self.assertLess(audit["final_loss"], audit["initial_loss"])
        self.assertNotEqual(
            report["model_checkpoint"]["before_sha256"],
            report["model_checkpoint"]["after_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
