"""Bounded CPU integration smoke; published restricted validation fixture only, no research."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
import wave

import numpy as np

from analyzers.bundle_validation import sha256_file
from analyzers.separation.p1_candidate import load_p1_candidate
from core.audio.types import AudioWindow
from core.contracts.validation import validate_analyzer_pair


def run_smoke(candidate, *, cache_dir, device="cpu"):
    candidate = Path(candidate)
    from analyzers.separation.p1_bundle import DEFAULT_SPEC
    spec = json.loads(DEFAULT_SPEC.read_text())
    for name, digest in spec["smoke_files"].items():
        if sha256_file(candidate / "runtime_smoke" / name) != digest:
            raise ValueError("Frozen smoke file hash mismatch")
    model_started = time.perf_counter()
    analyzer = load_p1_candidate(candidate, cache_dir=cache_dir, candidate_mode=True, device=device)
    model_seconds = time.perf_counter() - model_started
    try:
        config = {"instrument_config_version": 1, "instruments": [
            {"instrument_id": family, "family": family}
            for family in ("bass", "drums", "guitar", "keys", "vocals", "flute")]}
        def audio(name):
            with wave.open(str(candidate / "runtime_smoke" / (name + ".wav"))) as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) != (1, 4, 44100, 176400):
                    raise ValueError("Frozen smoke fixture geometry differs")
                samples = np.frombuffer(w.readframes(w.getnframes()), dtype="<i4").astype(np.float64) / 2147483648
            return AudioWindow(name, "p1-cpu-smoke", "smoke", "uploaded_file", name, "digital-clock",
                               44100, 0, 176400, 4.0, tuple(samples))
        reference, observation = audio("reference"), audio("observation")
        before = time.perf_counter()
        prepared = analyzer.prepare_reference([reference], config)
        reference_seconds = time.perf_counter() - before
        context = {
            "record_type": "AnalyzerContext", "schema_version": "1.0",
            "model": analyzer.capabilities()["model"], "observation": observation.identity(),
            "instrument_config": config, "target": {"target_kind": "reference",
                "reference": {"reference_id": "frozen-validation-smoke",
                              "source_asset_hash": "sha256:" + sha256_file(candidate / "runtime_smoke/reference.wav")},
                "baseline": None}, "comparison_regime": "matched_excerpt",
            "model_specific_context_asset": prepared["model_specific_context_asset"],
            "observation_purpose": "live", "probe_instrument_id": None,
        }
        before = time.perf_counter()
        first = analyzer.analyze(observation, context)
        seconds = time.perf_counter() - before
        file_diagnostics = analyzer.execution_diagnostics()
        second = analyzer.analyze(observation, context)
        mic = replace(observation, window_id="mic-observation", input_kind="live_microphone",
                      input_asset_or_device_id="replayed-mic-identity", clock_id="mic-clock",
                      analysis_run_id="mic-run")
        mic_context = dict(context, observation=mic.identity())
        mic_evidence = analyzer.analyze(mic, mic_context)
        validate_analyzer_pair(mic_context, mic_evidence)
        mic_diagnostics = analyzer.execution_diagnostics()
        six_source_parity = all(
            file_diagnostics["last_inference"][key] == mic_diagnostics["last_inference"][key]
            for key in ("source_order", "source_shape", "source_waveform_sha256", "source_levels_dbfs"))
        execution_proven = (file_diagnostics["model_calls_completed"] == 2
                            and mic_diagnostics["model_calls_completed"] == 4
                            and mic_diagnostics["model_calls_started"] == 4)
        validate_analyzer_pair(context, first)
        published = json.loads((candidate / "runtime_smoke/inference-run-1.json").read_text())
        expected = published["logical_output"]["family_evidence"][0]
        bass = first["measurements"][0]
        errors = {
            "reference_source_level_db": abs(bass["target_source_level_db"] - expected["reference_source_level_dbfs"]),
            "observation_source_level_db": abs(bass["source_level_db"] - expected["observation_source_level_dbfs"]),
            "raw_source_delta_db": abs((bass["source_level_db"] - bass["target_source_level_db"])
                                      - expected["raw_source_delta_db"]),
        }
        return {
            "record_type": "P1CandidateIntegrationSmoke", "schema_version": "1.0",
            "material_class": "real_recorded", "claim": "INTEGRATION_ONLY",
            "input_sha256": {n: sha256_file(candidate / "runtime_smoke" / n)
                             for n in ("reference.wav", "observation.wav", "inference-run-1.json")},
            "fixture_provenance": json.loads((candidate / "runtime_smoke/fixture_provenance.json").read_text()),
            "usage": "Private integration verification; no public/demo redistribution approval.",
            "noise_type": "none", "snr_db": None, "seed": 260920,
            "capabilities": analyzer.capabilities(), "manifest_sha256": hashlib.sha256(analyzer.bundle.data("manifest.json")).hexdigest(),
            "upstream_sha256": analyzer.bundle.manifest["upstream_pretrained_checkpoint"]["sha256"],
            "adapted_sha256": analyzer.bundle.manifest["bundled_adapted_checkpoint"]["sha256"],
            "base_module_sha256": analyzer.runner.base_hashes, "adapted_module_sha256": analyzer.runner.adapted_hashes,
            "deterministic_repeat_exact": first == second, "parity_absolute_tolerance_db": 0.01,
            "parity_errors_db": errors, "parity_passed": max(errors.values()) <= 0.01,
            "timing_seconds": {"model_load": model_seconds, "reference": reference_seconds, "observation": seconds},
            "context": context, "evidence": first, "python": platform.python_version(),
            "file_mic_execution_parity": {
                "actual_frozen_model": True, "physical_capture": False,
                "input_description": "Identical restricted fixture PCM; only acquisition identities changed.",
                "file_diagnostics": file_diagnostics, "mic_diagnostics": mic_diagnostics,
                "six_source_waveforms_identical": six_source_parity,
                "execution_proven": execution_proven, "mic_context": mic_context, "mic_evidence": mic_evidence,
            },
            "limitations": ["Restricted validation-excerpt smoke only; no real-room/PN54/MI300/production acceptance.",
                            "Raw source estimates only; non-bass attribution is unvalidated, partial/ambiguous anchors are null.",
                            "Cross-profile tolerance is an integration check, not an accuracy or calibration claim."],
        }
    finally:
        analyzer.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("Commit source before recording candidate smoke evidence")
    report = run_smoke(args.candidate, cache_dir=args.cache_dir, device=args.device)
    report["integration_git_sha"] = sha
    report["origin_git_sha"] = "3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if (report["parity_passed"] and report["deterministic_repeat_exact"]
                 and report["file_mic_execution_parity"]["six_source_waveforms_identical"]
                 and report["file_mic_execution_parity"]["execution_proven"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
