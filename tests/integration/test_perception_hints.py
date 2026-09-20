"""HTTP/WS and lifecycle fixtures for experimental hints, not empirical model evidence."""
import json
import struct
import threading
import time
import unittest
from websockets.sync.client import connect
from apps.api.service import RuntimeAPI
from core.audio import SharedAudioPipeline
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer,FakeEvidenceSpec
from core.runtime.timing import analysis_timing_profile
import test_transport as transport
from test_api_service import wav_bytes,command
from test_live_reference_runtime import Backend


class TinyBackend(Backend):
    def negotiate(self,**kwargs):return dict(sample_rate_hz=10,channels=1)
    def open(self,**kwargs):
        class Stream:
            def __init__(self):self.stopped=threading.Event();self.thread=None
            def start(self):
                def emit():
                    while not self.stopped.wait(.2):kwargs["callback"](struct.pack("=2f",.1,.1),2,None,False)
                self.thread=threading.Thread(target=emit,daemon=True);self.thread.start()
            def abort(self):self.stopped.set()
            def close(self):
                self.stopped.set()
                if self.thread:self.thread.join(1)
        return Stream()


class AttemptedFixture(ContinuousFakeInstrumentAnalyzer):
    """Synthetic non-example contract fixture; not a production analyzer."""
    delta=4
    def capabilities(self):
        caps=super().capabilities()
        caps.update(provider="synthetic-attempted-contract-fixture",example_only=False,supported_families=["bass"],
            attempted_families=["bass","drums","guitar","keys","vocals"],validated_families=["bass"])
        return caps
    def analyze(self,window,context):
        self.queue(FakeEvidenceSpec(deltas_db=dict(guitar=self.delta,bass=0,drums=0),
            invalid_reasons={"keys":"partial_source_representation"}))
        evidence=super().analyze(window,context);evidence["example_only"]=False
        for row in evidence["measurements"]:
            if row["validity"]=="valid":
                row["reason_codes"]=["uncalibrated_candidate"]
                if row["family"]!="bass":row["reason_codes"].append("family_attribution_unvalidated")
        return evidence


class PerceptionHintTransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=transport.TransportTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown);self.api=self.fixture.runtime
        self.api.analysis_timing=analysis_timing_profile("candidate_delayed_v1")
        self.api.max_upload_bytes=4096
        self.api.analyzer_factory=AttemptedFixture;self.api._capabilities=None
        self.api.native_backend=TinyBackend()
        self.api.pipeline=SharedAudioPipeline(window_size_samples=2,hop_size_samples=2,sample_rate_hz=10)
        self.request=self.fixture.request
        _,project=self.request("POST","/v1/projects",json_body=dict(name="Hint contract fixture"))
        _,self.song=self.request("POST","/v1/songs",json_body=dict(project_id=project["project_id"],name="Song",
            instruments=[dict(instrument_id=x,family=x) for x in ("guitar","bass","drums","keys")]))
        _,asset=self.request("POST","/v1/audio-assets",body=wav_bytes([.1]*200,sample_rate=10),headers={"Content-Type":"audio/wav"})
        _,job=self.request("POST",f"/v1/songs/{self.song['song_id']}/reference",json_body=dict(asset_id=asset["asset_id"]))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            _,job=self.request("GET",f"/v1/jobs/{job['job_id']}")
            if job["status"]=="completed":break
            time.sleep(.02)
        self.assertEqual("completed",job["status"])
        self.setup=dict(song_id=self.song["song_id"],reference_id=job["reference_id"],workflow_policy="live_reference_v1",
            source=dict(input_kind="uploaded_file",input_asset_or_device_id=asset["asset_id"]))
        _,snapshot=self.request("POST","/v1/sessions",json_body=self.setup)
        self.sid=snapshot["session_id"];self.path=f"/v1/sessions/{self.sid}"
    def wait(self,predicate):
        until=time.monotonic()+4
        while time.monotonic()<until:
            status,snapshot=self.request("GET",self.path)
            if predicate(snapshot):return snapshot
            time.sleep(.02)
        self.fail(str(snapshot))
    def hinted(self):return self.wait(lambda s:s["perception"][0].get("adjustment_hint") is not None)
    def test_attempted_unvalidated_hint_and_partial_family_over_actual_http_ws(self):
        snapshot=self.hinted()
        self.assertEqual(dict(profile_id="candidate_delayed_v1",queue_max_age_s=2.0,
            result_max_age_s=20.0,hint_hold_s=10.0,receipt_max_age_s=12.0),
            {key:value for key,value in snapshot["analysis_timing"].items() if key!="snapshot_monotonic_s"})
        self.assertEqual(["bass"],self.song["supported_families"])
        self.assertEqual([],self.song["unsupported_families"])
        self.assertEqual([],snapshot["song"]["unsupported_families"])
        guitar,bass,drums,keys=snapshot["perception"]
        self.assertEqual("uncertain",guitar["state"]);self.assertEqual("detected",bass["state"])
        self.assertEqual("uncertain",keys["state"]);self.assertIsNone(keys["adjustment_hint"])
        self.assertEqual("reduce_level",guitar["adjustment_hint"]["direction"])
        expiry=guitar["adjustment_hint"]["expires_monotonic_s"]
        self.assertLessEqual(expiry,min(snapshot["latest_frame"]["published_monotonic_s"]+10,
            snapshot["latest_frame"]["capture_end_monotonic_s"]+20))
        self.assertTrue(guitar["action_abstained"]);self.assertFalse(guitar["numerical_advice_allowed"])
        self.assertIsNone(snapshot["incident"]);self.assertEqual([],snapshot["recommendations"])
        self.assertIsNone(snapshot["latest_verification"])
        for state in snapshot["latest_frame"]["instruments"]:
            self.assertIsNone(state["confidence"]["probability"]);self.assertIsNone(state["balance_deviation_db"])
        self.api.workers[self.sid].stop()
        for _ in range(2):
            with connect(f"ws://127.0.0.1:{self.fixture.port}"+self.path+"/events?after_sequence=0",
                         origin=self.fixture.origin,close_timeout=1) as socket:
                event=json.loads(socket.recv(timeout=2));self.assertEqual(self.sid,event["session_id"])
            refreshed=self.hinted()["perception"][0]["adjustment_hint"]
            self.assertIsNotNone(refreshed);self.assertEqual(expiry,refreshed["expires_monotonic_s"])
    def test_pause_resume_switch_and_stop_clear_hints(self):
        snapshot=self.hinted()
        _,result=self.request("POST",self.path+"/actions",json_body=command(snapshot,"hint-pause","pause"))
        snapshot=result["snapshot"]
        self.assertTrue(all(p["adjustment_hint"] is None for p in snapshot["perception"]))
        self.request("POST",self.path+"/actions",json_body=command(snapshot,"hint-resume","resume"))
        snapshot=self.hinted()
        _,result=self.request("POST",self.path+"/actions",json_body=command(snapshot,"hint-switch","switch_microphone",
            dict(microphone_id="mic-a",expected_source_generation=snapshot["capture"]["source_generation"])))
        self.assertTrue(all(p["adjustment_hint"] is None for p in result["snapshot"]["perception"]))
        snapshot=self.wait(lambda s:s["capture"]["state"]=="active")
        self.assertFalse(snapshot["latest_frame"]["quality"]["capture_compatible"])
        self.assertTrue(all(p["adjustment_hint"] is None for p in snapshot["perception"]))
        _,result=self.request("POST",self.path+"/actions",json_body=command(snapshot,"hint-stop","stop"))
        self.assertTrue(all(p["adjustment_hint"] is None for p in result["snapshot"]["perception"]))
    def test_stale_frame_and_restart_never_restore_hint(self):
        self.hinted();session=self.api.runtime_session(self.sid)
        session._analysis_timing=analysis_timing_profile("strict_v1");session._current_hints={};session._hint_expires_monotonic_s=None
        self.api.workers[self.sid].stop()
        snapshot=self.wait(lambda s:s["latest_frame"] is None)
        self.assertTrue(all(p["adjustment_hint"] is None for p in snapshot["perception"]))
        self.api.close()
        restored=RuntimeAPI(storage_dir=self.api.storage_dir,window_size_samples=2,hop_size_samples=2,
            analysis_sample_rate_hz=10,analyzer_factory=AttemptedFixture,native_backend=Backend())
        try:
            snapshot=restored.get_session(self.sid)[1]
            self.assertTrue(all(p["adjustment_hint"] is None for p in snapshot["perception"]))
            self.assertIsNone(snapshot["latest_frame"])
        finally:restored.close()
