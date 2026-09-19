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
            dict(model={"id":"test"},source_kind="live_microphone",fingerprint={"device":"test"},
                 reviewed_by="TEST ONLY",operating_envelope_id="test-envelope")]}
        policy=ReviewedEvidencePolicy(settings)
        self.assertIsNone(policy.capture({"device":"other"},model={"id":"test"},source_kind="live_microphone"))
        self.assertIsNone(policy.capture({"device":"test"},model={"id":"replacement"},source_kind="live_microphone"))
        self.assertEqual({"device":"test"},policy.capture({"device":"test"},model={"id":"test"},source_kind="live_microphone"))
