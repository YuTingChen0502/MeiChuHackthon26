"""Host-approved held-out calibration consumption; no fitting or model inference.

Candidate/acceptance dictionaries follow the Lead-frozen ML internal seam.
No caller obtains production authorization from candidate metadata alone.
"""
import copy
import hashlib
import json
import math

from .quality import hard_gate_reasons


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


class CalibrationMapping:
    """Pure mapping mathematics. This class alone confers NO host approval."""
    def __init__(self, mapping, *, supported_scores):
        self.mapping = copy.deepcopy(mapping)
        feature = mapping["score_feature"]
        if (feature["name"], feature["unit"]) not in supported_scores:
            raise ValueError("unsupported calibration score/unit")
        if (mapping["magnitude_tolerance_db"] != 2.0 or
            mapping["endpoint_policy"] != "left_closed_right_open_last_closed" or
            mapping["interval_semantics"] != "true_balance_minus_predicted_balance"):
            raise ValueError("unsupported calibration semantics")
        bins = mapping["bins"]
        if not bins:
            raise ValueError("missing calibration bins")
        last = None
        for item in bins:
            lo, hi = item["residual_interval_db"]
            if not all(finite(v) for v in (item["lower"], item["upper"], item["probability"], lo, hi)):
                raise ValueError("nonfinite calibration")
            count, successes = item["count"], item["success_count"]
            if type(count) is not int or type(successes) is not int or count <= 0 or not 0 <= successes <= count:
                raise ValueError("invalid calibration support")
            if not 0 <= item["probability"] <= 1 or lo > hi or item["lower"] >= item["upper"]:
                raise ValueError("invalid calibration bounds")
            if last is not None and item["lower"] < last:
                raise ValueError("overlapping/unsorted calibration bins")
            last = item["upper"]

    def lookup(self, features):
        spec = self.mapping["score_feature"]
        matches = [f["value"] for f in features if f["name"] == spec["name"] and f["unit"] == spec["unit"]]
        if len(matches) != 1 or not finite(matches[0]):
            return None
        score = matches[0]
        bins = self.mapping["bins"]
        for index, item in enumerate(bins):
            if item["lower"] <= score < item["upper"] or (index == len(bins)-1 and score == item["upper"]):
                return copy.deepcopy(item)
        return None


class ReviewedEvidencePolicy:
    """Runtime-owned host settings, loaded separately from the untrusted bundle.

Required pins bind the exact candidate, full model, artifact and ML-validated
acceptance. Operating ranges and capture fingerprints come from host review.
"""
    def __init__(self, settings):
        self.settings = copy.deepcopy(settings)

    def bind(self, analyzer):
        return ApprovedCalibration(analyzer, self.settings)

    def capture(self, fingerprint, *, model, source_kind):
        for profile in self.settings.get("capture_profiles", []):
            if (profile["model"] == model and profile["source_kind"] == source_kind and
                profile["fingerprint"] == fingerprint and profile["reviewed_by"] and
                profile["operating_envelope_id"] == self.settings["acceptance"]["operating_envelope_id"]):
                return copy.deepcopy(profile["fingerprint"])
        return None


class ApprovedCalibration:
    def __init__(self, analyzer, settings):
        candidate = analyzer.calibration_metadata()
        acceptance = analyzer.acceptance_metadata()
        caps = analyzer.capabilities()
        if not candidate or not acceptance or acceptance != settings["acceptance"]:
            raise ValueError("host acceptance missing/mismatched")
        if (candidate.get("record_type") != "CalibrationCandidate" or candidate.get("schema_version") != "1.0" or
            candidate.get("status") != "candidate" or candidate.get("material_class") != "real_recorded" or
            candidate.get("example_only") is not False or caps["example_only"] is not False):
            raise ValueError("synthetic/unknown material cannot receive production approval")
        if (canonical_sha256(candidate) != settings["calibration_sha256"] or
            candidate["model"] != caps["model"] or candidate["model"] != settings["model"] or
            candidate["runtime_artifact_sha256"] != settings["runtime_artifact_sha256"] or
            candidate["calibration_id"] != acceptance["calibration_id"] or
            caps["provider"] not in settings["providers"]):
            raise ValueError("calibration/model/artifact/provider identity mismatch")
        if not acceptance["reviewed_by"] or acceptance["intended_use"] not in ("engineering", "competition"):
            raise ValueError("missing host review")
        if (type(acceptance["minimum_bin_count"]) is not int or acceptance["minimum_bin_count"] < 1 or
            not finite(acceptance["minimum_probability"]) or not 0 <= acceptance["minimum_probability"] <= 1 or
            not finite(acceptance["maximum_interval_width_db"]) or acceptance["maximum_interval_width_db"] <= 0):
            raise ValueError("invalid host thresholds")
        self.candidate, self.acceptance, self.settings = map(copy.deepcopy, (candidate, acceptance, settings))
        scores = {tuple(value) for value in settings["supported_scores"]}
        self.mappings = {event: CalibrationMapping(value, supported_scores=scores)
                         for event, value in candidate["mappings"].items()
                         if event in ("normal_within_envelope", "joint_anomaly_numeric_correct")}

    def evaluate(self, *, context, measurement, quality, balance, anomaly_threshold_db):
        event = "normal_within_envelope" if abs(balance) < anomaly_threshold_db else "joint_anomaly_numeric_correct"
        reason = None
        observation = context["observation"]
        envelope = self.settings["quality_envelope"]
        if (context["model"] != self.candidate["model"] or
            context["comparison_regime"] not in self.acceptance["comparison_regimes"] or
            measurement["family"] not in self.acceptance["accepted_families"] or
            observation["sample_rate_hz"] not in envelope["sample_rates_hz"] or
            not envelope["minimum_window_samples"] <= observation["sample_end"]-observation["sample_start"] <= envelope["maximum_window_samples"] or
            hard_gate_reasons(quality)):
            reason = "calibration_out_of_envelope"
        mapping = self.mappings.get(event)
        item = mapping.lookup(measurement["uncertainty_features"]) if mapping else None
        if reason is None and item is None:
            reason = "calibration_event_or_score_unavailable"
        if reason is None:
            lo, hi = item["residual_interval_db"]
            if (item["count"] < self.acceptance["minimum_bin_count"] or
                item["probability"] < self.acceptance["minimum_probability"] or
                hi-lo > self.acceptance["maximum_interval_width_db"]):
                reason = "calibration_support_insufficient"
        if reason:
            return None, reason
        return {"record_type":"ConfidenceState", "schema_version":"1.0", "calibration_status":"calibrated",
                "calibration_id":self.candidate["calibration_id"], "probability_event":event,
                "magnitude_tolerance_db":2.0, "probability":item["probability"],
                "prediction_interval_db":[balance+lo, balance+hi], "abstained":False, "reasons":[]}, None

    def normal_envelopes(self, instrument_config):
        by_family = self.settings["normal_envelopes_by_family"]
        result = []
        for instrument in instrument_config["instruments"]:
            values = by_family[instrument["family"]]
            if not all(finite(values[k]) for k in ("center_db", "lower_db", "upper_db")) or not values["lower_db"] <= values["center_db"] <= values["upper_db"]:
                raise ValueError("invalid reviewed normal envelope")
            result.append({"instrument_id":instrument["instrument_id"], **copy.deepcopy(values)})
        return result
