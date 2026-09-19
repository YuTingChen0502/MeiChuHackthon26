"""One fixed-pair evaluation path for separation and exported direct candidates.

Only mixtures, sample rate and configured instrument taxonomy enter predict().
Oracle labels and file/seed/noise identities stay in this offline harness.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median

import numpy as np

from analyzers.separation.htdemucs import HTDemucs6sSeparator
from analyzers.separation.levels import gain_response
from benchmarks.paired_metrics import summarize
from benchmarks.readiness_environment import source_identity
from training.asset_readiness import audit_assets
from training.experiment_metadata import current_git_commit, environment_record
from training.multitrack_assets import sha256_file
from training.pair_plan import build_pair_plan, materialize_planned_pair

REPO_ROOT = Path(__file__).resolve().parents[1]


class SeparationPredictor:
    def __init__(self, separator, floor_dbfs=-70.0):
        self.separator = separator
        self.floor_dbfs = floor_dbfs
        self.identity = {
            "backend": separator.backend_id, "checkpoint": separator.checkpoint_id,
            "artifact": getattr(separator, "checkpoint_artifact", None),
            "execution": getattr(separator, "execution_settings", {}),
        }

    def predict(self, reference, observation, sample_rate, instruments):
        families = list(instruments.values())
        if len(families) != len(set(families)):
            raise ValueError("Multiple IDs for one family require an explicitly grouped input")
        ref = self.separator.separate(reference, sample_rate)
        obs = self.separator.separate(observation, sample_rate)
        response = gain_response(ref.sources, obs.sources, configured_sources=families,
                                 activity_floor_dbfs=self.floor_dbfs)
        return {key: response.raw_source_delta_db[family] for key, family in instruments.items()}


class ScriptedDirectPredictor:
    """CPU probe for a locally supplied, hashed TorchScript paired-audio candidate.

    The artifact includes its exact audio frontend and outputs (raw_source_deltas,
    valid_mask), both [1, family_count]. This is an offline adapter, not RealAnalyzer.
    No checkpoint is downloaded and a model output is never promoted to confidence.
    """
    def __init__(self, artifact_path: Path, manifest_path: Path):
        import torch
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("artifact_sha256") != sha256_file(artifact_path):
            raise ValueError("Direct artifact SHA-256 mismatch")
        for key in ("model_id", "frontend_id", "pretrained_checkpoint_sha256",
                    "training_git_sha", "families", "sample_rate_hz"):
            if not manifest.get(key):
                raise ValueError(f"Direct artifact lacks {key}")
        for key, length in (("pretrained_checkpoint_sha256", 64), ("training_git_sha", 40)):
            value = manifest[key]
            if not isinstance(value, str) or len(value) != length or any(
                    c not in "0123456789abcdef" for c in value):
                raise ValueError(f"Invalid direct artifact identity: {key}")
        if (not isinstance(manifest["sample_rate_hz"], int)
                or isinstance(manifest["sample_rate_hz"], bool)
                or manifest["sample_rate_hz"] <= 0):
            raise ValueError("Invalid direct sample rate")
        self.families = manifest["families"]
        if (not isinstance(self.families, list)
                or not all(isinstance(x, str) and x for x in self.families)
                or len(set(self.families)) != len(self.families)):
            raise ValueError("Direct families must be distinct strings")
        self.rate = manifest["sample_rate_hz"]
        self.torch = torch
        self.model = torch.jit.load(str(artifact_path), map_location="cpu").eval()
        self.identity = {"backend": "direct_torchscript_cpu", "manifest": manifest,
                         "manifest_sha256": sha256_file(manifest_path),
                         "torch_version": torch.__version__}

    def predict(self, reference, observation, sample_rate, instruments):
        if len(set(instruments.values())) != len(instruments):
            raise ValueError("Multiple IDs for one family require an explicitly grouped input")
        if sample_rate != self.rate:
            raise ValueError("Direct artifact requires its declared sample rate")
        torch = self.torch
        with torch.inference_mode():
            values, valid = self.model(
                torch.from_numpy(reference.astype(np.float32)).unsqueeze(0),
                torch.from_numpy(observation.astype(np.float32)).unsqueeze(0))
        if values.shape != (1, len(self.families)) or valid.shape != values.shape:
            raise ValueError("Direct candidate output shape mismatch")
        if valid.dtype != torch.bool:
            raise ValueError("Direct validity output must be boolean, not a confidence score")
        outputs = {}
        for key, family in instruments.items():
            if family not in self.families:
                outputs[key] = None
            else:
                index = self.families.index(family)
                outputs[key] = float(values[0, index]) if bool(valid[0, index]) else None
        return outputs


def run_pairs(manifest_path, dataset_root, plan, predictor, thresholds):
    alert = float(thresholds["alert_db"])
    penalty = float(thresholds["missing_prediction_penalty_db"])
    # Validate metric parameters even when no usable predictions exist.
    summarize([], alert_db=alert, missing_penalty_db=penalty)
    rows, pair_records, latencies = [], [], []
    for entry in plan["pairs"]:
        pair = materialize_planned_pair(manifest_path, dataset_root, plan, entry)
        started = time.perf_counter()
        clipped = any(np.max(np.abs(x)) >= 1.0
                      for x in (pair.reference_mix, pair.observation_mix))
        if clipped:
            predicted = {key: None for key in entry["instrument_families"]}
        else:
            predicted = predictor.predict(
                pair.reference_mix.copy(), pair.observation_mix.copy(),
                entry["sample_rate_hz"], dict(entry["instrument_families"]))
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        if set(predicted) != set(entry["instrument_families"]):
            raise ValueError("Predictor must return every configured instrument exactly once")
        if any(value is not None and not np.isfinite(value) for value in predicted.values()):
            raise ValueError("Predictor returned nonfinite numerical evidence")
        numeric = [float(x) for x in predicted.values() if x is not None]
        center = float(median(numeric)) if len(numeric) >= 3 else None
        # Truth eligibility is separate from predicted validity.
        # Majority-unchanged origin is required for attributed balance evaluation.
        active = [key for key, value in pair.labels.valid_source_mask.items() if value]
        changed = sum(pair.labels.source_injected_gain_db[key] != 0 for key in active)
        identifiable = len(active) >= 3 and changed * 2 < len(active)
        for key in entry["instrument_families"]:
            raw = predicted[key]
            rows.append({
                "pair_id": entry["pair_id"], "instrument_id": key,
                "family": entry["instrument_families"][key],
                "scenario_kind": entry["scenario_kind"], "noise": entry["noise"],
                "true_raw_db": pair.labels.raw_source_delta_db[key],
                "true_balance_db": pair.labels.centered_balance_db[key] if identifiable else None,
                "oracle_centered_db": pair.labels.centered_balance_db[key],
                "attribution_evaluable": identifiable or not pair.labels.valid_source_mask[key],
                "predicted_raw_db": raw,
                "predicted_balance_db": raw - center if raw is not None and center is not None else None,
                "reason": "clipping" if clipped else "measurement_unavailable" if raw is None
                          else "insufficient_predicted_sources" if center is None else None,
            })
        pair_records.append({
            "pair_id": entry["pair_id"], "parent_group_id": entry["parent_group_id"],
            "split": entry["split"], "metadata": pair.metadata,
            "prediction_seconds": elapsed, "predicted_common_mode_db": center,
            "oracle_balance_identifiable": identifiable,
        })
    group_keys = sorted({json.dumps((r["scenario_kind"], r["noise"]), sort_keys=True) for r in rows})
    return {
        "status": "COMPLETED_DIAGNOSTIC", "calibrated": False,
        "model": predictor.identity, "thresholds": thresholds, "plan": plan,
        "metrics": summarize(rows, alert_db=alert, missing_penalty_db=penalty),
        "metrics_by_condition": {
            key: summarize([r for r in rows if json.dumps(
                (r["scenario_kind"], r["noise"]), sort_keys=True) == key],
                alert_db=alert, missing_penalty_db=penalty) for key in group_keys
        },
        "metrics_by_instrument": {
            key: summarize([r for r in rows if r["instrument_id"] == key],
                           alert_db=alert, missing_penalty_db=penalty)
            for key in sorted({r["instrument_id"] for r in rows})
        },
        "prediction_seconds_p50": float(np.median(latencies)) if latencies else None,
        "prediction_seconds_p95": float(np.percentile(latencies, 95)) if latencies else None,
        "pair_records": pair_records, "rows": rows,
        "limitations": [
            "Offline matched-excerpt diagnostics; no runtime confidence or action enablement.",
            "Full Gate B also needs real noise, unsupported/path-mismatch controls and continuous events.",
            "No musical feasibility claim follows from synthetic test execution.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    for name in ("manifest", "dataset-root", "use-review", "config", "thresholds", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--backend", choices=("htdemucs_6s", "direct"), required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--direct-artifact", type=Path)
    parser.add_argument("--direct-manifest", type=Path)
    args = parser.parse_args(argv)
    source = source_identity()
    if not source["worktree_clean"]:
        raise ValueError("Empirical probe requires a committed clean source worktree")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config["splits"] != ["validation"]:
        raise ValueError("Feasibility probing is validation-only; preserve calibration/final test")
    readiness = audit_assets(args.manifest, args.dataset_root, args.use_review)
    if readiness["status"] != "READY_FOR_LEAD_REVIEW":
        raise ValueError(f"Asset readiness blocked: {readiness['blockers']}")
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    if args.backend == "direct":
        if args.device != "cpu" or not args.direct_artifact or not args.direct_manifest:
            raise ValueError("Direct probe requires CPU and explicit local artifact/manifest")
        predictor = ScriptedDirectPredictor(args.direct_artifact, args.direct_manifest)
    else:
        predictor = SeparationPredictor(
            HTDemucs6sSeparator(device=args.device),
            floor_dbfs=float(thresholds["activity_floor_dbfs"]))
    commit = current_git_commit(REPO_ROOT)
    plan = build_pair_plan(args.manifest, args.config, git_commit=commit)
    report = run_pairs(args.manifest, args.dataset_root, plan, predictor, thresholds)
    report.update(git_commit=commit, source=source, environment=environment_record(),
                  asset_readiness=readiness, thresholds_sha256=sha256_file(args.thresholds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
