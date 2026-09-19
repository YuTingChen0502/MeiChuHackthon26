"""Import a remote directory or ZIP as a validated, content-addressed local bundle.

Declared files are copied as bytes. No model/code is loaded or executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from analyzers.bundle_validation import (
    contained_file, require, safe_relative, strict_json_bytes, validate_bundle,
)


def import_bundle(source: Path, store: Path, *, expected_manifest_sha256: str,
                  max_bytes: int = 8 * 1024 ** 3):
    source, store = Path(source), Path(store).resolve()
    require(type(max_bytes) is int and max_bytes > 0, "Positive import byte limit required")
    store.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".intake-", dir=store))
    archive = None
    try:
        if source.is_dir():
            manifest_path = contained_file(source, "manifest.json")
            require(manifest_path.stat().st_size <= 2 * 1024 ** 2, "Manifest too large")
            manifest_bytes = manifest_path.read_bytes()
        else:
            archive = zipfile.ZipFile(source)
            entries = archive.infolist()
            seen = set()
            for entry in entries:
                value = entry.filename.rstrip("/") if entry.is_dir() else entry.filename
                safe_relative(value)
                require(value.casefold() not in seen, "Duplicate ZIP path")
                seen.add(value.casefold())
                mode = entry.external_attr >> 16
                require(not stat.S_ISLNK(mode), "ZIP symlinks forbidden")
                require(not entry.flag_bits & 1, "Encrypted ZIP is unsupported")
            require(archive.getinfo("manifest.json").file_size <= 2 * 1024 ** 2, "Manifest too large")
            manifest_bytes = archive.read("manifest.json")
        require(len(manifest_bytes) <= 2 * 1024 ** 2, "Manifest too large")
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        require(digest == expected_manifest_sha256, "Remote manifest SHA-256 mismatch")
        manifest = strict_json_bytes(manifest_bytes)
        files = manifest.get("files")
        require(isinstance(files, dict), "Missing bundle file inventory")
        declared = {"manifest.json"}
        for entry in files.values():
            safe_relative(entry["path"])
            require(entry["path"].casefold() not in {x.casefold() for x in declared}, "Duplicate bundle path")
            declared.add(entry["path"])
        if archive:
            require({x.filename for x in archive.infolist() if not x.is_dir()} == declared,
                    "ZIP contains missing or undeclared files")
        (stage / "manifest.json").write_bytes(manifest_bytes)
        total = len(manifest_bytes)
        for entry in files.values():
            relative = entry["path"]
            destination = stage.joinpath(*safe_relative(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            reader = archive.open(relative) if archive else contained_file(source, relative).open("rb")
            with reader, destination.open("xb") as output:
                while block := reader.read(1024 * 1024):
                    total += len(block)
                    require(total <= max_bytes, "Bundle exceeds import byte limit")
                    output.write(block)
        validated = validate_bundle(stage)
        final = store / digest
        if final.exists():
            existing = validate_bundle(final)
            require(existing.manifest_sha256 == digest, "Existing destination is incompatible")
            return existing
        os.rename(stage, final)
        return validate_bundle(final)
    finally:
        if archive:
            archive.close()
        if stage.exists():
            require(stage.resolve().parent == store and stage.name.startswith(".intake-"),
                    "Refusing cleanup outside importer staging root")
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 ** 3)
    args = parser.parse_args(argv)
    bundle = import_bundle(args.source, args.store, expected_manifest_sha256=args.manifest_sha256,
                           max_bytes=args.max_bytes)
    print(json.dumps({"status": "IMPORTED_UNACCEPTED", "path": str(bundle.root),
                      "manifest_sha256": bundle.manifest_sha256}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
