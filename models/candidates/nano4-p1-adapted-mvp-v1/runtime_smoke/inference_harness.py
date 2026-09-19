#!/usr/bin/env python3
"""External experimental harness for the frozen Nano4 P1_ADAPTED bundle."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import time
import wave
from pathlib import Path

import numpy as np


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def read_wave(path):
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        count = wav.getnframes()
        payload = wav.readframes(count)
    if channels not in (1, 2):
        raise ValueError(f"Expected mono or stereo input: {path}")
    if width == 2:
        values = np.frombuffer(payload, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        integers = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
        integers = np.where(integers & 0x800000, integers - 0x1000000, integers)
        values = integers.astype(np.float64) / 8388608.0
    elif width == 4:
        values = np.frombuffer(payload, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"Unsupported PCM width {width}: {path}")
    values = values.reshape(-1, channels).mean(axis=1)
    return values, {"sample_rate_hz": rate, "sample_count": count, "input_channels": channels, "sample_width_bytes": width}


def module_hash(name, module):
    digest = hashlib.sha256()
    for key, value in sorted(module.state_dict().items()):
        digest.update(f"{name}.{key}".encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def verify_repository(repo, expected_sha):
    actual = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if actual != expected_sha:
        raise RuntimeError(f"Repository SHA mismatch: {actual}")
    dirty = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    ).stdout
    if dirty:
        raise RuntimeError("Tracked repository is not clean")
    return actual


def run_inference(reference_path, observation_path, instrument_config_path, bundle_path, device):
    bundle = Path(bundle_path).resolve()
    manifest = json.loads((bundle / "manifest.json").read_text())
    frontend = json.loads((bundle / manifest["frontend"]).read_text())
    taxonomy = json.loads((bundle / manifest["taxonomy"]).read_text())
    thresholds = json.loads((bundle / manifest["thresholds"]).read_text())
    instruments = json.loads(Path(instrument_config_path).read_text())
    configured = instruments["configured_families"]
    if not configured or len(configured) != len(set(configured)):
        raise ValueError("configured_families must be a non-empty unique list")

    adapted_path = bundle / manifest["bundled_adapted_checkpoint"]["path"]
    base_path = bundle / manifest["upstream_pretrained_checkpoint"]["path"]
    if sha256_file(adapted_path) != manifest["bundled_adapted_checkpoint"]["sha256"]:
        raise RuntimeError("Adapted checkpoint hash mismatch")
    if sha256_file(base_path) != manifest["upstream_pretrained_checkpoint"]["sha256"]:
        raise RuntimeError("Upstream checkpoint hash mismatch")
    verify_repository(Path(manifest["source_repository"]), manifest["source_repository_sha"])

    reference, reference_geometry = read_wave(reference_path)
    observation, observation_geometry = read_wave(observation_path)
    for name, geometry in (("reference", reference_geometry), ("observation", observation_geometry)):
        if geometry["sample_rate_hz"] != frontend["sample_rate_hz"]:
            raise ValueError(f"{name} sample rate mismatch")
        if geometry["sample_count"] != frontend["window_samples"]:
            raise ValueError(f"{name} must contain exactly one 4-second window")
    if reference.shape != observation.shape:
        raise ValueError("Reference and observation geometry differs")

    os.environ["TORCH_HOME"] = str(bundle / "torch_cache")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    from analyzers.separation.htdemucs import HTDemucs6sSeparator
    from analyzers.separation.levels import gain_response, rms_dbfs

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    total_started = time.perf_counter()
    load_started = time.perf_counter()
    separator = HTDemucs6sSeparator(device=device, segment_s=4.0, seed=260920)
    if len(separator._model.models) != 1:
        raise RuntimeError("Expected one network in the HTDemucs_6s bag")
    network = separator._model.models[0]
    artifact = torch.load(adapted_path, map_location="cpu", weights_only=False)
    if artifact["base_checkpoint_sha256"] != manifest["upstream_pretrained_checkpoint"]["sha256"]:
        raise RuntimeError("Adapted artifact has the wrong upstream parent")
    expected_modules = {"decoder.3.conv_tr", "tdecoder.3.conv_tr"}
    if set(artifact["state"]) != expected_modules:
        raise RuntimeError("Unexpected adapted module set")
    base_module_hashes = {
        name: module_hash(name, network.get_submodule(name)) for name in sorted(expected_modules)
    }
    for name, state in artifact["state"].items():
        network.get_submodule(name).load_state_dict(state)
    adapted_module_hashes = {
        name: module_hash(name, network.get_submodule(name)) for name in sorted(expected_modules)
    }
    expected_identity = manifest["adaptation_identity"]
    if base_module_hashes != expected_identity["expected_upstream_module_sha256"]:
        raise RuntimeError("Loaded upstream projection identity mismatch")
    if adapted_module_hashes != expected_identity["expected_adapted_module_sha256"]:
        raise RuntimeError("Loaded adapted projection identity mismatch")
    if any(base_module_hashes[name] == adapted_module_hashes[name] for name in expected_modules):
        raise RuntimeError("Adapted projection unexpectedly equals its upstream parent")
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    model_load_seconds = time.perf_counter() - load_started

    inference_started = time.perf_counter()
    reference_sources = separator.separate(reference, frontend["sample_rate_hz"])
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    reference_seconds = time.perf_counter() - inference_started
    observation_started = time.perf_counter()
    observation_sources = separator.separate(observation, frontend["sample_rate_hz"])
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    observation_seconds = time.perf_counter() - observation_started

    known = taxonomy["families"]
    recognized = [family for family in configured if family in known]
    model_sources = [known[family]["model_source"] for family in recognized]
    if len(model_sources) != len(set(model_sources)):
        raise ValueError("Configured families map to duplicate model sources")
    response = gain_response(
        reference_sources.sources,
        observation_sources.sources,
        configured_sources=model_sources,
        activity_floor_dbfs=thresholds["activity_floor_dbfs"],
    ) if model_sources else None

    rows = []
    for family in configured:
        if family not in known:
            rows.append({
                "configured_family": family,
                "support_status": "INSUFFICIENT_EVIDENCE",
                "activity": null_activity(),
                "validity": false_validity(),
                "reference_source_level_dbfs": None,
                "observation_source_level_dbfs": None,
                "raw_source_delta_db": None,
                "centered_balance_db": None,
                "alert_state": "ABSTAIN",
                "confidence_status": "UNCALIBRATED_UNAVAILABLE",
                "reason": taxonomy["unknown_configured_family_policy"]["reason"],
            })
            continue
        policy = known[family]
        if policy["status"] != "SUPPORTED":
            rows.append({
                "configured_family": family,
                "model_source": policy["model_source"],
                "support_status": policy["status"],
                "activity": null_activity(),
                "validity": false_validity(),
                "reference_source_level_dbfs": None,
                "observation_source_level_dbfs": None,
                "raw_source_delta_db": None,
                "centered_balance_db": None,
                "alert_state": "ABSTAIN",
                "confidence_status": "UNCALIBRATED_UNAVAILABLE",
                "reason": policy["reason"],
            })
            continue
        source = policy["model_source"]
        ref_level = rms_dbfs(reference_sources.sources[source], activity_floor_dbfs=thresholds["activity_floor_dbfs"])
        obs_level = rms_dbfs(observation_sources.sources[source], activity_floor_dbfs=thresholds["activity_floor_dbfs"])
        raw_delta = response.raw_source_delta_db[source]
        centered = response.centered_balance_db[source]
        valid = raw_delta is not None and centered is not None
        alert_threshold = thresholds["family_operating_points"][family]["alert_threshold_db"]
        rows.append({
            "configured_family": family,
            "model_source": source,
            "support_status": "SUPPORTED",
            "activity": {
                "reference_active": ref_level is not None,
                "observation_active": obs_level is not None,
                "activity_floor_dbfs": thresholds["activity_floor_dbfs"],
            },
            "validity": {
                "numeric_source_delta_available": raw_delta is not None,
                "centered_balance_available": centered is not None,
                "balance_identifiable": bool(response.balance_identifiable),
            },
            "reference_source_level_dbfs": ref_level,
            "observation_source_level_dbfs": obs_level,
            "raw_source_delta_db": raw_delta,
            "centered_balance_db": centered,
            "alert_state": (
                "ABSTAIN" if not valid else
                "ANOMALY_CANDIDATE" if abs(centered) >= alert_threshold else
                "WITHIN_FROZEN_THRESHOLD"
            ),
            "alert_threshold_db": alert_threshold,
            "confidence_status": "UNCALIBRATED_QUALITATIVE_AVAILABLE" if valid else "UNCALIBRATED_UNAVAILABLE",
            "reason": None if valid else "Activity or common-mode identifiability requirement not met.",
        })

    total_seconds = time.perf_counter() - total_started
    logical = {
        "bundle_id": manifest["bundle_id"],
        "bundle_checkpoint_sha256": sha256_file(adapted_path),
        "reference_sha256": sha256_file(reference_path),
        "observation_sha256": sha256_file(observation_path),
        "configured_families": configured,
        "common_mode_gain_db": response.common_mode_gain_db if response is not None else None,
        "reliable_configured_model_source_count": response.reliable_configured_source_count if response is not None else 0,
        "balance_identifiable": bool(response.balance_identifiable) if response is not None else False,
        "family_evidence": rows,
    }
    return {
        "record_type": "Nano4MVPExperimentalInferenceEvidence",
        "schema_version": "1.0",
        "model_identity": {
            "bundle_id": manifest["bundle_id"],
            "architecture": manifest["architecture"],
            "repository_sha": manifest["source_repository_sha"],
            "upstream_checkpoint_sha256": sha256_file(base_path),
            "adapted_checkpoint_sha256": sha256_file(adapted_path),
            "base_module_sha256": base_module_hashes,
            "adapted_module_sha256": adapted_module_hashes,
            "task_specific_weights_differ": all(base_module_hashes[name] != adapted_module_hashes[name] for name in expected_modules),
        },
        "reference_identity": {"path": str(Path(reference_path).resolve()), "sha256": sha256_file(reference_path), **reference_geometry},
        "observation_identity": {"path": str(Path(observation_path).resolve()), "sha256": sha256_file(observation_path), **observation_geometry},
        "instrument_config_identity": {"path": str(Path(instrument_config_path).resolve()), "sha256": sha256_file(instrument_config_path)},
        "inference_contract": {
            "matched_reference": True,
            "independent_normalization": False,
            "hidden_benchmark_labels_accepted_as_inputs": False,
            "confidence": "UNCALIBRATED_QUALITATIVE_ONLY",
        },
        "logical_output": logical,
        "deterministic_payload_sha256": canonical_sha256(logical),
        "timing": {
            "model_load_and_adaptation_seconds": model_load_seconds,
            "reference_separation_seconds": reference_seconds,
            "observation_separation_seconds": observation_seconds,
            "total_seconds": total_seconds,
        },
        "runtime_memory": {
            "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated()) if device.startswith("cuda") else None,
            "process_max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        },
        "runtime": {
            "device": device,
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "demucs": __import__("demucs").__version__,
            "numpy": np.__version__,
        },
    }


def null_activity():
    return {"reference_active": None, "observation_active": None, "activity_floor_dbfs": -70.0}


def false_validity():
    return {"numeric_source_delta_available": False, "centered_balance_available": False, "balance_identifiable": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--instrument-config", type=Path, required=True)
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    result = run_inference(args.reference, args.observation, args.instrument_config, args.model_bundle, args.device)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
