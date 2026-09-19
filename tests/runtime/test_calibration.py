"""Synthetic policy mechanics ONLY. No fixture receives production approval."""
import copy
import unittest
from core.runtime.calibration import CalibrationMapping, ApprovedCalibration, ReviewedEvidencePolicy


def mapping():
    return dict(magnitude_tolerance_db=2.0,score_feature=dict(name="error",unit="dB"),
                endpoint_policy="left_closed_right_open_last_closed",
                interval_semantics="true_balance_minus_predicted_balance",
                bins=[dict(lower=0,upper=1,count=10,success_count=9,probability=.9,residual_interval_db=[-1,1]),
                      dict(lower=1,upper=2,count=20,success_count=19,probability=.95,residual_interval_db=[-.5,.5])])


class CalibrationTests(unittest.TestCase):
    def test_endpoints_gaps_units_and_support(self):
        evaluator=CalibrationMapping(mapping(),supported_scores={("error","dB")})
        def lookup(value,unit="dB"):
            return evaluator.lookup([dict(name="error",unit=unit,value=value)])
        self.assertEqual(10,lookup(0)["count"])
        self.assertEqual(20,lookup(1)["count"])
        self.assertEqual(20,lookup(2)["count"])
        for value in (-.1,2.1,float("nan")):
            self.assertIsNone(lookup(value))
        self.assertIsNone(lookup(1,"ratio"))
        self.assertIsNone(evaluator.lookup([]))

    def test_invalid_bins_and_semantics_fail_closed(self):
        edits=[lambda v:v["bins"][0].update(count=0),lambda v:v["bins"][1].update(lower=.5),
               lambda v:v["bins"][0].update(probability=float("nan")),
               lambda v:v.update(endpoint_policy="invented"),lambda v:v["score_feature"].update(unit="ratio")]
        for edit in edits:
            value=mapping();edit(value)
            with self.assertRaises(ValueError): CalibrationMapping(value,supported_scores={("error","dB")})

    def test_synthetic_candidate_cannot_be_production_approved(self):
        class Synthetic:
            def calibration_metadata(self):
                return dict(record_type="CalibrationCandidate",schema_version="1.0",status="candidate",
                            material_class="synthetic",example_only=True)
            def acceptance_metadata(self): return {"reviewed_by":"TEST ONLY"}
            def capabilities(self): return {"example_only":False}
        with self.assertRaisesRegex(ValueError,"cannot receive production"):
            ApprovedCalibration(Synthetic(),{"acceptance":{"reviewed_by":"TEST ONLY"}})

    def test_capture_requires_exact_reviewed_fingerprint_and_model(self):
        settings={"acceptance":{"operating_envelope_id":"test-envelope"},"capture_profiles":[
            dict(model={"id":"test"},source_kind="live_microphone",fingerprint={"device_id":"test"},
                 reviewed_by="TEST ONLY",operating_envelope_id="test-envelope")]}
        policy=ReviewedEvidencePolicy(settings)
        self.assertIsNone(policy.capture({"device_id":"other"},model={"id":"test"},source_kind="live_microphone"))
        self.assertIsNone(policy.capture({"device_id":"test"},model={"id":"replacement"},source_kind="live_microphone"))
        self.assertEqual({"device_id":"test"},policy.capture({"device_id":"test"},model={"id":"test"},source_kind="live_microphone"))

    def test_both_event_mappings_and_runtime_support_quality_gates(self):
        # Exercise only the pure evaluate method on an explicit synthetic fixture.
        # ApprovedCalibration.__init__ is NOT bypassed on a production object.
        from types import SimpleNamespace
        from core.runtime.quality import quality_state
        fixture=SimpleNamespace(candidate={"calibration_id":"synthetic-policy-test-only","model":{"id":"fixture"}},
            acceptance={"comparison_regimes":["matched_excerpt"],"accepted_families":["guitar"],
                        "minimum_bin_count":10,"minimum_probability":.8,"maximum_interval_width_db":2},
            settings={"quality_envelope":{"sample_rates_hz":[10],"minimum_window_samples":10,"maximum_window_samples":10}},
            mappings={event:CalibrationMapping(mapping(),supported_scores={("error","dB")})
                      for event in ("normal_within_envelope","joint_anomaly_numeric_correct")})
        context={"model":{"id":"fixture"},"comparison_regime":"matched_excerpt",
                 "observation":{"sample_rate_hz":10,"sample_start":0,"sample_end":10}}
        measurement={"family":"guitar","uncertainty_features":[{"name":"error","unit":"dB","value":.5}]}
        def evaluate(balance,quality=None):
            return ApprovedCalibration.evaluate(fixture,context=context,measurement=measurement,
                quality=quality or quality_state(),balance=balance,anomaly_threshold_db=3)
        self.assertEqual("normal_within_envelope",evaluate(0)[0]["probability_event"])
        self.assertEqual([3,5],evaluate(4)[0]["prediction_interval_db"])
        self.assertEqual("calibration_out_of_envelope",evaluate(4,quality_state(dropout=True))[1])
        fixture.acceptance["minimum_bin_count"]=11
        self.assertEqual("calibration_support_insufficient",evaluate(4)[1])
        fixture.acceptance["minimum_bin_count"]=10
        fixture.mappings.pop("normal_within_envelope")
        self.assertEqual("calibration_event_or_score_unavailable",evaluate(0)[1])
        context["model"]={"id":"replacement"}
        self.assertEqual("calibration_out_of_envelope",evaluate(4)[1])
