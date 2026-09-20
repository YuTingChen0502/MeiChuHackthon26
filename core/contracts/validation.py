"""Shared structural and identity invariants, not a command handler/state machine.

All schema references resolve from the repository. No network retrieval is used.
Application owners must implement the lifecycle rules in PA_SHARED_INTERFACES_V1.md.
"""

import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


CONTRACT_DIR = Path(__file__).resolve().parents[2] / "contracts"
PUBLIC = "urn:pa-controller:contracts:1.0"
ANALYZER = "urn:pa-controller:analyzer:1.0"
WIRE = "urn:pa-controller:session-wire:1.0"
SETUP = "urn:pa-controller:setup-wire:1.0"
SCHEMAS = {
    document["$id"]: document
    for path in sorted(CONTRACT_DIR.glob("*.schema.json"))
    for document in [json.loads(path.read_text(encoding="utf-8-sig"))]
}
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(document)) for name, document in SCHEMAS.items()
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value):
    if isinstance(value, float):
        require(math.isfinite(value), "NaN and infinity are not contract numbers")
    elif isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


def validate_record(record, schema_id, definition=None):
    _finite(record)
    schema = SCHEMAS[schema_id] if definition is None else {
        "$ref": f"{schema_id}#/$defs/{definition}"
    }
    Draft202012Validator(schema, registry=REGISTRY).validate(record)


def _span(window):
    require(window["sample_end"] > window["sample_start"], "Empty/reversed sample span")
    if "capture_end_monotonic_s" in window:
        duration = (window["sample_end"] - window["sample_start"]) / window["sample_rate_hz"]
        require(window["capture_end_monotonic_s"] >= duration, "Window starts before clock origin")


def validate_analyzer_pair(context, evidence):
    validate_record(context, ANALYZER, "AnalyzerContext")
    validate_record(evidence, ANALYZER, "AnalyzerEvidence")
    _span(context["observation"])
    for field in ("observation", "model", "target", "comparison_regime",
                  "model_specific_context_asset"):
        require(context[field] == evidence[field], f"Analyzer binding differs: {field}")
    config = context["instrument_config"]
    require(config["instrument_config_version"] == evidence["instrument_config_version"],
            "Instrument configuration version mismatch")
    configured = {item["instrument_id"]: item["family"] for item in config["instruments"]}
    require(len(configured) == len(config["instruments"]), "Duplicate configured instrument")
    measured = {item["instrument_id"]: item["family"] for item in evidence["measurements"]}
    require(len(measured) == len(evidence["measurements"]), "Duplicate evidence instrument")
    require(configured == measured, "Evidence must cover each configured ID/family exactly once")
    if context["probe_instrument_id"] is not None:
        require(context["probe_instrument_id"] in configured, "Unknown probe instrument")
    for item in evidence["measurements"]:
        names = [feature["name"] for feature in item["uncertainty_features"]]
        require(len(names) == len(set(names)), "Duplicate uncertainty feature")
        if item["validity"] == "valid":
            require(context["comparison_regime"] != "unvalidated",
                    "Unvalidated comparison cannot provide valid numerical evidence")
            if context["comparison_regime"] == "matched_excerpt":
                require(evidence["matched_context_window_id"] is not None,
                        "Matched-excerpt evidence needs a matched context window")


def reference_binding(profile):
    if profile is None:
        return None
    return {key: profile[key] for key in ("reference_id", "source_asset_hash")}


def baseline_binding(profile):
    if profile is None:
        return None
    return {"baseline_id": profile["baseline_id"], "baseline_version": profile["version"]}


def event_binding(incident):
    if incident is None:
        return None
    return {"event_id": incident["event"]["event_id"], "event_version": incident["event_version"]}


