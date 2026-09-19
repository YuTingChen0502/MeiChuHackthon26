"""Validation/lookup of ML-internal calibration metadata, not confidence policy."""
from __future__ import annotations

import math

from analyzers.bundle_validation import require, sha, validate_result_record

EVENTS = {"joint_anomaly_numeric_correct", "normal_within_envelope"}
ENDPOINT_POLICY = "left_closed_right_open_last_closed"


def validate_calibration(record, *, model, artifact_sha256, declared_features=None):
    validate_result_record(record, model=model, artifact_sha256=artifact_sha256)
    require(record["record_type"] == "CalibrationCandidate", "Expected calibration candidate")
    require(record.get("status") == "candidate", "Calibration metadata cannot approve itself")
    require(type(record.get("example_only")) is bool, "Calibration example_only required")
    require(record["material_class"] == "real_recorded" or record["example_only"],
            "Synthetic/unknown calibration must be example-only")
    require(isinstance(record.get("calibration_id"), str) and record["calibration_id"],
            "calibration_id required")
    require(isinstance(record.get("operating_envelope_id"), str) and record["operating_envelope_id"],
            "Declared operating envelope identity required")
    evidence = record.get("evidence_hashes")
    require(isinstance(evidence, dict) and evidence, "Calibration evidence hashes required")
    for value in evidence.values():
        sha(value)
    mappings = record.get("mappings")
    require(isinstance(mappings, dict) and mappings and set(mappings) <= EVENTS,
            "Unknown/missing calibration event mapping")
    for event, mapping in mappings.items():
        require(set(mapping) == {"magnitude_tolerance_db", "score_feature", "endpoint_policy",
                                 "interval_semantics", "bins"}, "Invalid calibration mapping fields")
        require(mapping["magnitude_tolerance_db"] == 2.0, "Unsupported calibration correctness tolerance")
        feature = mapping["score_feature"]
        require(set(feature) == {"name", "unit"} and all(isinstance(v, str) and v for v in feature.values()),
                "Invalid calibration score feature")
        if declared_features is not None:
            require(feature in declared_features, "Calibration uses undeclared score name/unit")
        require(mapping["endpoint_policy"] == ENDPOINT_POLICY, "Unknown bin endpoint policy")
        require(mapping["interval_semantics"] == "true_balance_minus_predicted_balance",
                "Invalid interval residual convention")
        bins = mapping["bins"]
        require(isinstance(bins, list) and bins, "Calibration mapping requires populated bins")
        previous = None
        for b in bins:
            require(set(b) == {"lower", "upper", "count", "success_count", "probability",
                               "residual_interval_db"}, "Invalid calibration bin fields")
            for key in ("lower", "upper", "probability"):
                require(type(b[key]) in (int, float) and math.isfinite(b[key]), "Nonfinite bin value")
            require(b["lower"] < b["upper"] and (previous is None or b["lower"] >= previous),
                    "Overlapping/unordered score bins")
            previous = b["upper"]
            require(type(b["count"]) is int and b["count"] > 0
                    and type(b["success_count"]) is int and 0 <= b["success_count"] <= b["count"],
                    "Unsupported calibration bin count")
            require(0 <= b["probability"] <= 1, "Probability outside [0,1]")
            interval = b["residual_interval_db"]
            require(isinstance(interval, list) and len(interval) == 2
                    and all(type(x) in (int, float) and math.isfinite(x) for x in interval)
                    and interval[0] <= interval[1], "Invalid residual interval")
    return record


def lookup_bin(mapping, score):
    """Return a metadata bin or None. Runtime owns acceptance/threshold decisions."""
    if type(score) not in (int, float) or not math.isfinite(score):
        return None
    bins = mapping["bins"]
    for index, b in enumerate(bins):
        if b["lower"] <= score < b["upper"] or (
                index == len(bins) - 1 and score == b["upper"]):
            return b
    return None
