#!/usr/bin/env python3
"""Execute and assert the deterministic two-run integration smoke."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    smoke = root / "runtime_smoke"
    bundle = root / "model_bundle"
    config = json.loads((smoke / "smoke_config.json").read_text())
    provenance = json.loads((smoke / "fixture_provenance.json").read_text())
    if provenance["source_split"] != "validation" or provenance["fresh_final_used"]:
        raise RuntimeError("Smoke fixture violates non-final evidence policy")
    outputs = []
    for index in range(config["repeat_count"]):
        output = smoke / f"inference-run-{index + 1}.json"
        subprocess.run([
            sys.executable, str(smoke / "inference_harness.py"),
            "--reference", str(smoke / "reference.wav"),
            "--observation", str(smoke / "observation.wav"),
            "--instrument-config", str(smoke / "instrument_config.json"),
            "--model-bundle", str(bundle),
            "--output", str(output),
            "--device", config["device"],
        ], check=True)
        outputs.append(json.loads(output.read_text()))
    first, second = outputs
    rows = {row["configured_family"]: row for row in first["logical_output"]["family_evidence"]}
    bass = rows["bass"]
    unsupported = config["expected_unsupported_families"]
    checks = {
        "checkpoint_loads": first["model_identity"]["adapted_checkpoint_sha256"] == config["expected_checkpoint_sha256"],
        "adapted_weights_present_and_differ": first["model_identity"]["task_specific_weights_differ"],
        "output_taxonomy_complete": set(rows) == set(json.loads((smoke / "instrument_config.json").read_text())["configured_families"]),
        "supported_mask_exact": [family for family, row in rows.items() if row["support_status"] == "SUPPORTED"] == config["expected_supported_families"],
        "unsupported_abstains": all(
            rows[family]["raw_source_delta_db"] is None
            and rows[family]["centered_balance_db"] is None
            and rows[family]["alert_state"] == "ABSTAIN"
            and rows[family]["reason"]
            for family in unsupported
        ),
        "gain_sign_preserved": bass["raw_source_delta_db"] is not None and bass["raw_source_delta_db"] > 0,
        "gain_magnitude_smoke_tolerance": bass["raw_source_delta_db"] is not None and abs(bass["raw_source_delta_db"] - provenance["expected_injected_gain_db"]) <= config["maximum_smoke_gain_error_db"],
        "centered_balance_available": bass["centered_balance_db"] is not None,
        "repeat_deterministic": first["deterministic_payload_sha256"] == second["deterministic_payload_sha256"],
        "no_hidden_benchmark_label_input": not first["inference_contract"]["hidden_benchmark_labels_accepted_as_inputs"],
        "input_hashes_match_fixture": (
            first["reference_identity"]["sha256"] == provenance["reference_sha256"]
            and first["observation_identity"]["sha256"] == provenance["observation_sha256"]
        ),
        "confidence_uncalibrated": first["inference_contract"]["confidence"] == "UNCALIBRATED_QUALITATIVE_ONLY",
    }
    result = {
        "record_type": "Nano4MVPCandidateSmokeResult",
        "schema_version": "1.0",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "fixture": provenance,
        "bundle_manifest_sha256": sha256_file(bundle / "manifest.json"),
        "inference_harness_sha256": sha256_file(smoke / "inference_harness.py"),
        "instrument_config_sha256": sha256_file(smoke / "instrument_config.json"),
        "deterministic_payload_sha256": first["deterministic_payload_sha256"],
        "supported_bass_evidence": {
            "reference_source_level_dbfs": bass["reference_source_level_dbfs"],
            "observation_source_level_dbfs": bass["observation_source_level_dbfs"],
            "raw_source_delta_db": bass["raw_source_delta_db"],
            "centered_balance_db": bass["centered_balance_db"],
            "alert_state": bass["alert_state"],
            "confidence_status": bass["confidence_status"],
        },
        "unsupported_family_outputs": {family: rows[family] for family in unsupported},
        "repeat_timing": [run["timing"] for run in outputs],
        "runtime_memory": outputs[0]["runtime_memory"],
        "runtime": outputs[0]["runtime"],
        "inference_run_sha256": [sha256_file(smoke / f"inference-run-{index + 1}.json") for index in range(config["repeat_count"])],
    }
    (smoke / "smoke_result.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if result["status"] != "PASS":
        raise RuntimeError(f"Smoke checks failed: {[key for key, value in checks.items() if not value]}")


if __name__ == "__main__":
    main()
