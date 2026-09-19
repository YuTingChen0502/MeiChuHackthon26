"""Run the first deterministic mixed-audio separation gain-response probe."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Mapping

import numpy as np

from analyzers.separation.diagnostic import SyntheticBandSeparator
from analyzers.separation.htdemucs import HTDemucs6sSeparator, SeparationRuntimeUnavailable
from analyzers.separation.levels import gain_response
from training.controlled_pairs import NoiseSpec, PairSpec, generate_controlled_pair
from training.experiment_metadata import build_experiment_metadata
from training.multitrack_assets import load_manifest, load_recording_excerpt, sha256_file


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "training" / "configs" / "first_gain_response.json"
DEFAULT_OUTPUT = REPO_ROOT / "benchmarks" / "results" / "first_gain_response"
INSTRUMENTS = ("bass", "guitar", "vocals", "drums")


def _synthetic_stems(sample_rate_hz: int, duration_s: float, seed: int) -> dict[str, np.ndarray]:
    count = int(sample_rate_hz * duration_s)
    time = np.arange(count, dtype=np.float64) / sample_rate_hz
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=12)
    frequencies = {
        "bass": (80.0, 140.0, 200.0),
        "guitar": (330.0, 660.0, 990.0),
        "vocals": (1400.0, 2100.0, 2800.0),
        "drums": (4000.0, 5200.0, 6800.0),
    }
    stems = {}
    for index, name in enumerate(INSTRUMENTS):
        components = [
            np.sin(2.0 * np.pi * frequency * time + phases[index * 3 + offset])
            for offset, frequency in enumerate(frequencies[name])
        ]
        # Fixed taper prevents endpoint discontinuities from contaminating other bands.
        taper = np.sin(np.pi * np.arange(count) / max(count - 1, 1)) ** 2
        stems[name] = 0.12 * taper * np.sum(components, axis=0) / len(components)
    return stems


def _cases(gain_grid: list[float]) -> list[dict[str, object]]:
    result = []
    for gain in gain_grid:
        result.append(
            {
                "case_id": f"guitar_{gain:+g}db".replace("+", "plus_").replace("-", "minus_"),
                "source_gain_db": {name: gain if name == "guitar" else 0.0 for name in INSTRUMENTS},
                "common_gain_db": 0.0,
            }
        )
    result.extend(
        [
            {
                "case_id": "common_plus_4db",
                "source_gain_db": {name: 0.0 for name in INSTRUMENTS},
                "common_gain_db": 4.0,
            },
            {
                "case_id": "multi_source_centered",
                "source_gain_db": {"bass": -2.0, "guitar": 4.0, "vocals": 0.0, "drums": 2.0},
                "common_gain_db": 1.0,
            },
        ]
    )
    return result


def _sign(value: float, tolerance: float) -> int:
    return 1 if value > tolerance else -1 if value < -tolerance else 0


def _metrics(rows: list[dict[str, object]], neutral_tolerance_db: float) -> dict[str, object]:
    eligible = [row for row in rows if row["target_balance_db"] is not None]
    numeric_covered = [row for row in eligible if row["predicted_raw_delta_db"] is not None]
    covered = [row for row in eligible if row["predicted_balance_db"] is not None]
    absolute_errors = [float(row["absolute_error_db"]) for row in covered]
    raw_absolute_errors = [float(row["raw_absolute_error_db"]) for row in numeric_covered]
    penalty_db = 12.0
    unconditional = [
        float(row["absolute_error_db"]) if row["absolute_error_db"] is not None else penalty_db
        for row in eligible
    ]
    unconditional_raw = [
        float(row["raw_absolute_error_db"]) if row["raw_absolute_error_db"] is not None else penalty_db
        for row in eligible
    ]
    directional = [
        row
        for row in covered
        if _sign(float(row["target_balance_db"]), neutral_tolerance_db) != 0
    ]
    sign_correct = sum(
        _sign(float(row["predicted_balance_db"]), neutral_tolerance_db)
        == _sign(float(row["target_balance_db"]), neutral_tolerance_db)
        for row in directional
    )
    tp = fp = fn = 0
    for row in eligible:
        truth = abs(float(row["target_balance_db"])) > neutral_tolerance_db
        predicted_value = row["predicted_balance_db"]
        predicted = predicted_value is not None and abs(float(predicted_value)) > neutral_tolerance_db
        tp += int(truth and predicted)
        fp += int(not truth and predicted)
        fn += int(truth and not predicted)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "eligible_measurements": len(eligible),
        "numeric_covered_measurements": len(numeric_covered),
        "numeric_coverage": len(numeric_covered) / len(eligible) if eligible else 0.0,
        "actionable_covered_measurements": len(covered),
        "actionable_coverage": len(covered) / len(eligible) if eligible else 0.0,
        "covered_measurements": len(covered),
        "coverage": len(covered) / len(eligible) if eligible else 0.0,
        "raw_delta_mae_db_on_numeric_covered": (
            float(np.mean(raw_absolute_errors)) if raw_absolute_errors else None
        ),
        "unconditional_raw_delta_mae_db": (
            float(np.mean(unconditional_raw)) if unconditional_raw else None
        ),
        "mae_db_on_covered": float(np.mean(absolute_errors)) if absolute_errors else None,
        "unconditional_mae_db": float(np.mean(unconditional)) if unconditional else None,
        "missing_prediction_penalty_db": penalty_db,
        "sign_accuracy_non_neutral_on_covered": sign_correct / len(directional) if directional else None,
        "non_neutral_covered_count": len(directional),
        "attributed_anomaly_precision": precision,
        "attributed_anomaly_recall": recall,
        "attributed_anomaly_f1": f1,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _separator(backend: str):
    if backend == "synthetic_band_masks_v1":
        return SyntheticBandSeparator()
    if backend == "htdemucs_6s":
        return HTDemucs6sSeparator(device="cpu")
    raise ValueError(f"Unknown backend: {backend}")


def run(
    config: Mapping[str, object],
    backend: str,
    command: list[str],
    *,
    input_stems: Mapping[str, np.ndarray] | None = None,
    input_provenance: Mapping[str, object] | None = None,
    input_split_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    sample_rate = int(config["sample_rate_hz"])
    duration_s = float(config["duration_s"])
    seed = int(config["seed"])
    if input_stems is None:
        stems = _synthetic_stems(sample_rate, duration_s, seed)
        provenance = {
            "asset_id": "generated-synthetic-four-band-v1",
            "origin": "generated://benchmarks.run_gain_response._synthetic_stems",
            "license_or_permission": "repository-generated mathematical waveforms; no third-party recording",
            "publication_status": "publishable",
            "scope": "pipeline diagnostic only; not music-domain feasibility evidence",
        }
        split_identity = {
            "split_id": config["split_id"],
            "parent_group": "generated-synthetic-four-band-v1",
            "all_augmentations_grouped": True,
        }
        evidence_asset_class = "synthetic"
    else:
        if set(input_stems) != set(INSTRUMENTS):
            raise ValueError(f"Empirical probe requires exactly these families: {INSTRUMENTS}")
        stems = {name: np.asarray(input_stems[name], dtype=np.float64) for name in INSTRUMENTS}
        if input_provenance is None or input_split_identity is None:
            raise ValueError("Empirical stems require provenance and split identity")
        provenance = dict(input_provenance)
        split_identity = dict(input_split_identity)
        evidence_asset_class = "manifested_multitrack"
    pair_split_id = str(split_identity.get("split_id", config["split_id"]))
    try:
        separator = _separator(backend)
    except SeparationRuntimeUnavailable as error:
        return {
            "probe_status": "blocked_missing_runtime",
            "backend": backend,
            "reason": str(error),
            "runtime_status": HTDemucs6sSeparator.runtime_status(),
            "claims": ["No HTDemucs gain-response result was measured."],
        }

    rows: list[dict[str, object]] = []
    pair_metadata: list[dict[str, object]] = []
    separation_cache = {}

    def separate_cached(signal: np.ndarray):
        digest = hashlib.sha256(np.ascontiguousarray(signal, dtype="<f8").tobytes()).hexdigest()
        if digest not in separation_cache:
            separation_cache[digest] = separator.separate(signal, sample_rate)
        return separation_cache[digest]

    for noise_index, noise in enumerate(config["noise_conditions"]):
        noise_kind = str(noise["kind"])
        snr = noise["snr_db"]
        for case_index, case in enumerate(_cases([float(x) for x in config["gain_grid_db"]])):
            pair_id = f"{case['case_id']}__{noise_kind}_{snr if snr is not None else 'clean'}"
            pair = generate_controlled_pair(
                stems,
                PairSpec(
                    pair_id=pair_id,
                    split_id=pair_split_id,
                    seed=seed + noise_index * 1000 + case_index,
                    source_injected_gain_db=case["source_gain_db"],
                    common_gain_db=float(case["common_gain_db"]),
                    shared_scale=float(config["shared_scale"]),
                    noise=NoiseSpec(
                        kind=noise_kind,
                        reference_snr_db=None if snr is None else float(snr),
                        observation_snr_db=None if snr is None else float(snr),
                    ),
                ),
                asset_provenance=provenance,
            )
            reference = separate_cached(pair.reference_mix)
            observation = separate_cached(pair.observation_mix)
            response = gain_response(
                reference.sources,
                observation.sources,
                configured_sources=INSTRUMENTS,
                activity_floor_dbfs=float(config["activity_floor_dbfs_rms"]),
            )
            pair_metadata.append(pair.metadata)
            for name in INSTRUMENTS:
                target = pair.labels.centered_balance_db[name]
                predicted_raw = response.raw_source_delta_db.get(name)
                predicted = response.centered_balance_db.get(name)
                target_raw = pair.labels.raw_source_delta_db[name]
                rows.append(
                    {
                        "pair_id": pair_id,
                        "case_id": case["case_id"],
                        "noise_kind": noise_kind,
                        "snr_db": snr,
                        "instrument": name,
                        "source_injected_gain_db": pair.labels.source_injected_gain_db[name],
                        "target_raw_delta_db": target_raw,
                        "target_common_mode_db": pair.labels.common_mode_gain_db,
                        "target_balance_db": target,
                        "predicted_raw_delta_db": predicted_raw,
                        "raw_absolute_error_db": (
                            None if target_raw is None or predicted_raw is None
                            else abs(predicted_raw - target_raw)
                        ),
                        "predicted_common_mode_db": response.common_mode_gain_db,
                        "predicted_balance_db": predicted,
                        "absolute_error_db": None if target is None or predicted is None else abs(predicted - target),
                        "valid_source": pair.labels.valid_source_mask[name],
                        "numeric_available": response.numeric_valid_mask[name],
                        "reliable_configured_source_count": response.reliable_configured_source_count,
                        "balance_identifiable": response.balance_identifiable,
                    }
                )

    metadata = build_experiment_metadata(
        repo_root=REPO_ROOT,
        config=config,
        seed=seed,
        asset_provenance=[provenance],
        split_identity=split_identity,
        injected_gain={
            "gain_grid_db": config["gain_grid_db"],
            "controls": ["zero", "common_gain", "one_source", "multi_source_centered"],
            "label_procedure": "training.oracle.compute_gain_labels",
        },
        noise_snr={"conditions": config["noise_conditions"], "independent_within_pair": True},
        model_checkpoint={
            "backend_id": separator.backend_id,
            "checkpoint_id": separator.checkpoint_id,
            "artifact": getattr(separator, "checkpoint_artifact", {
                "expected_sha256": None,
                "actual_sha256": None,
                "verified": None,
            }),
            "runtime": (
                HTDemucs6sSeparator.runtime_status()
                if backend == "htdemucs_6s"
                else {"implementation": "NumPy deterministic FFT masks"}
            ),
            "execution_settings": getattr(separator, "execution_settings", {}),
            "adapted": False,
        },
        command=command,
    )
    metrics_by_noise = {}
    for noise in config["noise_conditions"]:
        snr = noise["snr_db"]
        key = "clean" if snr is None else f"{noise['kind']}@{snr}dB"
        condition_rows = [
            row for row in rows
            if row["noise_kind"] == noise["kind"] and row["snr_db"] == snr
        ]
        metrics_by_noise[key] = _metrics(condition_rows, float(config["neutral_tolerance_db"]))
    return {
        "probe_status": "completed",
        "backend": separator.backend_id,
        "checkpoint": separator.checkpoint_id,
        "evidence_class": (
            "synthetic_pipeline_diagnostic_only"
            if evidence_asset_class == "synthetic" and backend == "synthetic_band_masks_v1"
            else "synthetic_htdemucs_smoke_not_music_domain_feasibility"
            if evidence_asset_class == "synthetic"
            else "manifested_multitrack_probe"
        ),
        "asset_mode": evidence_asset_class,
        "metadata": metadata,
        "pair_metadata": pair_metadata,
        "metrics": _metrics(rows, float(config["neutral_tolerance_db"])),
        "metric_semantics": {
            "numeric_coverage": "configured sources with finite raw source delta",
            "actionable_coverage": "configured sources with centered balance after at least three reliable configured sources",
            "coverage": "legacy alias of actionable_coverage",
        },
        "metrics_by_noise": metrics_by_noise,
        "unique_separation_calls": len(separation_cache),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--backend", choices=("synthetic_band_masks_v1", "htdemucs_6s"),
        default="synthetic_band_masks_v1",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--asset-manifest", type=Path)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--recording-id")
    parser.add_argument("--sample-start", type=int, default=0)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    command = [sys.executable, "-m", "benchmarks.run_gain_response", *sys.argv[1:]]
    empirical_fields = (args.asset_manifest, args.dataset_root, args.recording_id)
    if any(value is not None for value in empirical_fields) and not all(
        value is not None for value in empirical_fields
    ):
        parser.error("--asset-manifest, --dataset-root and --recording-id are required together")
    run_kwargs = {}
    if args.asset_manifest is not None:
        manifest = load_manifest(args.asset_manifest)
        sample_count = round(float(config["duration_s"]) * int(config["sample_rate_hz"]))
        loaded = load_recording_excerpt(
            manifest,
            dataset_root=args.dataset_root,
            recording_id=args.recording_id,
            sample_start=args.sample_start,
            sample_count=sample_count,
        )
        if loaded.sample_rate_hz != int(config["sample_rate_hz"]):
            parser.error("Manifest recording sample rate differs from benchmark config")
        family_to_instrument: dict[str, str] = {}
        for instrument_id, family in loaded.families.items():
            if family in INSTRUMENTS:
                if family in family_to_instrument:
                    parser.error(f"Multiple configured stems map to family {family}")
                family_to_instrument[family] = instrument_id
        missing = set(INSTRUMENTS).difference(family_to_instrument)
        if missing:
            parser.error(f"Recording lacks required families: {sorted(missing)}")
        selected_stems = {
            family: loaded.stems[instrument_id]
            for family, instrument_id in family_to_instrument.items()
        }
        provenance = dict(loaded.asset_provenance)
        provenance.update({
            "manifest_sha256": sha256_file(args.asset_manifest),
            "excerpt_sample_start": loaded.sample_start,
            "excerpt_sample_end": loaded.sample_end,
            "selected_family_to_instrument_id": family_to_instrument,
        })
        run_kwargs = {
            "input_stems": selected_stems,
            "input_provenance": provenance,
            "input_split_identity": {
                "split_id": f"{loaded.dataset_id}:{loaded.split}",
                "dataset_id": loaded.dataset_id,
                "recording_id": loaded.recording_id,
                "parent_group_id": loaded.parent_group_id,
                "split": loaded.split,
                "all_augmentations_grouped": True,
            },
        }
    result = run(config, args.backend, command, **run_kwargs)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.backend
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if result["probe_status"] == "completed":
        _write_csv(args.output_dir / f"{stem}.csv", result["rows"])
    print(json.dumps({key: result[key] for key in result if key not in ("rows", "pair_metadata")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