def validate_snapshot(snapshot):
    validate_record(snapshot, WIRE, "SessionSnapshot")
    song, reference, baseline = (snapshot[k] for k in ("song", "active_reference", "active_baseline"))
    require(song["reference_id"] == (reference["reference_id"] if reference else None),
            "Song/reference binding mismatch")
    require(song["baseline_id"] == (baseline["baseline_id"] if baseline else None),
            "Song/baseline binding mismatch")
    for profile in (reference, baseline):
        if profile is not None:
            require(profile["song_id"] == song["song_id"], "Profile belongs to another song")
    if baseline is not None:
        require(reference is not None and baseline["reference_id"] == reference["reference_id"],
                "Baseline/reference mismatch")
    live_reference = snapshot.get("workflow_policy") == "live_reference_v1"
    if live_reference:
        require(reference is not None and baseline is None, "Live reference policy requires reference without baseline")
    elif snapshot["session_mode"] == "live":
        require(baseline is not None, "Live requires an accepted baseline")
    workflow = song["workflow_state"]
    if workflow in ("LIVE_MONITORING", "LIVE_ANOMALY", "VERIFY_RECOVERY"):
        require(snapshot["session_mode"] == "live", "Live workflow/mode mismatch")
    if workflow in ("REHEARSAL", "ANOMALY_DETECTED", "RECHECK", "ACCEPT_BASELINE"):
        require(snapshot["session_mode"] == "rehearsal", "Rehearsal workflow/mode mismatch")
    incident = snapshot["incident"]
    if incident is not None:
        event, target = incident["event"], incident["target"]
        if live_reference:
            require(target["target_kind"] == "reference", "Live reference incident cannot target baseline")
        require(event["session_id"] == snapshot["session_id"], "Incident session mismatch")
        require(target["reference"] == reference_binding(reference), "Incident reference mismatch")
        require(event["reference_id"] == target["reference"]["reference_id"], "Event reference mismatch")
        expected = baseline_binding(baseline) if target["target_kind"] == "baseline" else None
        require(target["baseline"] == expected, "Incident baseline/version mismatch")
        require(event["baseline_id"] == (expected["baseline_id"] if expected else None),
                "Event baseline mismatch")
    adjustment = snapshot["adjustment"]
    if adjustment is not None:
        if live_reference:
            require(adjustment["target"]["target_kind"] == "reference", "Live reference adjustment cannot target baseline")
        require(adjustment["clock_id"] == snapshot["source"]["clock_id"], "Adjustment clock mismatch")
        if adjustment["event"] is not None:
            current_event = event_binding(incident)
            require(current_event is not None and adjustment["event"]["event_id"] == current_event["event_id"]
                    and adjustment["event"]["event_version"] <= current_event["event_version"],
                    "Adjustment incident mismatch")
        require(adjustment["target"]["reference"] == reference_binding(reference),
                "Adjustment reference mismatch")
        expected = baseline_binding(baseline) if adjustment["target"]["target_kind"] == "baseline" else None
        require(adjustment["target"]["baseline"] == expected, "Adjustment baseline mismatch")
        if incident is not None:
            require(adjustment["target"] == incident["target"], "Adjustment target mismatch")
        completed, cutoff = (adjustment[k] for k in
                             ("completed_monotonic_s", "verification_not_before_monotonic_s"))
        require((completed is None) == (cutoff is None), "Completion/cutoff must be paired")
        if completed is not None:
            require(adjustment["started_monotonic_s"] <= completed <= cutoff,
                    "Adjustment timestamps are out of order")
    frame = snapshot["latest_frame"]
    if frame is not None:
        _span(frame)
        require(frame["session_id"] == snapshot["session_id"], "Frame session mismatch")
    if live_reference:
        capture = snapshot["capture"]
        timing = snapshot.get("analysis_timing")
        if timing is not None:
            require(math.isfinite(timing["snapshot_monotonic_s"]), "Finite snapshot clock required")
        require(capture["clock_id"] == snapshot["source"]["clock_id"], "Capture clock mismatch")
        if capture["state"] in ("switching", "starting", "paused", "stopped", "unavailable"):
            require(not capture["frame_fresh"], "Inactive capture cannot claim a fresh frame")
        if capture["frame_fresh"]:
            require(frame is not None, "Fresh frame flag requires a frame")
            if timing is not None:
                require(math.isfinite(frame["capture_end_monotonic_s"]) and
                        timing["snapshot_monotonic_s"] <=
                        frame["capture_end_monotonic_s"] + timing["result_max_age_s"],
                        "Fresh frame exceeds its result age budget")
        if frame is not None:
            require(frame["baseline_id"] is None and frame["baseline_version"] is None,
                    "Live reference frame cannot bind a baseline")
            require(frame["reference_id"] == reference["reference_id"], "Frame reference mismatch")
            for key in ("clock_id", "input_kind", "input_asset_or_device_id"):
                require(frame[key] == snapshot["source"][key], f"Old source frame: {key}")
            require(frame["analysis_run_id"] == capture["analysis_run_id"], "Old source frame: run")
        seen = set()
        states = {item["instrument_id"]: item for item in frame["instruments"]} if frame else {}
        for item in snapshot["perception"]:
            require(item["instrument_id"] not in seen, "Duplicate perception instrument")
            seen.add(item["instrument_id"])
            if item["numerical_advice_allowed"]:
                require(item["calibration_status"] == "calibrated" and not item["action_abstained"],
                        "Numerical advice requires calibrated actionable confidence")
            if item["frame_id"] is not None:
                require(frame is not None and item["frame_id"] == frame["frame_id"], "Old perception frame")
            hint = item.get("adjustment_hint")
            if hint is not None:
                if timing is not None or "expires_monotonic_s" in hint:
                    require(timing is not None and "expires_monotonic_s" in hint,
                            "Hint expiry requires authoritative timing")
                    deadline = hint["expires_monotonic_s"]
                    require(math.isfinite(deadline) and deadline > timing["snapshot_monotonic_s"],
                            "Expired hint cannot be current")
                    require(frame is not None and deadline <= min(
                        frame["published_monotonic_s"] + timing["hint_hold_s"],
                        frame["capture_end_monotonic_s"] + timing["result_max_age_s"]),
                        "Hint lifetime exceeds its original evidence budget")
                require(item["calibration_status"] == "uncalibrated" and item["action_abstained"]
                        and not item["numerical_advice_allowed"],
                        "Experimental hint bypasses only uncalibrated abstention")
                require(frame is not None and capture["frame_fresh"]
                        and hint["evidence_frame_id"] == item["frame_id"] == frame["frame_id"],
                        "Direction hint requires current fresh evidence")
                quality = frame["quality"]
                require(not quality["stale"] and not quality["dropout"]
                        and quality["clipped_fraction"] == 0 and quality["capture_compatible"]
                        and quality["comparability"] == "comparable",
                        "Unusable audio cannot support a direction hint")
                require(item["state"] in ("detected", "uncertain")
                        and item["activity"] == "active" and item["observability"] == "observable"
                        and item["validity"] == "valid", "Direction hint requires usable source measurement")
                require(frame["identifiability_assumption"] == "majority_active_sources_unchanged"
                        or "reference_delta_without_common_mode" in hint["reason_codes"],
                        "Direction hint requires an explicit estimate basis")
                require(item["instrument_id"] in states
                        and states[item["instrument_id"]]["family"] == item["family"],
                        "Direction hint instrument mismatch")
            if item["state"] in ("detected", "not_heard"):
                require(capture["frame_fresh"] and item["frame_id"] is not None, "Perception requires fresh evidence")
                require(not frame["quality"]["stale"] and not frame["quality"]["dropout"],
                        "Stale/dropout audio cannot establish perception")
                state = states.get(item["instrument_id"])
                require(state is not None and state["family"] == item["family"], "Perception instrument mismatch")
                if item["state"] == "detected":
                    require(item["activity"] == "active" and item["observability"] == "observable"
                            and item["validity"] == "valid", "Detected requires valid observable perception")
                    require(item["family"] not in song["unsupported_families"], "Unsupported family cannot be detected")
                else:
                    require(item["activity"] == "inactive", "Not heard requires inactive evidence")
            state = states.get(item["instrument_id"]) if item["frame_id"] is not None else None
            if state is not None:
                require(item["calibration_status"] == state["confidence"]["calibration_status"]
                        and item["action_abstained"] == state["confidence"]["abstained"],
                        "Perception actionability must match downstream confidence")
    for recommendation in snapshot["recommendations"]:
        require(incident is not None and recommendation["event_id"] == incident["event"]["event_id"],
                "Recommendation must bind the snapshot incident")


