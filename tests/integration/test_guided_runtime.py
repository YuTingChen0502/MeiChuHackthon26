"""Guided intent is persisted control, never a source-activity label."""
import copy
import tempfile
import unittest
from dataclasses import replace
from apps.api.service import RuntimeAPI, APIError
from core.audio import MicAudioInput
from core.runtime import FakeEvidenceSpec
from core.runtime.quality import quality_state
from core.contracts.guided import validate_probe_response
import test_api_service as fixtures
import test_transport as transport_fixtures


def probe(snapshot,key="probe",mode="instrument",instrument="guitar"):
    value=fixtures.command(snapshot,key,"unused")
    value.pop("action");value.pop("payload")
    value.update(record_type="RehearsalProbeCommand",mode=mode,instrument_id=instrument)
    return value


class GuidedRuntimeTests(unittest.TestCase):
    def setup_runtime(self,directory):
        api=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={"mic-1"},
                       monotonic_clock=lambda:10)
        self.addCleanup(api.close)
        snapshot=fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)[3]
        return api,snapshot

    def test_durable_idempotency_cross_endpoint_conflict_and_restart_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            api,snapshot=self.setup_runtime(directory);sid=snapshot["session_id"]
            request=probe(snapshot)
            status,response=api.post_probe(sid,request);self.assertEqual(200,status);validate_probe_response(response)
            self.assertEqual("instrument",response["probe"]["mode"])
            self.assertEqual(response,api.post_probe(sid,request)[1])
            changed=copy.deepcopy(request);changed.update(mode="idle",instrument_id=None)
            self.assertEqual(409,api.post_probe(sid,changed)[0])
            conflict=fixtures.command(api.get_session(sid)[1],"probe","pause")
            self.assertEqual(409,api.post_action(sid,conflict)[0])
            with self.assertRaises(APIError):api.post_action(sid,request)
            api.close()
            restored=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={"mic-1"})
            self.assertEqual("idle",restored.get_probe(sid)[1]["mode"])
            self.assertEqual(response,restored.post_probe(sid,request)[1])
            self.assertEqual("idle",restored.get_probe(sid)[1]["mode"])
            restored.close()

    def test_failed_atomic_commit_rolls_back_probe_version_events(self):
        with tempfile.TemporaryDirectory() as directory:
            api,snapshot=self.setup_runtime(directory);sid=snapshot["session_id"]
            before=api.runtime_session(sid).export_state()
            ledger=api.handlers[sid].ledger;original=ledger.put
            ledger.put=lambda *a,**k: (_ for _ in ()).throw(OSError("disk fixture"))
            with self.assertRaises(OSError):api.post_probe(sid,probe(snapshot))
            self.assertEqual(before,api.runtime_session(sid).export_state())
            ledger.put=original

    def test_fresh_complete_window_and_truthful_inactive_source_then_gap_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            api,snapshot=self.setup_runtime(directory);sid=snapshot["session_id"];session=api.runtime_session(sid)
            api.post_probe(sid,probe(snapshot))
            seen=[];original=session.analyzer.analyze
            def capture(window,context):seen.append(context);return original(window,context)
            session.analyzer.analyze=capture
            audio=MicAudioInput(input_asset_or_device_id="mic-1",clock_id=session.source["clock_id"],
                                sample_rate_hz=10,samples=[.1]*30,origin_monotonic_s=9.5)
            windows=list(api.pipeline.iter_windows(audio,session_id=sid,analysis_run_id="probe-run"))
            self.assertIsNone(session.observe_window(windows[0]))
            self.assertEqual([],seen)
            session.analyzer.queue(FakeEvidenceSpec(inactive=frozenset({"guitar"})))
            result=session.observe_window(windows[1])
            self.assertEqual("guided_probe",seen[0]["observation_purpose"])
            self.assertEqual("guitar",seen[0]["probe_instrument_id"])
            self.assertEqual("inactive",result["instruments"][0]["activity"])
            self.assertTrue(result["instruments"][0]["confidence"]["abstained"])
            session.observe_window(windows[2],quality=quality_state(dropout=True))
            self.assertEqual("idle",api.get_probe(sid)[1]["mode"])
            self.assertEqual("rehearsal",seen[-1]["observation_purpose"])

    def test_invalid_instrument_stale_binding_and_pause_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            api,snapshot=self.setup_runtime(directory);sid=snapshot["session_id"]
            self.assertEqual(422,api.post_probe(sid,probe(snapshot,"bad",instrument="other"))[0])
            _,response=api.post_probe(sid,probe(snapshot,"full",mode="full_band",instrument=None))
            self.assertEqual(409,api.post_probe(sid,probe(snapshot,"stale"))[0])
            api.post_action(sid,fixtures.command(response["command"]["snapshot"],"pause","pause"))
            self.assertEqual("idle",api.get_probe(sid)[1]["mode"])

    def test_actual_http_probe_and_snapshot_event_reconnect(self):
        server=transport_fixtures.TransportTests();server.setUp()
        try:
            snapshot=server.setup_session();sid=snapshot["session_id"]
            status,response=server.request("POST",f"/v1/sessions/{sid}/probes",json_body=probe(snapshot))
            self.assertEqual(200,status);validate_probe_response(response)
            state=server.request("GET",f"/v1/sessions/{sid}/probes")[1]
            self.assertEqual(response["probe"],state)
            events=server.runtime.connect_events(sid,after_sequence=snapshot["event_sequence"])[1]["events"]
            self.assertEqual("SessionSnapshot",events[-1]["payload"]["record_type"])
            self.assertEqual(state["state_version"],events[-1]["state_version"])
        finally:server.tearDown()
