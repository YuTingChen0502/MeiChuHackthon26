"""Audit supplied assets and materialize a fixed validation plan without a model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from benchmarks.readiness_environment import source_identity
from training.asset_readiness import audit_assets
from training.experiment_metadata import current_git_commit, environment_record
from training.multitrack_assets import sha256_file
from training.pair_plan import build_pair_plan, materialize_planned_pair

REPO_ROOT = Path(__file__).resolve().parents[1]


def audit_pairs(manifest_path: Path, dataset_root: Path, plan: dict) -> dict:
    rows = []
    for entry in plan["pairs"]:
        pair = materialize_planned_pair(manifest_path, dataset_root, plan, entry)
        errors = []
        measured = {}
        for instrument_id, valid in pair.labels.valid_source_mask.items():
            ref = pair.reference_stems[instrument_id]
            obs = pair.observation_stems[instrument_id]
            if valid:
                delta = float(10 * np.log10(np.mean(obs ** 2) / np.mean(ref ** 2)))
                measured[instrument_id] = delta
                if not np.isclose(delta, pair.labels.raw_source_delta_db[instrument_id], atol=1e-9):
                    errors.append(f"oracle_mismatch:{instrument_id}")
            else:
                measured[instrument_id] = None
        peak = max(float(np.max(np.abs(pair.reference_mix))),
                   float(np.max(np.abs(pair.observation_mix))))
        if not np.isfinite(peak) or peak >= 1.0:
            errors.append("nonfinite_or_clipping_mixture")
        rows.append({
            "pair_id": entry["pair_id"], "split": entry["split"],
            "parent_group_id": entry["parent_group_id"],
            "scenario_kind": entry["scenario_kind"],
            "metadata": pair.metadata, "measured_raw_delta_db": measured,
            "peak": peak, "errors": errors,
        })
    return {
        "status": "PASS" if all(not row["errors"] for row in rows) else "BLOCKED",
        "pair_count": len(rows), "failed_pairs": sum(bool(row["errors"]) for row in rows),
        "claim": "pair arithmetic and input readiness only; no perception evidence",
        "rows": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--use-review", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    # Readiness runs must not consume reserved calibration/final-test excerpts.
    if set(config["splits"]) - {"train", "validation"}:
        raise ValueError("Readiness pair audit is restricted to train/validation")
    assets = audit_assets(args.manifest, args.dataset_root, args.use_review)
    report = {
        "record_type": "CP2InputAudit", "schema_version": "1.0",
        "git_commit": current_git_commit(REPO_ROOT),
        "environment": environment_record(), "source": source_identity(),
        "config_sha256": sha256_file(args.config),
        "assets": assets, "pair_audit": None,
    }
    if assets["status"] == "READY_FOR_LEAD_REVIEW":
        plan = build_pair_plan(args.manifest, args.config, git_commit=report["git_commit"])
        report["pair_plan"] = plan
        report["pair_audit"] = audit_pairs(args.manifest, args.dataset_root, plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if report["pair_audit"] and report["pair_audit"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
