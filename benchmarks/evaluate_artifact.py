"""Generic held-out analyzer evaluation. Labels remain outside the backend call."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from analyzers.bundle_validation import read_json, require, validate_bundle, validate_result_record
from analyzers.bundles import BackendRegistry
from benchmarks.paired_metrics import summarize
from core.audio.types import AudioWindow
from core.contracts.validation import validate_analyzer_pair


def pcm_hash(samples):
    return hashlib.sha256(np.ascontiguousarray(samples, dtype="<f8").tobytes()).hexdigest()


def _window(value):
    return value if isinstance(value, AudioWindow) else AudioWindow(**value)


def evaluate(bundle_path, *, registry, cases, provenance, thresholds):
    bundle = validate_bundle(Path(bundle_path))
    m = bundle.manifest
    require(cases, "Evaluation cases required")
    require(provenance["dataset_manifest_sha256"] == m["dataset"]["manifest_sha256"]
            and provenance["split_groups"] == m["dataset"]["split_groups"], "Evaluation dataset mismatch")
    require(provenance["material_class"] == m["dataset"]["material_class"], "Evaluation material mismatch")
    required_provenance = ("seed", "gain_intervention", "noise_type", "snr_db",
                           "augmentation", "label_procedure", "environment")
    require(all(k in provenance for k in required_provenance), "Incomplete experiment provenance")
    require(type(provenance["seed"]) is int, "Experiment seed required")
    require(isinstance(provenance["label_procedure"], str) and provenance["label_procedure"],
            "Ground-truth label procedure required")
    require(isinstance(provenance["environment"], dict) and provenance["environment"],
            "Measured runtime environment required")
    require(len({c["split"] for c in cases}) == 1, "Evaluate one split per report")
    backend = registry.instantiate(bundle)
    outputs, rows, timings, seen = [], [], [], set()
    try:
        require(backend.capabilities()["model"] == m["model"], "Backend identity mismatch")
        for case in cases:
            case_id = case["case_id"]
            require(case_id not in seen, "Duplicate evaluation case")
            seen.add(case_id)
            split = case["split"]
            require(split in {"validation", "calibration", "test"} and case["parent_group_id"] in provenance["split_groups"][split],
                    "Evaluation used wrong grouped split")
            reference = [_window(x) for x in case["reference_windows"]]
            window = _window(case["observation"])
            inp = m["input"]
            for w in reference + [window]:
                require(w.sample_rate_hz == inp["sample_rate_hz"]
                        and len(w.samples) == w.sample_end - w.sample_start
                        and inp["min_window_samples"] <= len(w.samples) <= inp["max_window_samples"]
                        and all(np.isfinite(x) for x in w.samples), "Evaluation PCM/input profile mismatch")
            require(reference, "Reference PCM required")
            require(case["comparison_regime"] in m["comparison_regimes"], "Unsupported comparison regime")
            configured = case["instrument_config"]
            require(set(case["labels"]) == {x["instrument_id"] for x in configured["instruments"]},
                    "Evaluation labels must cover every configured instrument")
            prepared = backend.prepare_reference(reference, copy.deepcopy(configured))
            context = {
                "record_type": "AnalyzerContext", "schema_version": "1.0", "model": copy.deepcopy(m["model"]),
                "observation": window.identity(), "instrument_config": copy.deepcopy(configured),
                "target": copy.deepcopy(case["target"]), "comparison_regime": case["comparison_regime"],
                "model_specific_context_asset": prepared["model_specific_context_asset"],
                "observation_purpose": "rehearsal", "probe_instrument_id": None,
            }
            before = time.perf_counter()
            evidence = backend.analyze(window, context)
            timings.append(time.perf_counter() - before)
            validate_analyzer_pair(context, evidence)
            require(evidence["evidence_mode"] == m["evidence_mode"], "Evaluation evidence mode mismatch")
            deltas = {
                x["instrument_id"]: (
                    x["source_level_delta_db"] if evidence["evidence_mode"] == "source_level_deltas"
                    else x["source_level_db"] - x["target_source_level_db"])
                for x in evidence["measurements"] if x["validity"] == "valid"
            }
            center = float(np.median(list(deltas.values()))) if len(deltas) >= 3 else None
            for item in configured["instruments"]:
                key = item["instrument_id"]
                label = case["labels"][key]
                delta = deltas.get(key)
                rows.append({
                    "pair_id": case_id, "instrument_id": key,
                    "true_raw_db": label["raw_source_delta_db"], "true_balance_db": label["balance_deviation_db"],
                    "attribution_evaluable": label["attribution_evaluable"],
                    "predicted_raw_db": delta,
                    "predicted_balance_db": delta - center if delta is not None and center is not None else None,
                })
            outputs.append({
                "case_id": case_id, "split": split, "parent_group_id": case["parent_group_id"],
                "pcm_sha256": pcm_hash(window.samples),
                "reference_pcm_sha256": [pcm_hash(w.samples) for w in reference],
                "instrument_config": copy.deepcopy(configured), "target": copy.deepcopy(case["target"]),
                "comparison_regime": case["comparison_regime"],
                "context": context, "evidence": evidence,
            })
    finally:
        backend.close()
    metrics = summarize(rows, alert_db=thresholds["alert_db"],
                        missing_penalty_db=thresholds["missing_prediction_penalty_db"])
    metrics["eligible_count"] = metrics["balance_eligible_measurements"]
    metrics["case_count"] = len(cases)
    metrics["prediction_seconds_p95"] = float(np.percentile(timings, 95))
    report = {
        "record_type": "BenchmarkResult", "schema_version": "1.0",
        "model": m["model"], "runtime_artifact_sha256": m["files"][m["components"]["runtime_model"]]["sha256"],
        **{k: copy.deepcopy(provenance[k]) for k in (
            "git_sha", "config_sha256", "dataset_manifest_sha256", "split_groups", "material_class")},
        "example_only": provenance["material_class"] != "real_recorded" or provenance.get("example_only", True),
        "status": "evaluated", "evaluation_split": cases[0]["split"],
        "metrics": metrics, "thresholds": thresholds, "outputs": outputs, "rows": rows,
        "experiment": {k: copy.deepcopy(provenance[k]) for k in required_provenance},
        "bundle_manifest_sha256": bundle.manifest_sha256,
    }
    require(len({c["split"] for c in cases}) == 1, "Evaluate one split per report")
    validate_result_record(report, model=m["model"], artifact_sha256=report["runtime_artifact_sha256"])
    return report


def main(argv=None, *, registry=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(args.bundle, registry=registry or BackendRegistry(), cases=read_json(args.cases),
                      provenance=read_json(args.provenance), thresholds=read_json(args.thresholds))
    from analyzers.bundle_validation import sha256_file
    report["input_hashes"] = {"cases": sha256_file(args.cases), "thresholds": sha256_file(args.thresholds),
                              "provenance": sha256_file(args.provenance)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
