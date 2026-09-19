"""Reproducible experiment metadata capture."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


REQUIRED_FIELDS = {
    "git_commit",
    "config",
    "seed",
    "asset_provenance",
    "split_identity",
    "injected_gain",
    "noise_snr",
    "model_checkpoint",
    "environment",
}


def current_git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
    ).strip()


def environment_record() -> dict[str, object]:
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pid": os.getpid(),
    }


def build_experiment_metadata(
    *,
    repo_root: Path,
    config: Mapping[str, object],
    seed: int,
    asset_provenance: Sequence[Mapping[str, object]],
    split_identity: Mapping[str, object],
    injected_gain: Mapping[str, object],
    noise_snr: Mapping[str, object],
    model_checkpoint: Mapping[str, object],
    command: Sequence[str],
) -> dict[str, object]:
    record = {
        "schema_version": "1.0",
        "git_commit": current_git_commit(repo_root),
        "config": dict(config),
        "seed": int(seed),
        "asset_provenance": [dict(item) for item in asset_provenance],
        "split_identity": dict(split_identity),
        "injected_gain": dict(injected_gain),
        "noise_snr": dict(noise_snr),
        "model_checkpoint": dict(model_checkpoint),
        "environment": environment_record(),
        "command": list(command),
    }
    validate_experiment_metadata(record)
    return record


def validate_experiment_metadata(record: Mapping[str, object]) -> None:
    missing = REQUIRED_FIELDS.difference(record)
    if missing:
        raise ValueError(f"Experiment metadata missing fields: {sorted(missing)}")
    commit = record["git_commit"]
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("git_commit must be an exact 40-character SHA")
    json.dumps(record, sort_keys=True, allow_nan=False)

