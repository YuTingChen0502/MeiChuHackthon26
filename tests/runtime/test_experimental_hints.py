"""Deterministic evidence fixtures; no model quality or calibration claims."""
import copy
import unittest
from core.runtime.fake_analyzer import FakeInstrumentAnalyzer,FakeEvidenceSpec
from core.runtime.deviation import FrameBuilder
from core.runtime.quality import quality_state
from roles.pa.experimental_hints import adjustment_hints
from test_streaming import windows,context


class ExperimentalHintTests(unittest.TestCase):
    def evidence(self,changes=None,levels=False):
        changes=changes or dict(guitar=4,bass=0,drums=0)
        spec=FakeEvidenceSpec(source_levels_db={k:(-20+v,-20) for k,v in changes.items()}) if levels else FakeEvidenceSpec(deltas_db=changes)
        analyzer=FakeInstrumentAnalyzer([spec]);window=windows()[0];ctx=context(window,analyzer)
        evidence=analyzer.analyze(window,ctx);evidence["example_only"]=False
        for row in evidence["measurements"]:
            row["reason_codes"]=["uncalibrated_candidate"]
            if row["family"]!="bass":row["reason_codes"].append("family_attribution_unvalidated")
        return ctx,evidence
    def hint(self,ctx,evidence,quality=None):
        frame=FrameBuilder().build(context=ctx,evidence=evidence,quality=quality or quality_state(),frame_id="f",sequence=1)
        return adjustment_hints(context=ctx,evidence=evidence,frame=frame,anomaly_threshold_db=3),frame
    def test_direction_inversion_both_modes_and_no_calibrated_side_effect(self):
        for levels in (False,True):
            for value,direction in ((4,"reduce_level"),(-4,"increase_level"),(3,"reduce_level"),(-3,"increase_level")):
                with self.subTest(levels=levels,value=value):
                    ctx,evidence=self.evidence(dict(guitar=value,bass=0,drums=0),levels)
                    hints,frame=self.hint(ctx,evidence)
                    self.assertEqual(direction,hints["guitar"]["direction"])
                    self.assertEqual({"direction","status","basis","evidence_frame_id","reason_codes","automatic_execution"},set(hints["guitar"]))
                    for row in frame["instruments"]:
                        self.assertTrue(row["confidence"]["abstained"])
                        self.assertIsNone(row["confidence"]["probability"])
                        self.assertIsInstance(row["balance_deviation_db"],float)
    def test_global_gain_and_subthreshold_changes_have_no_hint(self):
        for changes in (dict(guitar=8,bass=8,drums=8),dict(guitar=-8,bass=-8,drums=-8),dict(guitar=2.99,bass=0,drums=0)):
            self.assertEqual({},self.hint(*self.evidence(changes))[0])
    def test_sparse_valid_source_gets_only_an_explicit_experimental_direction(self):
        ctx,evidence=self.evidence(dict(guitar=5,bass=0,drums=0))
        for row in evidence["measurements"]:
            if row["instrument_id"]!="guitar":
                row.update(validity="invalid",activity="unknown",observability="unknown",
                           source_level_delta_db=None,reason_codes=["source_below_activity_floor"])
        hints,frame=self.hint(ctx,evidence)
        self.assertEqual("reduce_level",hints["guitar"]["direction"])
        self.assertIn("reference_delta_without_common_mode",hints["guitar"]["reason_codes"])
        state=next(row for row in frame["instruments"] if row["instrument_id"]=="guitar")
        self.assertTrue(state["confidence"]["abstained"])
        self.assertEqual(5,state["source_level_delta_db"])
    def test_all_hard_quality_gates_remain(self):
        for changed in (dict(stale=True),dict(dropout=True),dict(clipped_fraction=.01),dict(capture_compatible=False),dict(comparability="weak"),dict(reason_codes=["unclassified_noise"])):
            with self.subTest(changed=changed):self.assertEqual({},self.hint(*self.evidence(),quality_state(**changed))[0])
    def test_invalid_inactive_partial_alias_and_unknown_reasons_cannot_be_anchors(self):
        for reason in ("partial_source_representation","ambiguous_same_family_sources","matched_reference_span_unavailable","source_below_activity_floor"):
            ctx,evidence=self.evidence();row=evidence["measurements"][-1]
            row.update(validity="invalid",activity="unknown",observability="unknown",source_level_delta_db=None,reason_codes=[reason])
            self.assertNotIn(row["instrument_id"],self.hint(ctx,evidence)[0])
        ctx,evidence=self.evidence();evidence["measurements"][-1]["reason_codes"]=["unreviewed_failure"]
        self.assertNotIn(evidence["measurements"][-1]["instrument_id"],self.hint(ctx,evidence)[0])
        ctx,evidence=self.evidence();evidence["measurements"][-1]["family"]="bass"
        ctx["instrument_config"]["instruments"][-1]["family"]="bass"
        self.assertNotIn(evidence["measurements"][-1]["instrument_id"],self.hint(ctx,evidence)[0])
    def test_no_alignment_or_old_cache_never_hints(self):
        for reason in ("matched_reference_span_unavailable","reference_context_reprepare_required"):
            ctx,evidence=self.evidence();evidence["matched_context_window_id"]=None
            for row in evidence["measurements"]:
                row.update(validity="invalid",activity="unknown",observability="unknown",source_level_delta_db=None,reason_codes=[reason])
            self.assertEqual({},self.hint(ctx,evidence)[0])
    def test_context_model_frame_and_reference_bindings_are_validated(self):
        ctx,evidence=self.evidence();_,frame=self.hint(ctx,evidence)
        for key,value in (("clock_id","wrong"),("sample_start",7),("model_bundle_id","wrong"),("reference_id","wrong")):
            bad=copy.deepcopy(frame);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                adjustment_hints(context=ctx,evidence=evidence,frame=bad,anomaly_threshold_db=3)

    def test_calibrated_fake_and_out_of_envelope_confidence_never_hint(self):
        ctx,evidence=self.evidence();evidence["example_only"]=True
        for row in evidence["measurements"]:row["reason_codes"]=[]
        hints,frame=self.hint(ctx,evidence)
        self.assertEqual({},hints)
        self.assertEqual("too_loud",frame["instruments"][0]["status"])
        self.assertEqual("calibrated",frame["instruments"][0]["confidence"]["calibration_status"])
        ctx,evidence=self.evidence();_,frame=self.hint(ctx,evidence)
        for row in frame["instruments"]:row["confidence"]["calibration_status"]="out_of_envelope"
        self.assertEqual({},adjustment_hints(context=ctx,evidence=evidence,frame=frame,anomaly_threshold_db=3))