def validate_command_binding(command, snapshot):
    """Check a NEW command after the application has checked its idempotency ledger.

An identical retry must return the stored response before checking stale versions.
This helper does not authorize an action or mutate session/baseline state.
"""
    validate_record(command, WIRE, "SessionCommand")
    validate_snapshot(snapshot)
    require(command["session_id"] == snapshot["session_id"], "Command session mismatch")
    require(command["expected_state_version"] == snapshot["state_version"], "Stale state version")
    require(command["reference"] == reference_binding(snapshot["active_reference"]), "Stale reference")
    require(command["baseline"] == baseline_binding(snapshot["active_baseline"]), "Stale baseline")
    require(command["event"] == event_binding(snapshot["incident"]), "Stale incident")
    if command["action"] == "switch_microphone":
        require(snapshot.get("workflow_policy") == "live_reference_v1", "Switch requires live reference policy")
        require(command["payload"]["expected_source_generation"] == snapshot["capture"]["source_generation"],
                "Stale source generation")
    if command["action"] == "accept_baseline":
        _span(command["payload"]["interval"])
        require(command["payload"]["interval"]["clock_id"] == snapshot["source"]["clock_id"],
                "Acceptance interval clock mismatch")
    adjustment_id = command["payload"].get("adjustment_id")
    if adjustment_id is not None:
        require(snapshot["adjustment"] is not None and
                adjustment_id == snapshot["adjustment"]["adjustment_id"], "Stale adjustment")


def validate_response(response):
    validate_record(response, WIRE, "CommandResponse")
    if response["snapshot"] is not None:
        validate_snapshot(response["snapshot"])
        require(response["session_id"] == response["snapshot"]["session_id"], "Response session mismatch")


def validate_event(event):
    validate_record(event, WIRE, "SessionEvent")
    payload = event["payload"]
    if "session_id" in payload:
        require(payload["session_id"] == event["session_id"], "Event session mismatch")
    if payload["record_type"] == "SessionSnapshot":
        validate_snapshot(payload)
        require(payload["event_sequence"] == event["event_sequence"], "Snapshot/event cursor mismatch")
        require(payload["state_version"] == event["state_version"], "Snapshot/event version mismatch")
