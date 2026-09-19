#!/usr/bin/env python3
"""Build one deterministic non-final validation fixture for bundle smoke."""

import argparse
import hashlib
import json
import wave
from pathlib import Path

import numpy as np

from training.pair_plan import materialize_planned_pair


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_pcm32(path, values, rate):
    integers = np.rint(np.clip(values, -1.0, 1.0 - 2 ** -31) * 2147483648.0).astype("<i4")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(4)
        wav.setframerate(rate)
        wav.writeframes(integers.tobytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path("/work/austinhpc25/nano4_cp2_fastest_first_pass")
    manifest = root / "results/moisesdb-manifest.json"
    plan_path = root / "results/moisesdb-clean-pair-plan.json"
    dataset_root = root / "datasets/moisesdb_prepared"
    plan = json.loads(plan_path.read_text())
    candidates = []
    for entry in plan["pairs"]:
        if entry["split"] != "validation" or entry["scenario_kind"] != "one_source_gain":
            continue
        changed = [
            instrument for instrument, gain in entry["source_injected_gain_db"].items()
            if abs(float(gain) - 4.0) < 1e-9
            and entry["instrument_families"][instrument] == "bass"
        ]
        if len(changed) == 1 and entry["recording_id"].endswith("excerpt0"):
            candidates.append(entry)
    entry = sorted(candidates, key=lambda item: item["pair_id"])[0]
    pair = materialize_planned_pair(manifest, dataset_root, plan, entry)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_path = args.output_dir / "reference.wav"
    observation_path = args.output_dir / "observation.wav"
    write_pcm32(reference_path, pair.reference_mix, entry["sample_rate_hz"])
    write_pcm32(observation_path, pair.observation_mix, entry["sample_rate_hz"])
    provenance = {
        "record_type": "Nano4MVPSmokeFixtureProvenance",
        "schema_version": "1.0",
        "source_split": "validation",
        "fresh_final_used": False,
        "pair_id": entry["pair_id"],
        "parent_group_id": entry["parent_group_id"],
        "recording_id": entry["recording_id"],
        "scenario_kind": entry["scenario_kind"],
        "expected_changed_family": "bass",
        "expected_injected_gain_db": 4.0,
        "reference_sha256": sha256_file(reference_path),
        "observation_sha256": sha256_file(observation_path),
        "source_manifest_sha256": sha256_file(manifest),
        "source_pair_plan_sha256": sha256_file(plan_path),
        "label_usage": "Expected gain is retained only for post-inference smoke assertions and is not passed to inference_harness.py."
    }
    (args.output_dir / "fixture_provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
