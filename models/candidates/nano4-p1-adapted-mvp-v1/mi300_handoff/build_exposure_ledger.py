#!/usr/bin/env python3
"""Build the CP2/CP2B parent and artist exposure ledger."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path("/work/austinhpc25/nano4_cp2_fastest_first_pass")
    metadata_path = root / "results/moisesdb-metadata-audit.json"
    cp2_manifest_path = root / "results/moisesdb-manifest.json"
    cp2b_split_path = root / "cp2b_broad_family/split_audit/cp2b-split-v1.json"
    fresh_manifest_path = root / "cp2b_broad_family/fresh_final/cp2b-fresh-final-manifest-v1.json"
    metadata = json.loads(metadata_path.read_text())
    cp2_manifest = json.loads(cp2_manifest_path.read_text())
    cp2b_split = json.loads(cp2b_split_path.read_text())
    fresh_manifest = json.loads(fresh_manifest_path.read_text())

    cp2_role = {}
    for recording in cp2_manifest["recordings"]:
        parent = recording["parent_group_id"]
        role = recording["split"]
        if parent in cp2_role and cp2_role[parent] != role:
            raise RuntimeError("CP2 parent crosses roles")
        cp2_role[parent] = role
    cp2b_assignments = {row["parent_id"]: row for row in cp2b_split["assignments"]}
    actual_cp2b_train = {parent for parent, role in cp2_role.items() if role == "train"}
    fresh_parents = {recording["parent_group_id"] for recording in fresh_manifest["recordings"]}
    if fresh_parents != {parent for parent, row in cp2b_assignments.items() if row["split"] == "final"}:
        raise RuntimeError("Fresh-final manifest does not match frozen CP2B split")

    rows = []
    exposed_artists = set()
    for track in metadata["tracks"]:
        parent = track["parent_id"]
        old_role = cp2_role.get(parent)
        new_assignment = cp2b_assignments.get(parent)
        new_role = new_assignment["split"] if new_assignment else None
        cp2_status = {
            "train": "TRAINING_INPUT_AND_SUPERVISION",
            "validation": "VALIDATION_MODEL_OUTPUT_OBSERVED",
            "calibration": "CALIBRATION_MODEL_OUTPUT_OBSERVED",
            "test": "FINAL_MODEL_OUTPUT_OBSERVED",
        }.get(old_role, "UNUSED_METADATA_ONLY")
        if new_role == "train" and parent in actual_cp2b_train:
            cp2b_status = "P1_AND_P2_TRAINING_INPUT_AND_SUPERVISION"
        elif new_role == "train":
            cp2b_status = "DECLARED_CP2B_TRAIN_ONLY_NOT_USED_IN_CP2B_OPTIMIZATION; CP2_FINAL_OUTPUT_ALREADY_OBSERVED"
        elif new_role == "validation":
            cp2b_status = "P1_AND_P2_VALIDATION_MODEL_OUTPUT_OBSERVED"
        elif new_role == "calibration":
            cp2b_status = "P1_AND_P2_CALIBRATION_MODEL_OUTPUT_OBSERVED"
        elif new_role == "final":
            cp2b_status = "P1_BASELINE_AND_P1_ADAPTED_FRESH_FINAL_OUTPUT_OBSERVED"
        else:
            cp2b_status = "UNUSED_METADATA_ONLY"
        exposed = cp2_status != "UNUSED_METADATA_ONLY" or cp2b_status != "UNUSED_METADATA_ONLY"
        if exposed:
            exposed_artists.add(track["artist_group"])
        rows.append({
            "parent_id": parent,
            "artist": track["artist"],
            "artist_id": track["artist_group"],
            "cp2_role": old_role or "UNUSED",
            "cp2_exposure_status": cp2_status,
            "cp2b_role": new_role or "UNUSED",
            "cp2b_exposure_status": cp2b_status,
            "prediction_or_training_exposed": exposed,
            "fresh_final_output_observed": new_role == "final",
        })

    for row in rows:
        row["artist_has_any_exposed_parent"] = row["artist_id"] in exposed_artists
        row["eligible_as_future_untouched_candidate_before_content_freeze"] = (
            not row["prediction_or_training_exposed"]
            and not row["artist_has_any_exposed_parent"]
        )
    rows.sort(key=lambda row: row["parent_id"])
    result = {
        "record_type": "CP2CP2BExposureLedger",
        "schema_version": "1.0",
        "git_sha": "3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0",
        "policy": {
            "new_mi300_final_rule": "Use only genuinely unexposed parents from artist groups with no exposed parent; select using metadata only, then freeze before audio/model inspection.",
            "opened_cp2_or_cp2b_final_reuse": "PROHIBITED_AS_UNTOUCHED_FINAL",
            "eligibility_is_not_selection": "A true candidate flag does not preselect a future holdout and does not authorize audio inspection."
        },
        "source_artifacts": {
            "metadata_audit": {"path": str(metadata_path), "sha256": sha256_file(metadata_path)},
            "cp2_manifest": {"path": str(cp2_manifest_path), "sha256": sha256_file(cp2_manifest_path)},
            "cp2b_split": {"path": str(cp2b_split_path), "sha256": sha256_file(cp2b_split_path)},
            "cp2b_fresh_manifest": {"path": str(fresh_manifest_path), "sha256": sha256_file(fresh_manifest_path)}
        },
        "summary": {
            "parent_count": len(rows),
            "artist_count": len({row["artist_id"] for row in rows}),
            "exposed_parent_count": sum(row["prediction_or_training_exposed"] for row in rows),
            "exposed_artist_count": len(exposed_artists),
            "future_candidate_parent_count_before_content_freeze": sum(row["eligible_as_future_untouched_candidate_before_content_freeze"] for row in rows),
            "cp2_role_counts": dict(sorted(Counter(row["cp2_role"] for row in rows).items())),
            "cp2b_role_counts": dict(sorted(Counter(row["cp2b_role"] for row in rows).items())),
        },
        "parents": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
