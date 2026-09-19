"""Focused interface compatibility tests; no product handlers or inference mocks."""

import copy
import json
import types
import unittest
from pathlib import Path
from typing import Literal, get_args, get_origin, get_type_hints, is_typeddict

from jsonschema import Draft202012Validator, ValidationError

from core.contracts import analyzer
from core.contracts.validation import (
    ANALYZER, PUBLIC, WIRE, SETUP, SCHEMAS, baseline_binding, event_binding,
    reference_binding, validate_analyzer_pair, validate_command_binding,
    validate_event, validate_record, validate_response, validate_snapshot,
)


FIXTURES = json.loads((Path(__file__).resolve().parents[3] /
                       "contracts/examples/pa_shared_v1.json").read_text(encoding="utf-8"))


def example(name):
    return copy.deepcopy(FIXTURES[name])


def command_for(snapshot, action, payload=None):
    return {
        "record_type": "SessionCommand", "schema_version": "1.0",
        "session_id": snapshot["session_id"], "idempotency_key": "test-command-1",
        "expected_state_version": snapshot["state_version"],
        "reference": reference_binding(snapshot["active_reference"]),
        "baseline": baseline_binding(snapshot["active_baseline"]),
        "event": event_binding(snapshot["incident"]),
        "action": action, "payload": {} if payload is None else payload,
    }


def with_adjustment():
    snapshot = example("rehearsal_snapshot")
    snapshot["song"]["workflow_state"] = "PA_ADJUSTING"
    snapshot["incident_state"] = "adjusting"
    snapshot["adjustment"] = {
        "adjustment_id": "adjustment-1", "event": None,
        "target": {"target_kind": "reference", "reference": reference_binding(snapshot["active_reference"]),
                   "baseline": None},
        "clock_id": "clock-1", "started_monotonic_s": 40,
        "completed_monotonic_s": None, "verification_not_before_monotonic_s": None,
    }
    return snapshot


def with_incident():
    snapshot = example("live_snapshot")
    snapshot["song"]["workflow_state"] = "LIVE_ANOMALY"
    snapshot["incident_state"] = "active"
    target = example("analyzer_context")["target"]
    event = {
        "record_type": "AnomalyEvent", "schema_version": "1.0", "event_id": "event-1",
        "session_id": "session-1", "instrument_ids": ["guitar"], "direction": "too_loud",
        "onset_monotonic_s": 34, "confirmed_monotonic_s": 36, "baseline_id": "baseline-1",
        "reference_id": "reference-1", "evidence_frame_ids": ["frame-1"], "state": "active",
        "confidence": {"record_type": "ConfidenceState", "schema_version": "1.0",
                       "calibration_status": "calibrated", "calibration_id": "illustrative-only",
                       "probability_event": "joint_anomaly_numeric_correct", "magnitude_tolerance_db": 2,
                       "probability": 0.95, "prediction_interval_db": [3, 5], "abstained": False, "reasons": []},
    }
    snapshot["incident"] = {"event": event, "event_version": 1, "target": target}
    return snapshot


def normalized_union(shapes):
    return ("union", tuple(sorted(shapes, key=repr)))


def schema_shape(schema):
    """Structural type view; numeric constraints/conditional masks are tested separately."""
    if "$ref" in schema:
        identity, pointer = schema["$ref"].split("#")
        value = SCHEMAS[identity]
        for key in pointer.strip("/").split("/"):
            value = value[key]
        return schema_shape(value)
    if "oneOf" in schema:
        return normalized_union([schema_shape(item) for item in schema["oneOf"]])
    if "const" in schema:
        return ("literal", (schema["const"],))
    if "enum" in schema:
        return ("literal", tuple(sorted(schema["enum"], key=repr)))
    if schema["type"] == "object":
        return ("object", tuple(sorted((key, schema_shape(value)) for key, value in schema["properties"].items())))
    if schema["type"] == "array":
        return ("array", schema_shape(schema["items"]))
    return schema["type"]


