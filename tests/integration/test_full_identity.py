"""Exact private profile identity; frozen public records stay unchanged."""
import copy
import tempfile
import unittest
from apps.api.service import RuntimeAPI, APIError
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer, FakeEvidenceSpec
import test_api_service as fixtures
import test_pa_vertical_slice as pa


class FullIdentityTests(unittest.TestCase):
    def test_reference_reuse_after_restart_requires_every_model_id(self):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={"mic-1"})
            song,asset,job,snapshot=fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)
            request=dict(song_id=song["song_id"],reference_id=job["reference_id"],
                source=dict(input_kind="live_microphone",input_asset_or_device_id="mic-1"),
                capture_fingerprint=copy.deepcopy(api.runtime_session(snapshot["session_id"]).capture_fingerprint))
            api.close()
            for key in ContinuousFakeInstrumentAnalyzer.MODEL:
                with self.subTest(identity=key):
                    class Replacement(ContinuousFakeInstrumentAnalyzer):
                        MODEL=dict(ContinuousFakeInstrumentAnalyzer.MODEL,**{key:"replacement-test-only"})
                    restored=RuntimeAPI(storage_dir=directory,window_size_samples=10,
                        available_audio_devices={"mic-1"},analyzer_factory=Replacement)
                    try:
                        with self.assertRaises(APIError) as error:restored.create_session(request)
                        self.assertEqual("incompatible_reference",error.exception.code)
                    finally:restored.close()
            restored=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={"mic-1"})
            self.assertEqual(201,restored.create_session(request)[0])
            restored.reference_models.clear()
            with self.assertRaises(APIError):restored.create_session(request)
            restored.close()

    def test_level_scale_change_blocks_observation_and_live_without_mutating_baseline(self):
        fixture=pa.PAVerticalSliceTests();fixture.setUp()
        try:
            fixture.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0)))
            window=fixture.window("accepted",2);fixture.session.observe_window(window)
            fixture.apply("accept","accept_baseline",dict(
                interval={key:getattr(window,key) for key in ("analysis_run_id","clock_id","sample_rate_hz","sample_start","sample_end")},
                accepted_by="human-pa",reference_difference_accepted=True,acceptance_note="synthetic test"))
            before=copy.deepcopy(fixture.session.baseline)
            original=fixture.analyzer.capabilities
            def changed():
                value=original();value["model"]["level_scale_id"]="different-scale";return value
            fixture.analyzer.capabilities=changed
            with self.assertRaisesRegex(ValueError,"model/profile changed"):
                fixture.session.observe_window(fixture.window("changed",3))
            accept_again=fixture.handler.handle(pa.command(fixture.session.snapshot(),"accept-changed","accept_baseline",dict(
                interval={key:getattr(window,key) for key in ("analysis_run_id","clock_id","sample_rate_hz","sample_start","sample_end")},
                accepted_by="human-pa",reference_difference_accepted=True,acceptance_note="must reject")))
            self.assertEqual("incompatible_profile",accept_again["error"]["code"])
            result=fixture.handler.handle(pa.command(fixture.session.snapshot(),"live","start_live"))
            self.assertEqual(409,result["http_status"])
            self.assertEqual("incompatible_profile",result["error"]["code"])
            self.assertEqual(before,fixture.session.baseline)
        finally:fixture.tearDown()
