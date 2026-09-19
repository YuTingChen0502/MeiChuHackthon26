"""Convert backend-neutral analyzer evidence into canonical public state records."""

from __future__ import annotations

import statistics
import time

from core.contracts.validation import PUBLIC, validate_analyzer_pair, validate_record

from .quality import hard_gate_reasons


class FrameBuilder:
    def __init__(self, *, anomaly_threshold_db: float = 3.0) -> None:
        self.anomaly_threshold_db = anomaly_threshold_db

    @staticmethod
    def _confidence(*, abstained: bool, reasons: list[str], value: float | None) -> dict:
        calibrated = not abstained
        return {
            "record_type": "ConfidenceState",
            "schema_version": "1.0",
            "calibration_status": "calibrated" if calibrated else "out_of_envelope",
            "calibration_id": "fake-simulated-calibration-v1" if calibrated else None,
            "probability_event": (
                "normal_within_envelope"
                if calibrated and value is not None and abs(value) < 3.0
                else "joint_anomaly_numeric_correct"
                if calibrated
                else "not_available"
            ),
            "magnitude_tolerance_db": 2.0,
            "probability": 0.95 if calibrated else None,
            "prediction_interval_db": (
                [value - 1.0, value + 1.0] if calibrated and value is not None else None
            ),
            "abstained": abstained,
            "reasons": reasons,
        }

    def build(
        self,
        *,
        context: dict,
        evidence: dict,
        quality: dict,
        frame_id: str,
        sequence: int,
        published_monotonic_s: float | None = None,
        inference_wall_ms: float = 0.0,
    ) -> dict:
        validate_analyzer_pair(context, evidence)
        deltas: dict[str, float] = {}
        valid_ids: list[str] = []
        for measurement in evidence["measurements"]:
            if measurement["validity"] != "valid":
                continue
            instrument_id = measurement["instrument_id"]
            if evidence["evidence_mode"] == "source_levels":
                delta = measurement["source_level_db"] - measurement["target_source_level_db"]
            else:
                delta = measurement["source_level_delta_db"]
            deltas[instrument_id] = float(delta)
            valid_ids.append(instrument_id)

        # V1 only claims an absolute centered balance when the documented majority
        # assumption has at least three reliable active anchors.
        identifiable = len(valid_ids) >= 3
        common_mode = statistics.median(deltas.values()) if identifiable else None
        gate_reasons = hard_gate_reasons(quality)
        instruments = []
        for measurement in evidence["measurements"]:
            instrument_id = measurement["instrument_id"]
            activity = measurement["activity"]
            reasons = list(measurement["reason_codes"])
            if measurement["validity"] == "valid" and not measurement["uncertainty_features"]:
                reasons.append("uncalibrated_uncertainty")
            reasons.extend(reason for reason in gate_reasons if reason not in reasons)
            if measurement["validity"] == "valid" and not identifiable:
                reasons.append("insufficient_stable_anchors")
            abstained = bool(reasons)
            if activity == "inactive":
                status = "inactive"
                abstained = True
            elif activity == "unsupported":
                status = "unsupported"
                abstained = True
            elif abstained:
                status = "unknown"
            else:
                balance = deltas[instrument_id] - common_mode
                status = (
                    "too_loud"
                    if balance >= self.anomaly_threshold_db
                    else "too_quiet"
                    if balance <= -self.anomaly_threshold_db
                    else "normal"
                )
            balance = None if abstained else deltas[instrument_id] - common_mode
            state = {
                "record_type": "InstrumentState",
                "schema_version": "1.0",
                "instrument_id": instrument_id,
                "family": measurement["family"],
                "activity": activity,
                "presence_probability": None,
                "source_level_delta_db": None if abstained else deltas[instrument_id],
                "balance_deviation_db": balance,
                "status": status,
                "confidence": self._confidence(
                    abstained=abstained, reasons=reasons, value=balance
                ),
                "tone": None,
            }
            validate_record(state, PUBLIC, "InstrumentState")
            instruments.append(state)

        observation = evidence["observation"]
        baseline = evidence["target"]["baseline"]
        frame = {
            "record_type": "AnalysisFrame",
            "schema_version": "1.0",
            "example_only": evidence["example_only"],
            "frame_id": frame_id,
            "session_id": observation["session_id"],
            "analysis_run_id": observation["analysis_run_id"],
            "sequence": sequence,
            "input_kind": observation["input_kind"],
            "input_asset_or_device_id": observation["input_asset_or_device_id"],
            "clock_id": observation["clock_id"],
            "sample_rate_hz": observation["sample_rate_hz"],
            "sample_start": observation["sample_start"],
            "sample_end": observation["sample_end"],
            "capture_end_monotonic_s": observation["capture_end_monotonic_s"],
            "published_monotonic_s": (
                time.monotonic() if published_monotonic_s is None else published_monotonic_s
            ),
            "model_bundle_id": evidence["model"]["model_bundle_id"],
            "frontend_id": evidence["model"]["frontend_id"],
            "execution_profile_id": evidence["model"]["execution_profile_id"],
            "baseline_id": baseline["baseline_id"] if baseline else None,
            "baseline_version": baseline["baseline_version"] if baseline else None,
            "reference_id": evidence["target"]["reference"]["reference_id"],
            "quality": quality,
            "observed_mix_level_delta_db": None,
            "common_mode_gain_db": common_mode if not gate_reasons and identifiable else None,
            "identifiability_assumption": (
                "majority_active_sources_unchanged" if identifiable else "unresolved"
            ),
            "inference_wall_ms": float(inference_wall_ms),
            "instruments": instruments,
        }
        validate_record(frame, PUBLIC, "AnalysisFrame")
        return frame
