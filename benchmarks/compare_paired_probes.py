"""Compare two completed diagnostics only when their actual inputs match."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.paired_metrics import summarize
from training.multitrack_assets import sha256_file


def compare(first: dict, second: dict) -> dict:
    for report in (first, second):
        if report.get("status") != "COMPLETED_DIAGNOSTIC":
            raise ValueError("Both probe reports must be completed")
    if first.get("git_commit") != second.get("git_commit") or not first.get("git_commit"):
        raise ValueError("Comparison requires identical recorded source commits")
    if first["thresholds"] != second["thresholds"]:
        raise ValueError("Comparison thresholds differ")
    for field in ("config_sha256", "manifest_sha256", "pairs"):
        if first["plan"][field] != second["plan"][field]:
            raise ValueError(f"Pair plans differ: {field}")
    def audio_identity(report):
        identities = {}
        for item in report["pair_records"]:
            metadata = item["metadata"]
            pair_id = item["pair_id"]
            if pair_id in identities:
                raise ValueError("Duplicate pair record")
            identities[pair_id] = (
                metadata["reference_mix_sha256_f64le"],
                metadata["observation_mix_sha256_f64le"],
                metadata["raw_source_delta_db"], metadata["valid_source_mask"])
        return identities
    if audio_identity(first) != audio_identity(second):
        raise ValueError("Actual PCM or labels differ between probes")
    def row_identity(report):
        return {(r["pair_id"], r["instrument_id"]): (r["true_raw_db"], r["true_balance_db"], r.get("attribution_evaluable", True))
                for r in report["rows"]}
    if row_identity(first) != row_identity(second):
        raise ValueError("Metric populations or labels differ")
    planned = {(p["pair_id"], key) for p in first["plan"]["pairs"]
               for key in p["instrument_families"]}
    if set(row_identity(first)) != planned:
        raise ValueError("Incomplete metric population")
    if set(audio_identity(first)) != {p["pair_id"] for p in first["plan"]["pairs"]}:
        raise ValueError("Incomplete PCM identity population")
    thresholds = first["thresholds"]
    return {
        "record_type": "CP2MatchedProbeComparison", "schema_version": "1.0",
        "status": "AWAITING_LEAD_DECISION", "git_commit": first["git_commit"],
        "config_sha256": first["plan"]["config_sha256"],
        "manifest_sha256": first["plan"]["manifest_sha256"],
        "thresholds": thresholds,
        "candidates": [{
            "model": report["model"],
            "metrics": summarize(report["rows"], alert_db=thresholds["alert_db"],
                                 missing_penalty_db=thresholds["missing_prediction_penalty_db"]),
            "prediction_seconds_p50": report["prediction_seconds_p50"],
            "prediction_seconds_p95": report["prediction_seconds_p95"],
        } for report in (first, second)],
        "limitations": [
            "Matched diagnostics do not pass Gate B/C automatically.",
            "No confidence/calibration, runtime action, MI300 adaptation or physical claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare(json.loads(args.first.read_text(encoding="utf-8")),
                     json.loads(args.second.read_text(encoding="utf-8")))
    report["input_report_sha256"] = [sha256_file(args.first), sha256_file(args.second)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
