"""Compare measured candidates on identical held-out inputs; never choose a winner."""
import argparse
import copy
import json
from pathlib import Path

from analyzers.bundle_validation import read_json, require, validate_result_record
from analyzers.bundle_validation import sha256_file


def compare(reports):
    require(isinstance(reports, list) and len(reports) >= 2, "At least two measured reports required")
    first = reports[0]
    def population(report):
        outputs = report["outputs"]
        require(outputs and len({x["case_id"] for x in outputs}) == len(outputs), "Duplicate/missing cases")
        fields = ("pcm_sha256", "reference_pcm_sha256", "instrument_config", "target",
                  "comparison_regime", "split", "parent_group_id")
        cases = {x["case_id"]: {k: x[k] for k in fields} for x in outputs}
        labels = {(x["pair_id"], x["instrument_id"]): {
            k: x[k] for k in ("true_raw_db", "true_balance_db", "attribution_evaluable")}
            for x in report["rows"]}
        require(len(labels) == len(report["rows"]), "Duplicate metric rows")
        return cases, labels
    expected = population(first)
    for report in reports:
        validate_result_record(report, model=report["model"],
                               artifact_sha256=report["runtime_artifact_sha256"])
        require(report["record_type"] == "BenchmarkResult", "Measured benchmark required")
        for key in ("dataset_manifest_sha256", "split_groups", "evaluation_split",
                    "thresholds", "material_class", "example_only", "experiment"):
            require(report[key] == first[key], "Comparison populations/protocol differ: " + key)
        for key in ("taxonomy_id", "level_scale_id"):
            require(report["model"][key] == first["model"][key], "Comparison semantics differ")
        require(population(report) == expected, "Comparison PCM, labels or contexts differ")
    return {
        "schema_version": "1.0", "record_type": "ArtifactComparison", "status": "diagnostic",
        "decision": "NOT_SELECTED", "dataset_manifest_sha256": first["dataset_manifest_sha256"],
        "split_groups": copy.deepcopy(first["split_groups"]), "evaluation_split": first["evaluation_split"],
        "thresholds": copy.deepcopy(first["thresholds"]), "case_count": len(expected[0]),
        "candidates": [{k: copy.deepcopy(r[k]) for k in
                        ("model", "runtime_artifact_sha256", "metrics", "material_class", "example_only")}
                       for r in reports],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare([read_json(p) for p in args.reports])
    report["evidence_sha256"] = [sha256_file(p) for p in args.reports]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
