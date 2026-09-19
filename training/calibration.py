"""Fit/evaluate unaccepted binned calibration candidates from declared held-out rows.

No audio training, backbone choice or live confidence policy is implemented here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from analyzers.bundle_validation import read_json, require, validate_result_record
from analyzers.calibration_metadata import EVENTS, ENDPOINT_POLICY, lookup_bin, validate_calibration
from analyzers.bundle_validation import sha256_file


def _validate_rows(document, *, split, model, artifact_sha256):
    require(document.get("record_type") == "CalibrationRows" and document.get("schema_version") == "1.0",
            "Expected CalibrationRows version 1.0")
    require(document.get("model") == model and document.get("runtime_artifact_sha256") == artifact_sha256,
            "Calibration row identity mismatch")
    require(isinstance(document.get("label_procedure"), str) and document["label_procedure"],
            "Ground-truth label procedure required")
    require(isinstance(document.get("score_features"), dict), "Declared score features required")
    rows = document.get("rows")
    require(isinstance(rows, list) and rows, "Calibration rows must be nonempty")
    seen = set()
    groups = document["split_groups"]
    require(set(groups) == {"train", "validation", "calibration", "test"}, "Four split groups required")
    all_groups = [g for values in groups.values() for g in values]
    require(len(all_groups) == len(set(all_groups)), "Calibration split leakage")
    for row in rows:
        require(row["sample_id"] not in seen, "Duplicate calibration sample")
        seen.add(row["sample_id"])
        require(row["split"] == split and row["parent_group_id"] in groups[split],
                "Calibration fitting/evaluation used wrong split")
        require(row["probability_event"] in EVENTS, "Unknown event label")
        require(type(row["eligible"]) is bool, "Explicit eligibility required")
        require(type(row["attribution_correct"]) is bool
                and type(row["target_within_normal_envelope"]) is bool, "Explicit ground-truth labels required")
        require((row["target_balance_db"] is None and not row["eligible"]) or
                (type(row["target_balance_db"]) in (int, float) and math.isfinite(row["target_balance_db"])),
                "Invalid calibration target")
        for field in ("score", "predicted_balance_db"):
            require(row[field] is None or (type(row[field]) in (int, float) and math.isfinite(row[field])),
                    "Invalid calibration numerical value")
    return rows


def _success(row):
    pred, truth = row["predicted_balance_db"], row["target_balance_db"]
    magnitude_correct = abs(pred - truth) <= 2.0
    if row["probability_event"] == "joint_anomaly_numeric_correct":
        return row["attribution_correct"] and pred * truth > 0 and magnitude_correct
    return row["attribution_correct"] and row["target_within_normal_envelope"] and magnitude_correct


def fit_candidate(document, config, *, rows_sha256, config_sha256):
    model, artifact = document["model"], document["runtime_artifact_sha256"]
    rows = _validate_rows(document, split="calibration", model=model, artifact_sha256=artifact)
    require(config["magnitude_tolerance_db"] == 2.0, "Only the frozen 2 dB correctness event is supported")
    coverage = config["interval_mass"]
    require(type(coverage) in (int, float) and 0 < coverage < 1, "Invalid residual interval mass")
    require(set(config["mappings"]) <= EVENTS and config["mappings"], "Invalid event configuration")
    mappings = {}
    for event, settings in config["mappings"].items():
        require(settings["score_feature"] == document["score_features"].get(event),
                "Calibration score name/unit mismatch")
        edges = settings["score_edges"]
        require(isinstance(edges, list) and len(edges) >= 2
                and all(type(v) in (int, float) and math.isfinite(v) for v in edges)
                and all(a < b for a, b in zip(edges, edges[1:])), "Score edges must be finite and increasing")
        bins = []
        for i, (lower, upper) in enumerate(zip(edges, edges[1:])):
            members = [r for r in rows if r["probability_event"] == event and r["eligible"]
                       and r["predicted_balance_db"] is not None and r["score"] is not None
                       and (lower <= r["score"] < upper or i == len(edges)-2 and r["score"] == upper)]
            if not members:
                continue
            residuals = [r["target_balance_db"] - r["predicted_balance_db"] for r in members]
            alpha = (1 - coverage) / 2
            interval = np.quantile(residuals, [alpha, 1 - alpha]).tolist()
            success = sum(_success(r) for r in members)
            bins.append({"lower": lower, "upper": upper, "count": len(members), "success_count": success,
                         "probability": success / len(members), "residual_interval_db": interval})
        if bins:
            mappings[event] = {
                "magnitude_tolerance_db": 2.0, "score_feature": settings["score_feature"],
                "endpoint_policy": ENDPOINT_POLICY,
                "interval_semantics": "true_balance_minus_predicted_balance", "bins": bins,
            }
    require(mappings, "No supported calibration bins; refusing fabricated confidence")
    identity = hashlib.sha256((rows_sha256 + config_sha256 + artifact).encode()).hexdigest()
    result = {
        "record_type": "CalibrationCandidate", "schema_version": "1.0",
        "calibration_id": "calibration-" + identity, "model": copy.deepcopy(model),
        "runtime_artifact_sha256": artifact, "git_sha": document["git_sha"],
        "config_sha256": config_sha256, "dataset_manifest_sha256": document["dataset_manifest_sha256"],
        "split_groups": copy.deepcopy(document["split_groups"]),
        "material_class": document["material_class"],
        "example_only": document["material_class"] != "real_recorded" or document.get("example_only", True),
        "status": "candidate", "operating_envelope_id": document["operating_envelope_id"],
        "evidence_hashes": {"calibration_rows": rows_sha256, "fit_config": config_sha256},
        "metrics": {"input_count": len(rows), "eligible_count": sum(r["eligible"] for r in rows),
                    "fitted_count": sum(b["count"] for m in mappings.values() for b in m["bins"]),
                    "interval_mass": coverage, "independent_group_count": len({r["parent_group_id"] for r in rows})},
        "mappings": mappings,
        "limitations": ["Unaccepted candidate; Runtime applies reviewed mapping and envelope policy.",
                       "Intervals are empirical residual quantiles, not a distribution-free coverage guarantee.",
                       "Rows within a parent group are not independent trials."],
    }
    validate_calibration(result, model=model, artifact_sha256=artifact)
    return result


def evaluate_candidate(candidate, document):
    validate_calibration(candidate, model=document["model"],
                         artifact_sha256=document["runtime_artifact_sha256"])
    require(candidate["split_groups"] == document["split_groups"]
            and candidate["dataset_manifest_sha256"] == document["dataset_manifest_sha256"],
            "Evaluation dataset/splits differ from calibration")
    require(candidate["material_class"] == document["material_class"]
            and candidate["example_only"] == (document["material_class"] != "real_recorded"
                                              or document.get("example_only", True)),
            "Evaluation material/example status differs")
    require(candidate["operating_envelope_id"] == document["operating_envelope_id"],
            "Evaluation operating envelope differs")
    for event, mapping in candidate["mappings"].items():
        require(mapping["score_feature"] == document["score_features"].get(event),
                "Evaluation score name/unit mismatch")
    rows = _validate_rows(document, split="test", model=candidate["model"],
                          artifact_sha256=candidate["runtime_artifact_sha256"])
    eligible = [r for r in rows if r["eligible"]]
    evaluated, brier, covered, widths = [], [], 0, []
    for r in eligible:
        mapping = candidate["mappings"].get(r["probability_event"])
        b = lookup_bin(mapping, r["score"]) if mapping and r["score"] is not None else None
        if b is None or r["predicted_balance_db"] is None:
            continue
        correct = _success(r)
        brier.append((b["probability"] - int(correct)) ** 2)
        residual = r["target_balance_db"] - r["predicted_balance_db"]
        lo, hi = b["residual_interval_db"]
        covered += int(lo <= residual <= hi)
        widths.append(hi - lo)
        evaluated.append({"sample_id": r["sample_id"], "event": r["probability_event"],
                          "probability": b["probability"], "event_correct": correct,
                          "residual_db": residual})
    result = {key: copy.deepcopy(candidate[key]) for key in (
        "schema_version", "model", "runtime_artifact_sha256", "git_sha", "config_sha256",
        "dataset_manifest_sha256", "split_groups", "material_class", "example_only")}
    result.update(record_type="BenchmarkResult", status="evaluated", evaluation_split="test",
                  calibration_id=candidate["calibration_id"], metrics={
                      "eligible_count": len(eligible), "evaluated_count": len(evaluated),
                      "coverage": len(evaluated) / len(eligible) if eligible else None,
                      "brier_score": float(np.mean(brier)) if brier else None,
                      "interval_covered_count": covered,
                      "interval_coverage": covered / len(evaluated) if evaluated else None,
                      "mean_interval_width_db": float(np.mean(widths)) if widths else None,
                  }, rows=evaluated)
    validate_result_record(result, model=candidate["model"],
                           artifact_sha256=candidate["runtime_artifact_sha256"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("fit", "evaluate"))
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "fit":
        require(args.config is not None, "Fit config required")
        report = fit_candidate(read_json(args.rows), read_json(args.config),
                               rows_sha256=sha256_file(args.rows), config_sha256=sha256_file(args.config))
    else:
        require(args.candidate is not None, "Calibration candidate required")
        report = evaluate_candidate(read_json(args.candidate), read_json(args.rows))
        report["evidence_hashes"] = {"evaluation_rows": sha256_file(args.rows),
                                     "calibration_candidate": sha256_file(args.candidate)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
