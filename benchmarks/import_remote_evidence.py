"""Metadata-only remote result import. Binary artifacts remain external/unverified."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from analyzers.bundle_validation import (
    contained_file, inspect_remote_metadata, read_json, require, sha,
)


from benchmarks.metadata_disclosure import validate_repository_metadata


def import_remote_evidence(source: Path, evidence_root: Path, *, expected_manifest_sha256: str,
                           max_json_bytes=32 * 1024 ** 2):
    sha(expected_manifest_sha256)
    metadata = inspect_remote_metadata(source)
    require(metadata["manifest_sha256"] == expected_manifest_sha256, "Remote manifest hash mismatch")
    evidence_root = Path(evidence_root).resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".evidence-", dir=evidence_root))
    try:
        manifest = metadata["manifest"]
        selected = ["manifest.json"] + [x["path"] for x in manifest["files"].values() if x["kind"] == "json"]
        total = 0
        for relative in selected:
            source_file = contained_file(source, relative)
            total += source_file.stat().st_size
            require(total <= max_json_bytes, "Metadata import exceeds JSON byte limit")
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, destination)
            validate_repository_metadata(read_json(destination))
        copied = inspect_remote_metadata(stage)
        require(copied["manifest_sha256"] == expected_manifest_sha256, "Source changed during import")
        final = evidence_root / expected_manifest_sha256
        if final.exists():
            require(inspect_remote_metadata(final)["manifest_sha256"] == expected_manifest_sha256,
                    "Existing evidence destination differs")
        else:
            os.rename(stage, final)
        return {"status": "IMPORTED_METADATA_ONLY", "metadata_path": str(final),
                "manifest_sha256": expected_manifest_sha256,
                "external_artifacts": copied["external_artifacts"],
                "binary_bytes_copied": 0, "numerical_use_accepted": False}
    finally:
        if stage.exists():
            require(stage.resolve().parent == evidence_root and stage.name.startswith(".evidence-"),
                    "Refusing cleanup outside evidence staging root")
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(import_remote_evidence(args.source, args.evidence_root,
                                           expected_manifest_sha256=args.manifest_sha256), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