def python_shape(annotation):
    if is_typeddict(annotation):
        return ("object", tuple(sorted((key, python_shape(value)) for key, value in get_type_hints(annotation).items())))
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is types.UnionType:
        return normalized_union([python_shape(item) for item in args])
    if origin is Literal:
        return ("literal", tuple(sorted(args, key=repr)))
    if origin is list:
        return ("array", python_shape(args[0]))
    return {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}[annotation]


class SharedContractTests(unittest.TestCase):
    def test_all_schemas_are_valid_draft_2020_12(self):
        self.assertEqual({PUBLIC, ANALYZER, WIRE, SETUP}, set(SCHEMAS))
        for schema in SCHEMAS.values():
            Draft202012Validator.check_schema(schema)

    def test_python_types_match_analyzer_schema_recursively(self):
        for name in ("AnalyzerContext", "AnalyzerEvidence"):
            self.assertEqual(schema_shape(SCHEMAS[ANALYZER]["$defs"][name]),
                             python_shape(getattr(analyzer, name)), name)
        for name, value in vars(analyzer).items():
            if is_typeddict(value):
                self.assertFalse(value.__optional_keys__, name)

    def test_shared_examples_resolve_local_references(self):
        for mode in ("source_levels", "source_level_deltas"):
            validate_analyzer_pair(example("analyzer_context"), example(mode))
        for name in ("rehearsal_snapshot", "live_snapshot"):
            validate_snapshot(example(name))
        validate_command_binding(example("accept_command"), example("rehearsal_snapshot"))
        validate_response(example("accept_response"))
        validate_event(example("snapshot_event"))

    def test_evidence_modes_cannot_be_mixed_or_claim_centered_values(self):
        evidence = example("source_level_deltas")
        for field in ("source_level_db", "balance_deviation_db"):
            bad = copy.deepcopy(evidence)
            bad["measurements"][0][field] = 4
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_record(bad, ANALYZER)
        evidence["units"] = "dBFS_rms"
        with self.assertRaises(ValidationError):
            validate_record(evidence, ANALYZER)

    def test_analyzer_cannot_publish_downstream_state_confidence_or_actions(self):
        for field in ("status", "confidence", "recommendation", "action"):
            evidence = example("source_levels")
            evidence["measurements"][0][field] = "normal"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_record(evidence, ANALYZER)

    def test_invalid_and_inactive_evidence_requires_null_and_reason(self):
        evidence = example("source_level_deltas")
        item = evidence["measurements"][0]
        item.update(activity="inactive", observability="not_observable", validity="invalid")
        with self.assertRaises(ValidationError):
            validate_record(evidence, ANALYZER)
        item.update(source_level_delta_db=None, reason_codes=["source_inactive"])
        validate_analyzer_pair(example("analyzer_context"), evidence)
        item["validity"] = "valid"
        with self.assertRaises(ValidationError):
            validate_record(evidence, ANALYZER)

    def test_context_and_evidence_identity_must_match(self):
        for field, key in (("model", "model_bundle_id"), ("model", "frontend_id"),
                           ("model", "execution_profile_id"), ("model", "level_scale_id"),
                           ("observation", "clock_id"), ("observation", "window_id")):
            evidence = example("source_level_deltas")
            evidence[field][key] = "mismatch"
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_analyzer_pair(example("analyzer_context"), evidence)
        evidence = example("source_levels")
        evidence["target"]["baseline"]["baseline_version"] = 2
        with self.assertRaises(ValueError):
            validate_analyzer_pair(example("analyzer_context"), evidence)

    def test_configured_ids_and_families_are_exact(self):
        for change in ("missing", "duplicate", "wrong_family"):
            evidence = example("source_levels")
            if change == "missing":
                evidence["measurements"].pop()
            elif change == "duplicate":
                evidence["measurements"].append(copy.deepcopy(evidence["measurements"][0]))
            else:
                evidence["measurements"][0]["family"] = "other"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_analyzer_pair(example("analyzer_context"), evidence)

    def test_guided_probe_uses_same_contract_without_assuming_activity(self):
        context = example("analyzer_context")
        context.update(observation_purpose="guided_probe", probe_instrument_id="guitar")
        evidence = example("source_level_deltas")
        evidence["measurements"][0].update(activity="unknown", observability="unknown",
                                         validity="invalid", source_level_delta_db=None,
                                         reason_codes=["insufficient_evidence"])
        validate_analyzer_pair(context, evidence)
        context["probe_instrument_id"] = "unconfigured"
        with self.assertRaises(ValueError):
            validate_analyzer_pair(context, evidence)

    def test_valid_matched_evidence_requires_match_and_validated_regime(self):
        context, evidence = example("analyzer_context"), example("source_levels")
        evidence["matched_context_window_id"] = None
        with self.assertRaises(ValueError):
            validate_analyzer_pair(context, evidence)
        context["comparison_regime"] = evidence["comparison_regime"] = "unvalidated"
        with self.assertRaises(ValueError):
            validate_analyzer_pair(context, evidence)

    def test_nonfinite_and_reversed_spans_are_rejected(self):
        evidence = example("source_level_deltas")
        evidence["measurements"][0]["source_level_delta_db"] = float("nan")
        with self.assertRaises(ValueError):
            validate_record(evidence, ANALYZER)
        context, evidence = example("analyzer_context"), example("source_levels")
        context["observation"]["sample_end"] = context["observation"]["sample_start"]
        evidence["observation"] = copy.deepcopy(context["observation"])
        with self.assertRaises(ValueError):
            validate_analyzer_pair(context, evidence)

    def test_commands_have_distinct_payloads_and_server_owned_time(self):
        snapshot = with_adjustment()
        for action, payload in (("start_adjustment", {}),
                                ("complete_adjustment", {"adjustment_id": "adjustment-1"}),
                                ("recheck", {"adjustment_id": None}),
                                ("recheck", {"adjustment_id": "adjustment-1"}),
                                *[(name, {}) for name in ("pause", "resume", "stop", "dismiss", "start_live")]):
            with self.subTest(action=action):
                validate_command_binding(command_for(snapshot, action, payload), snapshot)
        command = command_for(snapshot, "complete_adjustment", {"adjustment_id": "adjustment-1",
                                                               "completed_monotonic_s": 42})
        with self.assertRaises(ValidationError):
            validate_record(command, WIRE)
        command = command_for(snapshot, "accept_baseline")
        with self.assertRaises(ValidationError):
            validate_record(command, WIRE)

    def test_command_versions_and_bindings_cannot_drift(self):
        snapshot = example("live_snapshot")
        for change in ("state", "reference", "baseline", "event", "session"):
            command = command_for(snapshot, "pause")
            if change == "state":
                command["expected_state_version"] -= 1
            elif change == "reference":
                command["reference"]["source_asset_hash"] = "other-content"
            elif change == "baseline":
                command["baseline"]["baseline_version"] += 1
            elif change == "event":
                command["event"] = {"event_id": "old-event", "event_version": 1}
            else:
                command["session_id"] = "other-session"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_command_binding(command, snapshot)

    def test_commands_require_idempotency_and_adjustment_binding(self):
        command = example("accept_command")
        del command["idempotency_key"]
        with self.assertRaises(ValidationError):
            validate_record(command, WIRE)
        snapshot = with_adjustment()
        command = command_for(snapshot, "complete_adjustment", {"adjustment_id": "old-adjustment"})
        with self.assertRaises(ValueError):
            validate_command_binding(command, snapshot)

    def test_acceptance_interval_clock_and_order(self):
        for change in ("clock", "span"):
            command = example("accept_command")
            if change == "clock":
                command["payload"]["interval"]["clock_id"] = "old-clock"
            else:
                command["payload"]["interval"]["sample_start"] = 1440000
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_command_binding(command, example("rehearsal_snapshot"))

    def test_live_requires_baseline_and_snapshot_ids_must_agree(self):
        snapshot = example("rehearsal_snapshot")
        snapshot["session_mode"] = "live"
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)
        snapshot = example("live_snapshot")
        snapshot["session_mode"] = "rehearsal"
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)
        snapshot = example("live_snapshot")
        snapshot["active_baseline"]["song_id"] = "other-song"
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_adjustment_completion_and_cutoff_are_paired_and_ordered(self):
        snapshot = with_adjustment()
        snapshot["adjustment"].update(completed_monotonic_s=42, verification_not_before_monotonic_s=43)
        validate_snapshot(snapshot)
        for completion, cutoff in ((42, None), (None, 43), (39, 43), (42, 41)):
            bad = copy.deepcopy(snapshot)
            bad["adjustment"].update(completed_monotonic_s=completion, verification_not_before_monotonic_s=cutoff)
            with self.subTest(completion=completion, cutoff=cutoff), self.assertRaises(ValueError):
                validate_snapshot(bad)

    def test_incident_version_advances_without_rewriting_adjustment_binding(self):
        snapshot = with_incident()
        validate_snapshot(snapshot)
        snapshot["adjustment"] = {
            "adjustment_id": "adjustment-1", "event": event_binding(snapshot["incident"]),
            "target": copy.deepcopy(snapshot["incident"]["target"]), "clock_id": "clock-1",
            "started_monotonic_s": 40, "completed_monotonic_s": 42,
            "verification_not_before_monotonic_s": 43,
        }
        snapshot["incident"]["event_version"] = 2
        snapshot["incident"]["event"]["state"] = "acknowledged"
        validate_snapshot(snapshot)
        command = command_for(snapshot, "recheck", {"adjustment_id": "adjustment-1"})
        validate_command_binding(command, snapshot)
        command["event"]["event_version"] = 1
        with self.assertRaises(ValueError):
            validate_command_binding(command, snapshot)
        snapshot["adjustment"]["event"]["event_version"] = 3
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_incident_comparison_target_keeps_exact_baseline_version(self):
        snapshot = with_incident()
        snapshot["incident"]["target"]["baseline"]["baseline_version"] = 2
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot)

    def test_event_cursors_and_response_status_are_unambiguous(self):
        event = example("snapshot_event")
        event["event_sequence"] += 1
        with self.assertRaises(ValueError):
            validate_event(event)
        response = example("accept_response")
        response["http_status"] = 409
        with self.assertRaises(ValidationError):
            validate_response(response)
        response.update(outcome="rejected", error={"code": "stale_state_version",
                        "message": "Refresh the session.", "retryable": True})
        validate_response(response)

    def test_existing_abstention_and_verification_semantics_remain_enforced(self):
        confidence = {"record_type": "ConfidenceState", "schema_version": "1.0",
                      "calibration_status": "uncalibrated", "calibration_id": None,
                      "probability_event": "not_available", "magnitude_tolerance_db": 2,
                      "probability": None, "prediction_interval_db": None,
                      "abstained": True, "reasons": ["source_inactive"]}
        state = {"record_type": "InstrumentState", "schema_version": "1.0", "instrument_id": "guitar",
                 "family": "guitar", "activity": "inactive", "presence_probability": None,
                 "source_level_delta_db": None, "balance_deviation_db": None,
                 "status": "inactive", "confidence": confidence, "tone": None}
        validate_record(state, PUBLIC)
        state.update(balance_deviation_db=-20, status="too_quiet")
        with self.assertRaises(ValidationError):
            validate_record(state, PUBLIC)
        verification = {"record_type": "VerificationResult", "schema_version": "1.0",
                        "verification_id": "verification-1", "event_id": "event-1",
                        "adjustment_id": "adjustment-1", "baseline_id": "baseline-1", "baseline_version": 1,
                        "adjustment_completed_monotonic_s": 42, "first_evidence_sample_start_monotonic_s": 43,
                        "evidence_frame_ids": ["frame-1"], "instrument_id": "guitar",
                        "before_balance_db": 4, "after_balance_db": None,
                        "source_observable": False, "outcome": "inconclusive", "reason_codes": ["source_inactive"]}
        validate_record(verification, PUBLIC)
        verification.update(outcome="recovered", after_balance_db=0)
        with self.assertRaises(ValidationError):
            validate_record(verification, PUBLIC)


if __name__ == "__main__":
    unittest.main()
