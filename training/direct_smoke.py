"""Finite forward/backward/optimizer smoke for the direct-estimator task head."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import torch

from analyzers.direct.torch_head import (
    DirectObjectiveWeights,
    DirectPairFusionHead,
    direct_multitask_loss,
)
from training.experiment_metadata import current_git_commit, environment_record
from training.multitrack_assets import sha256_file


REPO_ROOT = Path(__file__).resolve().parents[1]


def _state_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA/ROCm torch device requested but unavailable")
    return device


def run_smoke(config_path: Path, *, requested_device: str) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "1.0":
        raise ValueError("Unsupported direct-smoke config schema_version")
    seed = int(config["seed"])
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(bool(config["deterministic_algorithms"]))
    device = _device(requested_device)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    batch_size = int(config["batch_size"])
    embedding_dim = int(config["embedding_dim"])
    scale_feature_dim = int(config["scale_feature_dim"])
    source_count = int(config["source_count"])
    generator = torch.Generator(device="cpu").manual_seed(seed)
    reference = torch.randn(batch_size, embedding_dim, generator=generator).to(device)
    observation = (reference.cpu() + 0.15 * torch.randn(
        batch_size, embedding_dim, generator=generator
    )).to(device)
    scale = torch.randn(batch_size, scale_feature_dim, generator=generator).to(device)

    source_injection = torch.randn(
        batch_size, source_count, generator=generator
    ).to(device) * 2.0
    common = torch.randn(batch_size, generator=generator).to(device)
    consistency_pairs = torch.tensor(config["consistency_pairs"], device=device)
    for left, right in consistency_pairs.tolist():
        source_injection[right] = source_injection[left]
        common[left] = 0.0
        common[right] = 3.0
    raw_delta = source_injection + common.unsqueeze(1)
    valid = torch.ones(batch_size, source_count, dtype=torch.bool, device=device)
    valid[0, -1] = False
    raw_delta[0, -1] = float("nan")
    activity = valid.to(torch.float32)
    event = (source_injection.abs() >= 1.0).to(torch.float32)
    common = torch.stack([
        torch.median(raw_delta[index][valid[index]]) for index in range(batch_size)
    ])
    common_valid = torch.ones(batch_size, dtype=torch.bool, device=device)
    pair_valid = torch.ones(batch_size, dtype=torch.bool, device=device)

    model = DirectPairFusionHead(
        embedding_dim=embedding_dim,
        scale_feature_dim=scale_feature_dim,
        source_count=source_count,
        hidden_dim=int(config["hidden_dim"]),
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    weights = DirectObjectiveWeights(**config["loss_weights"])
    before_hash = _state_hash(model)
    before_parameters = {
        name: value.detach().cpu().clone() for name, value in model.named_parameters()
    }
    started = time.perf_counter()
    losses: list[float] = []
    nonzero_gradient_parameters: list[str] = []
    for step in range(int(config["optimizer_steps"])):
        optimizer.zero_grad(set_to_none=True)
        outputs = model(reference, observation, scale)
        breakdown = direct_multitask_loss(
            outputs,
            raw_source_delta_db=raw_delta,
            valid_source_mask=valid,
            activity_target=activity,
            event_target=event,
            common_gain_db=common,
            common_gain_valid_mask=common_valid,
            pair_valid_mask=pair_valid,
            consistency_pairs=consistency_pairs,
            weights=weights,
        )
        loss = breakdown["total"]
        if not torch.isfinite(loss):
            raise RuntimeError("Direct smoke produced a non-finite loss")
        losses.append(float(loss.detach().cpu()))
        loss.backward()
        if step == 0:
            nonzero_gradient_parameters = sorted(
                name for name, value in model.named_parameters()
                if value.grad is not None and bool(torch.any(value.grad != 0).item())
            )
        optimizer.step()
    elapsed = time.perf_counter() - started
    after_hash = _state_hash(model)
    changed_parameters = sorted(
        name for name, value in model.named_parameters()
        if not torch.equal(before_parameters[name], value.detach().cpu())
    )
    if not nonzero_gradient_parameters:
        raise RuntimeError("No direct-head parameter received a non-zero gradient")
    if not changed_parameters or before_hash == after_hash:
        raise RuntimeError("Optimizer smoke did not change direct-head weights")
    if losses[-1] >= losses[0]:
        raise RuntimeError("Finite smoke loss did not decrease")

    device_name = platform.processor() or platform.machine()
    if device.type == "cuda":
        device_name = torch.cuda.get_device_name(device)
    return {
        "record_type": "DirectTrainingSmoke",
        "schema_version": "1.0",
        "status": "pass",
        "claim_scope": "training_mechanics_only_no_audio_feasibility_claim",
        "git_commit": current_git_commit(REPO_ROOT),
        "config": config,
        "config_sha256": sha256_file(config_path),
        "seed": seed,
        "model_checkpoint": {
            "encoder": "synthetic_features_no_encoder_loaded",
            "head_initialization": "seeded_random_smoke_only",
            "before_sha256": before_hash,
            "after_sha256": after_hash,
        },
        "environment": {
            **environment_record(),
            "torch_version": torch.__version__,
            "torch_hip_version": torch.version.hip,
            "torch_cuda_version": torch.version.cuda,
            "requested_device": requested_device,
            "resolved_device": str(device),
            "device_name": device_name,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        },
        "optimizer_audit": {
            "optimizer": "AdamW",
            "steps": int(config["optimizer_steps"]),
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "loss_history": losses,
            "nonzero_gradient_parameter_count": len(nonzero_gradient_parameters),
            "trainable_parameter_count": sum(1 for _ in model.parameters()),
            "changed_parameter_count": len(changed_parameters),
            "nonzero_gradient_parameters": nonzero_gradient_parameters,
            "changed_parameters": changed_parameters,
            "elapsed_s": elapsed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_smoke(args.config, requested_device=args.device)
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
