"""Bounded CPU integration smoke; published synthetic fixture only, no research."""
import argparse
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
                "reference": {"reference_id": "frozen-synthetic-smoke",
                              "source_asset_hash": "sha256:" + sha256_file(candidate / "runtime_smoke/reference.wav")},
                "baseline": None}, "comparison_regime": "matched_excerpt",
            "model_specific_context_asset": prepared["model_specific_context_asset"],
            "observation_purpose": "rehearsal", "probe_instrument_id": None,
        }
        before = time.perf_counter()
        first = analyzer.analyze(observation, context)
        seconds = time.perf_counter() - before
        second = analyzer.analyze(observation, context)
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
            "material_class": "synthetic", "claim": "INTEGRATION_ONLY",
            "input_sha256": {n: sha256_file(candidate / "runtime_smoke" / n)
                             for n in ("reference.wav", "observation.wav", "inference-run-1.json")},
            "capabilities": analyzer.capabilities(), "manifest_sha256": hashlib.sha256(analyzer.bundle.data("manifest.json")).hexdigest(),
            "upstream_sha256": analyzer.bundle.manifest["upstream_pretrained_checkpoint"]["sha256"],
            "adapted_sha256": analyzer.bundle.manifest["bundled_adapted_checkpoint"]["sha256"],
            "base_module_sha256": analyzer.runner.base_hashes, "adapted_module_sha256": analyzer.runner.adapted_hashes,
            "deterministic_repeat_exact": first == second, "parity_absolute_tolerance_db": 0.01,
            "parity_errors_db": errors, "parity_passed": max(errors.values()) <= 0.01,
            "timing_seconds": {"model_load": model_seconds, "reference": reference_seconds, "observation": seconds},
            "context": context, "evidence": first, "python": platform.python_version(),
            "limitations": ["Synthetic smoke only; no real-room/PN54/MI300/production acceptance.",
                            "Raw source levels only; unsupported anchors never enter evidence.",
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
    return 0 if report["parity_passed"] and report["deterministic_repeat_exact"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
