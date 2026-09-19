#!/usr/bin/env python3
"""Build the final relative-path SHA-256 manifest, excluding itself."""

import argparse
import hashlib
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == output or "__pycache__" in path.parts:
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    output.write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
