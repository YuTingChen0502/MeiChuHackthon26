"""Read-only environment inventory and exact-source guard; submits no jobs."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import subprocess
from pathlib import Path

from training.experiment_metadata import current_git_commit, environment_record
from training.multitrack_assets import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("numpy", "torch", "torchaudio", "demucs", "jsonschema", "onnxruntime")


def source_identity(repo_root=REPO_ROOT):
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_root, text=True).splitlines()
    return {"git_commit": current_git_commit(repo_root), "worktree_clean": not status,
            "dirty_paths": status}


def require_exact_source(expected_sha: str, config_path: Path, expected_config_hash: str,
                         repo_root=REPO_ROOT):
    identity = source_identity(repo_root)
    if (len(expected_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_sha)
            or identity["git_commit"] != expected_sha):
        raise ValueError("Exact Git SHA mismatch")
    if not identity["worktree_clean"]:
        raise ValueError("Experiment source worktree must be clean")
    relative = config_path.resolve().relative_to(repo_root.resolve())
    subprocess.check_call(["git", "ls-files", "--error-unmatch", relative.as_posix()],
                          cwd=repo_root, stdout=subprocess.DEVNULL)
    if sha256_file(config_path) != expected_config_hash:
        raise ValueError("Experiment config SHA-256 mismatch")
    return identity


def inventory():
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = {"version": importlib.metadata.version(name),
                              "importable": importlib.util.find_spec(name) is not None}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"version": None, "importable": False}
    return {
        "record_type": "CP2EnvironmentReadiness", "schema_version": "1.0",
        "source": source_identity(), "environment": environment_record(),
        "packages": packages,
        # Only explicit scheduler metadata; never dump environment/credentials.
        "scheduler": {key: os.environ.get(key) for key in (
            "SLURM_JOB_ID", "SLURM_JOB_ACCOUNT", "SLURM_JOB_PARTITION",
            "SLURM_JOB_NUM_NODES", "SLURM_GPUS_ON_NODE", "SLURM_TIMELIMIT")},
        "claims": {
            "gate_a": "BLOCKED_EXTERNAL_ASSETS",
            "mi300_access_budget": "NOT_VERIFIED_BY_INVENTORY",
            "optimizer_executed": False, "gpu_executed": False,
            "real_analyzer_enabled": False,
        },
        "limitations": [
            "Package presence is not import, device compatibility or model execution evidence.",
            "No GPU job, model download, optimizer or empirical audio run is performed.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--config-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    fields = (args.expected_sha, args.config, args.config_sha256)
    if any(fields):
        if not all(fields):
            raise ValueError("Exact-source guard requires SHA, config and config SHA-256")
        require_exact_source(args.expected_sha, args.config, args.config_sha256)
    report = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Inventory saved; no model/GPU job executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
