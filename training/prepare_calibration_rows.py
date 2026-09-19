"""Convert measured analyzer outputs and explicit event labels into calibration rows."""
import argparse
import copy
import json
from pathlib import Path

from analyzers.bundle_validation import read_json, require, validate_result_record
from analyzers.calibration_metadata import EVENTS
from analyzers.bundle_validation import sha256_file


def prepare_rows(report, labels, settings):
    validate_result_record(report, model=report["model"],
                           artifact_sha256=report["runtime_artifact_sha256"])
    require(report["record_type"] == "BenchmarkResult"
            and report["evaluation_split"] in {"calibration", "test"}, "Held-out predictions required")
    require(isinstance(settings.get("label_procedure"), str) and settings["label_procedure"],
            "Explicit event label procedure required")
    features = settings["score_features"]
    require(features and set(features) <= EVENTS, "Event score declarations required")
    outputs = {x["case_id"]: x for x in report["outputs"]}
    predictions = {(x["pair_id"], x["instrument_id"]): x for x in report["rows"]}
    require(len(outputs) == len(report["outputs"]) and len(predictions) == len(report["rows"]),
            "Duplicate prediction identifiers")
    require(isinstance(labels, list) and labels, "Explicit event labels required")
    rows, seen = [], set()
    for label in labels:
        key = (label["pair_id"], label["instrument_id"])
        event = label["probability_event"]
        require(event in features and (*key, event) not in seen, "Unknown or duplicate event label")
        seen.add((*key, event))
        require(key in predictions and key[0] in outputs, "Label has no measured prediction")
        for k in ("eligible", "attribution_correct", "target_within_normal_envelope"):
            require(type(label[k]) is bool, "Explicit event truth/eligibility required")
        output = outputs[key[0]]
        evidence = next((x for x in output["evidence"]["measurements"] if x["instrument_id"] == key[1]), None)
        require(evidence is not None, "Prediction missing instrument evidence")
        feature = features[event]
        matches = [x for x in evidence["uncertainty_features"]
                   if x["name"] == feature["name"] and x["unit"] == feature["unit"]]
        require(len(matches) <= 1, "Ambiguous calibration feature")
        predicted = predictions[key]
        require(not label["eligible"] or predicted["true_balance_db"] is not None, "Numeric ground truth required for calibration event")
        rows.append({
            "sample_id": json.dumps([*key, event], separators=(",", ":")),
            "parent_group_id": output["parent_group_id"], "split": output["split"],
            "probability_event": event, "eligible": label["eligible"],
            "attribution_correct": label["attribution_correct"],
            "target_within_normal_envelope": label["target_within_normal_envelope"],
            "target_balance_db": predicted["true_balance_db"],
            "predicted_balance_db": predicted["predicted_balance_db"],
            "score": matches[0]["value"] if matches else None,
        })
    expected = {(pair, instrument, event) for pair, instrument in predictions for event in features}
    require(seen == expected, "Event labels must cover the full measured population; declare ineligible rows explicitly")
    result = {k: copy.deepcopy(report[k]) for k in (
        "schema_version", "model", "runtime_artifact_sha256", "git_sha", "dataset_manifest_sha256",
        "split_groups", "material_class", "example_only")}
    result.update(record_type="CalibrationRows", operating_envelope_id=settings["operating_envelope_id"],
                  label_procedure=settings["label_procedure"], score_features=copy.deepcopy(features), rows=rows)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare_rows(read_json(args.report), read_json(args.labels), read_json(args.settings))
    result["evidence_hashes"] = {k: sha256_file(getattr(args, k)) for k in ("report", "labels", "settings")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
