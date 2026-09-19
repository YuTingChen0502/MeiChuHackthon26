"""Validate empirical multitrack provenance, split grouping, hashes, and WAV headers."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from training.experiment_metadata import current_git_commit
from training.multitrack_assets import load_manifest, load_recording_excerpt, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[1]


def validate_assets(manifest_path: Path, dataset_root: Path) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    recordings = []
    split_counts = Counter()
    for item in manifest["recordings"]:
        loaded = load_recording_excerpt(
            manifest,
            dataset_root=dataset_root,
            recording_id=item["recording_id"],
            sample_start=0,
            sample_count=min(int(item["sample_count"]), int(item["sample_rate_hz"])),
        )
        split_counts[loaded.split] += 1
        recordings.append({
            "recording_id": loaded.recording_id,
            "parent_group_id": loaded.parent_group_id,
            "split": loaded.split,
            "sample_rate_hz": loaded.sample_rate_hz,
            "sample_count": item["sample_count"],
            "instrument_ids": sorted(loaded.stems),
            "verified_stem_count": len(loaded.stems),
        })
    return {
        "record_type": "MultitrackAssetValidation",
        "schema_version": "1.0",
        "status": "valid",
        "git_commit": current_git_commit(REPO_ROOT),
        "manifest_path": manifest_path.name,
        "manifest_sha256": sha256_file(manifest_path),
        "dataset_id": manifest["dataset_id"],
        "publication_status": manifest["provenance"]["allowed_publication_status"],
        "split_counts": dict(sorted(split_counts.items())),
        "recordings": recordings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = validate_assets(args.manifest, args.dataset_root)
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

