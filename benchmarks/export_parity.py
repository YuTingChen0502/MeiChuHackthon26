"""Backend-neutral export callback and strict eager/export evidence parity."""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import tempfile
from pathlib import Path

from analyzers.bundle_validation import contained_file, read_json, require, validate_bundle, validate_result_record
from analyzers.bundles import BackendRegistry
from core.contracts.validation import validate_analyzer_pair
from analyzers.bundle_validation import sha256_file


def export_artifact(bundle_path, *, registry, destination):
    bundle = validate_bundle(Path(bundle_path))
    exporter = registry.exporter(bundle.manifest["backend"]["adapter_id"])
    destination = Path(destination).resolve()
    require(not destination.exists(), "Refusing to overwrite export destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".export-", dir=destination.parent))
    backend = None
    publish = None
    try:
        backend = registry.instantiate(bundle)
        returned = Path(exporter(backend, stage))
        require(returned.is_absolute() and returned.is_relative_to(stage),
                "Exporter must return an absolute file path inside staging")
        artifact = contained_file(stage, returned.relative_to(stage).as_posix())
        require(artifact.name != "export-receipt.json", "Reserved export filename")
        digest = sha256_file(artifact)
        receipt = {
            "record_type": "ExportReceipt", "schema_version": "1.0",
            "status": "UNVERIFIED_EXPORT", "source_manifest_sha256": bundle.manifest_sha256,
            "source_checkpoint_sha256": bundle.manifest["files"][bundle.manifest["components"]["checkpoint"]]["sha256"],
            "artifact": artifact.name, "artifact_sha256": digest,
            "model": bundle.manifest["model"], "parity_accepted": False,
        }
        publish = Path(tempfile.mkdtemp(prefix=".export-", dir=destination.parent))
        shutil.copyfile(artifact, publish / artifact.name)
        (publish / "export-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        os.rename(publish, destination)
        return receipt
    finally:
        try:
            if backend is not None:
                backend.close()
        finally:
            for temporary in (stage, publish):
                if temporary is not None and temporary.exists():
                    require(temporary.resolve().parent == destination.parent and temporary.name.startswith(".export-"),
                            "Refusing unsafe export staging cleanup")
                    shutil.rmtree(temporary)


def compare_outputs(reference, candidate, *, atol_db, rtol=0.0):
    require(type(atol_db) in (int, float) and math.isfinite(atol_db) and atol_db >= 0
            and type(rtol) in (int, float) and math.isfinite(rtol) and rtol >= 0,
            "Invalid parity tolerances")
    for report in (reference, candidate):
        validate_result_record(report, model=report["model"],
                               artifact_sha256=report["runtime_artifact_sha256"])
        require(report["record_type"] == "BenchmarkResult" and report["outputs"], "Parity needs evaluated outputs")
    for key in ("frontend_id", "taxonomy_id", "level_scale_id"):
        require(reference["model"][key] == candidate["model"][key], "Parity frontend/taxonomy/scale mismatch")
    for key in ("dataset_manifest_sha256", "split_groups", "evaluation_split", "material_class", "example_only"):
        require(reference[key] == candidate[key], "Parity evaluated different populations")
    def index(report):
        entries = {x["case_id"]: x for x in report["outputs"]}
        require(len(entries) == len(report["outputs"]), "Duplicate parity case")
        return entries
    left, right = index(reference), index(candidate)
    require(set(left) == set(right), "Parity case sets differ")
    failures, max_error, comparisons = [], 0.0, 0
    for key in left:
        a, b = left[key], right[key]
        for field in ("pcm_sha256", "reference_pcm_sha256", "instrument_config", "target",
                      "comparison_regime", "split", "parent_group_id"):
            require(a[field] == b[field], f"Parity inputs differ: {field}")
        require(a["context"]["model"] == reference["model"] and b["context"]["model"] == candidate["model"],
                "Parity report/output model mismatch")
        validate_analyzer_pair(a["context"], a["evidence"])
        validate_analyzer_pair(b["context"], b["evidence"])
        require(a["evidence"]["evidence_mode"] == b["evidence"]["evidence_mode"], "Parity evidence modes differ")
        ma = {x["instrument_id"]: x for x in a["evidence"]["measurements"]}
        mb = {x["instrument_id"]: x for x in b["evidence"]["measurements"]}
        for instrument in ma:
            x, y = ma[instrument], mb[instrument]
            structural = ("activity", "observability", "validity", "family", "reason_codes")
            if any(x[field] != y[field] for field in structural):
                failures.append({"case_id": key, "instrument_id": instrument, "reason": "mask_or_semantics_changed"})
                continue
            numerical = [field for field in ("source_level_delta_db", "source_level_db", "target_source_level_db")
                         if field in x and x[field] is not None]
            ux = {(f["name"], f["unit"]): f["value"] for f in x["uncertainty_features"]}
            uy = {(f["name"], f["unit"]): f["value"] for f in y["uncertainty_features"]}
            if set(ux) != set(uy):
                failures.append({"case_id": key, "instrument_id": instrument, "reason": "uncertainty_features_changed"})
                continue
            pairs = [(x[field], y[field]) for field in numerical] + [(ux[f], uy[f]) for f in ux]
            for old, new in pairs:
                comparisons += 1
                error = abs(old - new)
                max_error = max(max_error, error)
                if error > atol_db + rtol * abs(old):
                    failures.append({"case_id": key, "instrument_id": instrument, "reason": "numerical_tolerance"})
    result = {field: copy.deepcopy(candidate[field]) for field in (
        "schema_version", "model", "runtime_artifact_sha256", "git_sha", "config_sha256",
        "dataset_manifest_sha256", "split_groups", "material_class", "example_only")}
    result.update(record_type="ExportParityReport", status="evaluated",
                  reference_artifact_sha256=reference["runtime_artifact_sha256"],
                  tolerances={"absolute": atol_db, "relative": rtol},
                  metrics={"passed": not failures and comparisons > 0, "case_count": len(left),
                           "numerical_comparisons": comparisons, "max_absolute_error": max_error,
                           "failure_count": len(failures)}, failures=failures)
    validate_result_record(result, model=candidate["model"], artifact_sha256=candidate["runtime_artifact_sha256"])
    return result


def main(argv=None, *, registry=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    export = sub.add_parser("export")
    export.add_argument("--bundle", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    parity = sub.add_parser("compare")
    parity.add_argument("--reference", type=Path, required=True)
    parity.add_argument("--candidate", type=Path, required=True)
    parity.add_argument("--atol-db", type=float, required=True)
    parity.add_argument("--rtol", type=float, default=0.0)
    parity.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "export":
        print(json.dumps(export_artifact(args.bundle, registry=registry or BackendRegistry(),
                                         destination=args.destination)))
    else:
        report = compare_outputs(read_json(args.reference), read_json(args.candidate),
                                 atol_db=args.atol_db, rtol=args.rtol)
        report["evidence_hashes"] = {"reference": sha256_file(args.reference), "candidate": sha256_file(args.candidate)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return 0 if report["metrics"]["passed"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
