"""New-policy full Fake correction loop through actual HTTP and WebSocket transport."""
import time
import unittest
from core.audio import SharedAudioPipeline
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer,FakeEvidenceSpec
from websockets.sync.client import connect
import test_transport as transport
from test_api_service import wav_bytes,command


class LiveReferenceHTTPTests(unittest.TestCase):
    def test_reference_live_adjustment_verification_and_reconnect(self):
        fixture=transport.TransportTests();fixture.setUp()
        self.addCleanup(fixture.tearDown)
        phase={"guitar":0}
        class Scripted(ContinuousFakeInstrumentAnalyzer):
            def analyze(self,window,context):
                self.queue(FakeEvidenceSpec(deltas_db=dict(guitar=phase["guitar"],bass=0,drums=0)))
                return super().analyze(window,context)
        fixture.runtime.analyzer_factory=Scripted
        fixture.runtime.pipeline=SharedAudioPipeline(window_size_samples=2,hop_size_samples=2,sample_rate_hz=10)
        _,project=fixture.request("POST","/v1/projects",json_body={"name":"Live-reference Fake only"})
        _,song=fixture.request("POST","/v1/songs",json_body={"project_id":project["project_id"],"name":"Song",
            "instruments":[dict(instrument_id=x,family=x) for x in ("guitar","bass","drums")]})
        _,asset=fixture.request("POST","/v1/audio-assets",body=wav_bytes([.1]*100,sample_rate=10),headers={"Content-Type":"audio/wav"})
        _,job=fixture.request("POST",f"/v1/songs/{song['song_id']}/reference",json_body={"asset_id":asset["asset_id"]})
        end=time.monotonic()+3
        while time.monotonic()<end:
            _,job=fixture.request("GET",f"/v1/jobs/{job['job_id']}")
            if job["status"]=="completed":break
            time.sleep(.01)
        self.assertEqual("completed",job["status"])
        status,snapshot=fixture.request("POST","/v1/sessions",json_body=dict(song_id=song["song_id"],reference_id=job["reference_id"],
            workflow_policy="live_reference_v1",source=dict(input_kind="uploaded_file",input_asset_or_device_id=asset["asset_id"])))
        self.assertEqual(201,status);self.assertIsNone(snapshot["active_baseline"])
        sid=snapshot["session_id"];path=f"/v1/sessions/{sid}"
        def wait(predicate):
            until=time.monotonic()+4
            while time.monotonic()<until:
                _,s=fixture.request("GET",path)
                if predicate(s):return s
                time.sleep(.02)
            self.fail(str(s))
        snapshot=wait(lambda s:s["capture"]["frame_fresh"])
        self.assertEqual("LIVE_MONITORING",snapshot["song"]["workflow_state"])
        phase["guitar"]=4
        snapshot=wait(lambda s:s["incident"] is not None)
        self.assertEqual("reference",snapshot["incident"]["target"]["target_kind"])
        _,result=fixture.request("POST",path+"/actions",json_body=command(snapshot,"adjust","start_adjustment"))
        snapshot=result["snapshot"];phase["guitar"]=0
        _,result=fixture.request("POST",path+"/actions",json_body=command(snapshot,"complete","complete_adjustment",
            dict(adjustment_id=snapshot["adjustment"]["adjustment_id"])))
        self.assertEqual(200,result["http_status"])
        snapshot=result["snapshot"]
        _,result=fixture.request("POST",path+"/actions",json_body=command(snapshot,"recheck","recheck",
            dict(adjustment_id=snapshot["adjustment"]["adjustment_id"])))
        self.assertEqual(200,result["http_status"])
        snapshot=wait(lambda s:s["latest_verification"] is not None)
        self.assertEqual("recovered",snapshot["latest_verification"]["outcome"])
        self.assertIsNone(snapshot["latest_verification"]["baseline_id"])
        self.assertEqual("LIVE_MONITORING",snapshot["song"]["workflow_state"])
        for _ in range(2):
            with connect(f"ws://127.0.0.1:{fixture.port}"+path+"/events?after_sequence=0",origin=fixture.origin,open_timeout=3) as socket:
                self.assertIn('SessionEvent',socket.recv(timeout=3))
        _,snapshot=fixture.request("GET",path)
        fixture.request("POST",path+"/actions",json_body=command(snapshot,"stop","stop"))
