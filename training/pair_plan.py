"""Deterministic, leakage-safe controlled-pair planning for manifested stems.

Planning is deliberately separate from audio materialization.  A plan fixes the
split/group identity, excerpt, intervention, noise condition, and seed before a
training host reads audio.  Materialization then verifies the exact manifest and
asset hashes and lets the existing oracle mask stems that are actually silent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping

from training.controlled_pairs import NoiseSpec, PairSpec, generate_controlled_pair
from training.experiment_metadata import current_git_commit, environment_record
from training.multitrack_assets import (
    ALLOWED_SPLITS,
    load_manifest,
    load_recording_excerpt,
    sha256_file,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _stable_seed(root_seed: int, identity: Mapping[str, object]) -> int:
    payload = f"{root_seed}:{_canonical_json(identity)}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_pair_plan_config(config: Mapping[str, object]) -> None:
    _require(config.get("schema_version") == "1.0", "Unsupported pair-plan schema_version")
    config_id = config.get("config_id")
    _require(isinstance(config_id, str) and bool(config_id), "config_id is required")
    root_seed = config.get("root_seed")
    _require(isinstance(root_seed, int) and not isinstance(root_seed, bool), "root_seed must be an integer")
    splits = config.get("splits")
    _require(isinstance(splits, list) and bool(splits), "splits must be non-empty")
    _require(len(splits) == len(set(splits)), "splits must not contain duplicates")
    _require(set(splits).issubset(ALLOWED_SPLITS), "Unsupported split in pair-plan config")
    for field in ("excerpt_duration_s", "hop_duration_s"):
        value = config.get(field)
        _require(_finite_number(value) and float(value) > 0.0,
                 f"{field} must be a positive finite number")
    max_excerpts = config.get("max_excerpts_per_recording")
    _require(isinstance(max_excerpts, int) and not isinstance(max_excerpts, bool)
             and max_excerpts > 0, "max_excerpts_per_recording must be a positive integer")
    shared_scale = config.get("shared_scale")
    _require(_finite_number(shared_scale) and 0.0 < float(shared_scale) <= 1.0,
             "shared_scale must be in (0, 1]")

    single = config.get("single_source_gain_grid_db")
    common = config.get("common_gain_grid_db")
    _require(isinstance(single, list) and bool(single), "single_source_gain_grid_db is required")
    _require(all(_finite_number(value) and float(value) != 0.0 for value in single),
             "single-source gain grid must contain finite non-zero values")
    _require(len(single) == len(set(float(value) for value in single)),
             "single-source gain grid must not contain duplicates")
    _require(isinstance(common, list), "common_gain_grid_db must be a list")
    _require(all(_finite_number(value) and float(value) != 0.0 for value in common),
             "common gain grid must contain only finite non-zero values")

    cycles = config.get("multi_source_gain_cycles_db")
    _require(isinstance(cycles, list), "multi_source_gain_cycles_db must be a list")
    for cycle in cycles:
        _require(isinstance(cycle, list) and len(cycle) >= 2,
                 "Each multi-source cycle must have at least two values")
        _require(all(_finite_number(value) for value in cycle),
                 "Multi-source cycles must contain finite gains")
        _require(sum(float(value) != 0.0 for value in cycle) >= 2,
                 "A multi-source cycle must change at least two positions")

    profiles = config.get("noise_profiles")
    _require(isinstance(profiles, list) and bool(profiles), "noise_profiles must be non-empty")
    seen_profiles: set[str] = set()
    for profile in profiles:
        _require(isinstance(profile, dict), "Each noise profile must be an object")
        kind = profile.get("kind")
        _require(kind in {"none", "white_gaussian"}, f"Unsupported noise kind: {kind}")
        reference_snr = profile.get("reference_snr_db")
        observation_snr = profile.get("observation_snr_db")
        if kind == "none":
            _require(reference_snr is None and observation_snr is None,
                     "Clean noise profile cannot declare SNR")
        else:
            _require(reference_snr is not None or observation_snr is not None,
                     "White-noise profile must declare at least one branch SNR")
            _require(all(value is None or _finite_number(value)
                         for value in (reference_snr, observation_snr)),
                     "SNR values must be finite numbers or null")
        identity = _canonical_json(profile)
        _require(identity not in seen_profiles, "Duplicate noise profile")
        seen_profiles.add(identity)


def _scenarios(instrument_ids: list[str], config: Mapping[str, object]) -> list[dict[str, object]]:
    zero = {instrument_id: 0.0 for instrument_id in instrument_ids}
    scenarios: list[dict[str, object]] = [{
        "scenario_id": "zero_change",
        "scenario_kind": "zero_change",
        "source_injected_gain_db": dict(zero),
        "common_gain_db": 0.0,
    }]
    for gain in config["common_gain_grid_db"]:  # type: ignore[index]
        gain_value = float(gain)
        scenarios.append({
            "scenario_id": f"common_{gain_value:+g}db",
            "scenario_kind": "common_gain",
            "source_injected_gain_db": dict(zero),
            "common_gain_db": gain_value,
        })
    for instrument_id in instrument_ids:
        for gain in config["single_source_gain_grid_db"]:  # type: ignore[index]
            gain_value = float(gain)
            injected = dict(zero)
            injected[instrument_id] = gain_value
            scenarios.append({
                "scenario_id": f"one_source_{instrument_id}_{gain_value:+g}db",
                "scenario_kind": "one_source_gain",
                "source_injected_gain_db": injected,
                "common_gain_db": 0.0,
            })
    if len(instrument_ids) >= 2:
        for cycle_index, cycle in enumerate(config["multi_source_gain_cycles_db"]):  # type: ignore[index]
            values = [float(value) for value in cycle]
            injected = {
                instrument_id: values[index % len(values)]
                for index, instrument_id in enumerate(instrument_ids)
            }
            scenarios.append({
                "scenario_id": f"multi_source_cycle_{cycle_index:02d}",
                "scenario_kind": "multi_source_gain",
                "source_injected_gain_db": injected,
                "common_gain_db": 0.0,
            })
    return scenarios


def _noise_id(profile: Mapping[str, object]) -> str:
    if profile["kind"] == "none":
        return "clean"
    digest = hashlib.sha256(_canonical_json(profile).encode("utf-8")).hexdigest()[:10]
    return f"white_{digest}"


def _duration_samples(duration_s: object, sample_rate_hz: int, field: str) -> int:
    exact = float(duration_s) * sample_rate_hz
    rounded = round(exact)
    _require(abs(exact - rounded) < 1e-9,
             f"{field} does not resolve to an integer sample count at {sample_rate_hz} Hz")
    _require(rounded > 0, f"{field} resolves to zero samples")
    return rounded


def build_pair_plan(
    manifest_path: Path,
    config_path: Path,
    *,
    git_commit: str,
) -> dict[str, object]:
    """Build a deterministic semantic pair plan from manifests and config files."""

    _require(len(git_commit) == 40 and all(c in "0123456789abcdef" for c in git_commit),
             "git_commit must be an exact lowercase 40-character SHA")
    manifest = load_manifest(manifest_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_pair_plan_config(config)
    requested_splits = set(config["splits"])
    entries: list[dict[str, object]] = []

    selected_recordings = sorted(
        (item for item in manifest["recordings"] if item["split"] in requested_splits),
        key=lambda item: (item["split"], item["recording_id"]),
    )
    _require(bool(selected_recordings), "Manifest has no recordings in requested splits")
    represented_splits = {item["split"] for item in selected_recordings}
    _require(represented_splits == requested_splits,
             f"Manifest lacks requested splits: {sorted(requested_splits - represented_splits)}")

    for recording in selected_recordings:
        total_samples = int(recording["sample_count"])
        sample_rate_hz = int(recording["sample_rate_hz"])
        excerpt_samples = _duration_samples(
            config["excerpt_duration_s"], sample_rate_hz, "excerpt_duration_s"
        )
        hop_samples = _duration_samples(
            config["hop_duration_s"], sample_rate_hz, "hop_duration_s"
        )
        _require(total_samples >= excerpt_samples,
                 f"Recording {recording['recording_id']} is shorter than excerpt_duration_s")
        starts = list(range(0, total_samples - excerpt_samples + 1, hop_samples))
        starts = starts[:int(config["max_excerpts_per_recording"])]
        instrument_ids = sorted(stem["instrument_id"] for stem in recording["stems"])
        families = {stem["instrument_id"]: stem["family"] for stem in recording["stems"]}
        asset_hashes = {stem["relative_path"]: stem["sha256"] for stem in recording["stems"]}
        scenarios = _scenarios(instrument_ids, config)
        for sample_start in starts:
            for scenario in scenarios:
                for noise_profile in config["noise_profiles"]:
                    identity = {
                        "dataset_id": manifest["dataset_id"],
                        "recording_id": recording["recording_id"],
                        "sample_start": sample_start,
                        "sample_count": excerpt_samples,
                        "scenario_id": scenario["scenario_id"],
                        "noise": noise_profile,
                    }
                    digest = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()[:16]
                    entries.append({
                        "pair_id": f"{recording['recording_id']}:{sample_start}:{scenario['scenario_id']}:{_noise_id(noise_profile)}:{digest}",
                        "seed": _stable_seed(int(config["root_seed"]), identity),
                        "dataset_id": manifest["dataset_id"],
                        "recording_id": recording["recording_id"],
                        "parent_group_id": recording["parent_group_id"],
                        "split": recording["split"],
                        "split_id": f"{manifest['dataset_id']}:{recording['split']}",
                        "sample_rate_hz": recording["sample_rate_hz"],
                        "sample_start": sample_start,
                        "sample_count": excerpt_samples,
                        "instrument_families": families,
                        "asset_sha256_by_path": asset_hashes,
                        **scenario,
                        "noise": dict(noise_profile),
                        "shared_scale": float(config["shared_scale"]),
                        "observability": "compute_from_verified_excerpt_at_materialization",
                    })

    split_identity: dict[str, object] = {}
    for split in sorted(requested_splits):
        recordings = [item for item in selected_recordings if item["split"] == split]
        split_identity[split] = {
            "recording_ids": sorted(item["recording_id"] for item in recordings),
            "parent_group_ids": sorted({item["parent_group_id"] for item in recordings}),
            "pair_count": sum(entry["split"] == split for entry in entries),
        }
    return {
        "record_type": "ControlledPairPlan",
        "schema_version": "1.0",
        "git_commit": git_commit,
        "config": config,
        "config_sha256": sha256_file(config_path),
        "manifest_sha256": sha256_file(manifest_path),
        "dataset_id": manifest["dataset_id"],
        "asset_provenance": manifest["provenance"],
        "split_identity": split_identity,
        "label_procedure": (
            "raw=common+source_injection; center=median(active raw); "
            "balance=raw-center; silent/inactive regression labels are null"
        ),
        "environment": environment_record(),
        "pair_count": len(entries),
        "pairs": entries,
    }


def materialize_planned_pair(
    manifest_path: Path,
    dataset_root: Path,
    plan: Mapping[str, object],
    entry: Mapping[str, object],
):
    """Verify and materialize one plan entry through the canonical pair generator."""

    _require(sha256_file(manifest_path) == plan.get("manifest_sha256"),
             "Manifest hash does not match pair plan")
    manifest = load_manifest(manifest_path)
    _require(entry.get("dataset_id") == manifest["dataset_id"], "Pair dataset_id mismatch")
    loaded = load_recording_excerpt(
        manifest,
        dataset_root=dataset_root,
        recording_id=str(entry["recording_id"]),
        sample_start=int(entry["sample_start"]),
        sample_count=int(entry["sample_count"]),
    )
    _require(entry.get("split") == loaded.split, "Pair split mismatch")
    _require(entry.get("parent_group_id") == loaded.parent_group_id, "Pair parent-group mismatch")
    _require(entry.get("sample_rate_hz") == loaded.sample_rate_hz, "Pair sample-rate mismatch")
    _require(entry.get("instrument_families") == loaded.families, "Pair instrument taxonomy mismatch")
    noise = entry["noise"]
    spec = PairSpec(
        pair_id=str(entry["pair_id"]),
        split_id=str(entry["split_id"]),
        seed=int(entry["seed"]),
        source_injected_gain_db=entry["source_injected_gain_db"],  # type: ignore[arg-type]
        common_gain_db=float(entry["common_gain_db"]),
        shared_scale=float(entry["shared_scale"]),
        noise=NoiseSpec(
            kind=str(noise["kind"]),  # type: ignore[index]
            reference_snr_db=noise.get("reference_snr_db"),  # type: ignore[union-attr]
            observation_snr_db=noise.get("observation_snr_db"),  # type: ignore[union-attr]
        ),
    )
    pair = generate_controlled_pair(loaded.stems, spec, asset_provenance=loaded.asset_provenance)
    pair.metadata["pair_plan"] = {
        "config_sha256": plan["config_sha256"],
        "manifest_sha256": plan["manifest_sha256"],
        "git_commit": plan["git_commit"],
        "scenario_id": entry["scenario_id"],
        "scenario_kind": entry["scenario_kind"],
        "sample_start": entry["sample_start"],
        "sample_count": entry["sample_count"],
    }
    return pair


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = build_pair_plan(
        args.manifest,
        args.config,
        git_commit=current_git_commit(REPO_ROOT),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {plan['pair_count']} deterministic pairs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
