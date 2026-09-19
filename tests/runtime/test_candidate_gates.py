"""Synthetic contract fixture for candidate limitations; not model evidence."""
import unittest
from core.runtime.fake_analyzer import FakeInstrumentAnalyzer, FakeEvidenceSpec
from core.runtime.deviation import FrameBuilder
from core.runtime.quality import quality_state
from test_streaming import windows, context


class CandidateGateTests(unittest.TestCase):
    def test_bass_only_uncalibrated_and_unsupported_evidence_never_becomes_normal(self):
        analyzer=FakeInstrumentAnalyzer([FakeEvidenceSpec(deltas_db={"bass":4},
            unsupported=frozenset({"guitar","drums","vocals","keys"}))])
        window=windows()[0];ctx=context(window,analyzer)
        ctx["instrument_config"]["instruments"]=[{"instrument_id":x,"family":x} for x in ("bass","guitar","drums","vocals","keys")]
        evidence=analyzer.analyze(window,ctx)
        # Deliberate non-example contract input tests downstream gates only.
        evidence["example_only"]=False
        frame=FrameBuilder().build(context=ctx,evidence=evidence,quality=quality_state(),frame_id="fixture",sequence=1)
        for state in frame["instruments"]:
            self.assertNotEqual("normal",state["status"])
            self.assertIsNone(state["balance_deviation_db"])
            self.assertIsNone(state["confidence"]["probability"])
            self.assertIsNone(state["confidence"]["prediction_interval_db"])
            self.assertTrue(state["confidence"]["abstained"])
            if state["family"] != "bass":self.assertEqual("unsupported",state["status"])
