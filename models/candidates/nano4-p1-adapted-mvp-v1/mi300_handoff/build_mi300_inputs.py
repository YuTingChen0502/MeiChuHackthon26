#!/usr/bin/env python3
"""Materialize the frozen MI300 training metadata from already-prepared assets."""

import argparse
import hashlib
import json
from pathlib import Path

from training.pair_plan import build_pair_plan


SHA = "3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source_root = Path("/work/austinhpc25/nano4_cp2_fastest_first_pass")
    source_manifest_path = source_root / "results/moisesdb-manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text())
    output_manifest = args.output_dir / "training_manifest.json"
    pair_config_path = args.output_dir / "pair_plan_config.json"
    pair_plan_path = args.output_dir / "pair_plan.json"

    manifest = json.loads(json.dumps(source_manifest))
    manifest["dataset_id"] = "cp2c-mi300-handoff-moisesdb-v0.1-excerpts-v1"
    manifest["provenance"]["cp2c_role_transform"] = (
        "The eight CP2 final parents were already exposed and are reassigned to training only. "
        "No audio or excerpt changed."
    )
    for recording in manifest["recordings"]:
        if recording["split"] == "test":
            recording["split"] = "train"
    output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    pair_config = {
        "schema_version": "1.0",
        "config_id": "cp2c-mi300-handoff-controlled-pairs-v1",
        "root_seed": 260919,
        "splits": ["train", "validation", "calibration"],
        "excerpt_duration_s": 4.0,
        "hop_duration_s": 4.0,
        "max_excerpts_per_recording": 1,
        "single_source_gain_grid_db": [-6, -4, -2, 2, 4, 6],
        "common_gain_grid_db": [-4, 4],
        "multi_source_gain_cycles_db": [[-2, 4, 0, 2]],
        "shared_scale": 0.1,
        "noise_profiles": [{"kind": "none", "reference_snr_db": None, "observation_snr_db": None}],
    }
    pair_config_path.write_text(json.dumps(pair_config, indent=2, sort_keys=True) + "\n")
    plan = build_pair_plan(output_manifest, pair_config_path, git_commit=SHA)
    pair_plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n")

    train_parents = len({row["parent_group_id"] for row in plan["pairs"] if row["split"] == "train"})
    train_pairs = sum(row["split"] == "train" for row in plan["pairs"])
    validation_parents = len({row["parent_group_id"] for row in plan["pairs"] if row["split"] == "validation"})
    if (train_parents, train_pairs, validation_parents) != (48, 3264, 12):
        raise RuntimeError("Unexpected MI300 handoff split geometry")
    report = {
        "record_type": "CP2CMI300InputPreparation",
        "schema_version": "1.0",
        "git_sha": SHA,
        "audio_copied": False,
        "audio_dataset_root": "/work/austinhpc25/nano4_cp2_fastest_first_pass/datasets/moisesdb_prepared",
        "source_manifest": {"path": str(source_manifest_path), "sha256": sha256_file(source_manifest_path)},
        "training_manifest": {"path": str(output_manifest), "sha256": sha256_file(output_manifest)},
        "pair_plan_config": {"path": str(pair_config_path), "sha256": sha256_file(pair_config_path)},
        "pair_plan": {"path": str(pair_plan_path), "sha256": sha256_file(pair_plan_path)},
        "split_pair_counts": {split: sum(row["split"] == split for row in plan["pairs"]) for split in ("train", "validation", "calibration")},
        "split_parent_counts": {split: len({row["parent_group_id"] for row in plan["pairs"] if row["split"] == split}) for split in ("train", "validation", "calibration")},
        "fresh_final_included": False,
        "prior_exposed_final_policy": "Reassigned to train only; never eligible as untouched evaluation."
    }
    (args.output_dir / "input_preparation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
