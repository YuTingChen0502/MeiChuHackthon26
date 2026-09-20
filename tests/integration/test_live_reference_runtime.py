"""Live-reference API lifecycle with real asynchronous callback/worker boundaries."""
import copy
import struct
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

from apps.api.service import RuntimeAPI
from core.audio.native import NativeDevice
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer,FakeEvidenceSpec
from test_api_service import wav_bytes,command


class Backend:
    def __init__(self):
        self.fail=set();self.silent=set();self.streams=[];self.opens=[];self.alternate_timing=False;self.status=False
    def discover(self):
        return [NativeDevice("mic-a",0,"Desk microphone","Test",1,48000,True),
                NativeDevice("mic-b",1,"USB microphone","Test",1,48000,False)]
    def negotiate(self,**kw):return dict(sample_rate_hz=48000,channels=1)
    def open(self,**kw):
        self.opens.append(kw["device_id"])
        if kw["device_id"] in self.fail:raise RuntimeError("injected_open_failure")
        backend=self
        class Stream:
            def __init__(self):self.stop=threading.Event();self.thread=None;self.closed=False
            def start(self):
                def emit():
                    packet=0
                    while not self.stop.wait(1024/48000):
                        if kw["device_id"] not in backend.silent:
                            packet+=1;adc=(1+packet*1024/48000) if backend.alternate_timing and packet%2 else 0
                            kw["callback"](struct.pack("=1024f",*([.1]*1024)),1024,
                                SimpleNamespace(inputBufferAdcTime=adc,currentTime=adc+.01 if adc else 0),backend.status)
                self.thread=threading.Thread(target=emit,daemon=True);self.thread.start()
            def abort(self):self.stop.set()
            def close(self):
                self.stop.set();self.closed=True
                if self.thread:self.thread.join(1)
        stream=Stream();self.streams.append(stream);return stream


class LiveReferenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.backend=Backend()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=1024,hop_size_samples=1024,
            analysis_sample_rate_hz=48000,native_backend=self.backend,managed_audio=True)
        self.api.live_audio.startup_timeout_s=.6
        _,project=self.api.create_project({"name":"Live reference"})
        _,self.song=self.api.create_song({"project_id":project["project_id"],"name":"Same song",
            "instruments":[{"instrument_id":x,"family":x} for x in ("bass","guitar","drums")]})
        _,asset=self.api.upload_audio(wav_bytes([.1]*4096,sample_rate=48000),filename="generated.wav")
        _,job=self.api.start_reference_job(self.song["song_id"],{"asset_id":asset["asset_id"]})
        self.api.run_reference_job(job["job_id"])
        self.request=dict(song_id=self.song["song_id"],reference_id=job["reference_id"],workflow_policy="live_reference_v1")
    def tearDown(self):self.api.close();self.temp.cleanup()
    def wait(self,sid,predicate,timeout=3):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            snapshot=self.api.get_session(sid)[1]
            if predicate(snapshot):return snapshot
            time.sleep(.01)
        self.fail(str(snapshot))
    def start(self):
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        return self.wait(sid,lambda s:s["capture"]["state"]=="active" and not self.api.live_audio.tasks[sid].is_alive())
    def switch(self,snapshot,identity,key="switch"):
        body=command(snapshot,key,"switch_microphone",dict(microphone_id=identity,
            expected_source_generation=snapshot["capture"]["source_generation"]))
        return body,self.api.post_action(snapshot["session_id"],body)
    def test_default_live_reference_no_baseline_and_exact_perception(self):
        snapshot=self.start();sid=snapshot["session_id"]
        self.assertEqual(("strict_v1",2.0,2.0,10.0,5.0),tuple(snapshot["analysis_timing"][key]
            for key in ("profile_id","queue_max_age_s","result_max_age_s","hint_hold_s","receipt_max_age_s")))
        self.assertEqual("live",snapshot["session_mode"])
        self.assertEqual("LIVE_MONITORING",snapshot["song"]["workflow_state"])
        self.assertIsNone(snapshot["active_baseline"])
        self.assertEqual(self.request["reference_id"],snapshot["latest_frame"]["reference_id"])
        self.assertTrue(all(x["state"]=="uncertain" for x in snapshot["perception"]))
        result=self.api.post_action(sid,command(snapshot,"old-live","start_live"))[1]
        self.assertEqual(409,result["http_status"])
    def test_switch_fences_old_work_idempotency_and_same_reference(self):
        old=self.start();sid=old["session_id"];worker=self.api.workers[sid]
        body,(status,accepted)=self.switch(old,"mic-b")
        self.assertEqual(200,status);self.assertEqual("switching",accepted["snapshot"]["capture"]["state"])
        self.assertIsNone(accepted["snapshot"]["latest_frame"])
        self.assertEqual(accepted,self.api.post_action(sid,body)[1])
        snapshot=self.wait(sid,lambda s:s["capture"]["switch_result"]=="applied" and s["capture"]["state"]=="active")
        self.assertEqual("mic-b",snapshot["source"]["input_asset_or_device_id"])
        self.assertNotEqual(old["source"]["clock_id"],snapshot["source"]["clock_id"])
        self.assertNotEqual(old["latest_frame"]["analysis_run_id"],snapshot["latest_frame"]["analysis_run_id"])
        before=copy.deepcopy(snapshot)
        worker.on_window(None,{},2) # A delayed previous generation callback cannot reach perception.
        worker.on_end("late_old_error")
        snapshot=self.api.get_session(sid)[1]
        self.assertEqual(before["source"],snapshot["source"])
        self.assertEqual("active",snapshot["capture"]["state"])
        self.assertEqual(old["active_reference"],snapshot["active_reference"])
        self.assertTrue(self.backend.streams[0].closed)
    def test_failed_switch_rolls_back_with_fresh_identity_and_retained_error(self):
        old=self.start();sid=old["session_id"];self.backend.fail.add("mic-b")
        self.switch(old,"mic-b")
        snapshot=self.wait(sid,lambda s:s["capture"]["switch_result"]=="rolled_back")
        self.assertEqual("mic-a",snapshot["source"]["input_asset_or_device_id"])
        self.assertEqual("mic-b",snapshot["capture"]["requested_microphone_id"])
        self.assertTrue(snapshot["capture"]["reason_codes"])
        self.assertNotEqual(old["source"]["clock_id"],snapshot["source"]["clock_id"])
        self.assertGreaterEqual(snapshot["capture"]["source_generation"],old["capture"]["source_generation"]+3)
    def test_absent_microphone_keeps_session_then_switch_recovers(self):
        self.backend.fail.update(("mic-a","mic-b"))
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="unavailable")
        self.assertEqual("SUSPENDED",snapshot["song"]["workflow_state"])
        self.backend.fail.clear();self.switch(snapshot,"mic-b")
        snapshot=self.wait(sid,lambda s:s["capture"]["switch_result"]=="applied" and s["capture"]["state"]=="active")
        self.assertEqual("LIVE_MONITORING",snapshot["song"]["workflow_state"])
    def test_pause_select_resume_and_stop_during_silent_switch(self):
        snapshot=self.start();sid=snapshot["session_id"]
        snapshot=self.api.post_action(sid,command(snapshot,"pause","pause"))[1]["snapshot"]
        self.switch(snapshot,"mic-b","paused-select")
        snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="paused" and s["capture"]["switch_result"]=="applied")
        self.assertIsNone(snapshot["latest_frame"]);self.assertTrue(all(x.closed for x in self.backend.streams))
        self.api.post_action(sid,command(snapshot,"resume","resume"))
        snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="active")
        self.backend.silent.add("mic-a");self.switch(snapshot,"mic-a","silent-switch")
        snapshot=self.api.get_session(sid)[1]
        self.api.post_action(sid,command(snapshot,"stop","stop"))
        time.sleep(.1)
        snapshot=self.api.get_session(sid)[1]
        self.assertEqual("stopped",snapshot["capture"]["state"])
        self.assertIsNone(snapshot["latest_frame"])
        self.assertTrue(all(x.closed for x in self.backend.streams))
    def test_restart_preserves_policy_reference_and_idempotent_switch_ack(self):
        old=self.start();sid=old["session_id"]
        body,(_,accepted)=self.switch(old,"mic-b")
        self.wait(sid,lambda s:s["capture"]["switch_result"]=="applied" and s["capture"]["state"]=="active")
        self.api.close()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=1024,analysis_sample_rate_hz=48000,
            native_backend=self.backend,managed_audio=True)
        snapshot=self.api.get_session(sid)[1]
        self.assertEqual("live_reference_v1",snapshot["workflow_policy"])
        self.assertEqual("unavailable",snapshot["capture"]["state"])
        self.assertIsNone(snapshot["latest_frame"])
        self.assertEqual(accepted,self.api.post_action(sid,body)[1])
        _,(status,result)=self.switch(snapshot,"mic-a","after-restart")
        self.assertEqual(200,status)
        recovered=self.wait(sid,lambda s:s["capture"]["state"]=="active")
        self.assertEqual(old["active_reference"],recovered["active_reference"])
        self.assertNotEqual(old["source"]["clock_id"],recovered["source"]["clock_id"])

    def test_switch_acceptance_does_not_wait_for_old_inference(self):
        snapshot=self.start();sid=snapshot["session_id"]
        session=self.api.runtime_session(sid)
        original=session.analyzer.analyze;entered=threading.Event();release=threading.Event()
        def blocked(window,context):
            entered.set();release.wait(3);return original(window,context)
        session.analyzer.analyze=blocked
        self.assertTrue(entered.wait(2))
        snapshot=self.api.get_session(sid)[1]
        started=time.monotonic()
        body,(_,accepted)=self.switch(snapshot,"mic-b","during-inference")
        self.assertLess(time.monotonic()-started,.5)
        self.assertIsNone(accepted["snapshot"]["latest_frame"])
        release.set()
        final=self.wait(sid,lambda s:s["capture"]["switch_result"]=="applied" and s["capture"]["state"]=="active")
        self.assertEqual("mic-b",final["latest_frame"]["input_asset_or_device_id"])

    def test_concurrent_switch_rejected_and_silent_failure_rolls_back(self):
        snapshot=self.start();sid=snapshot["session_id"]
        self.backend.silent.add("mic-b")
        self.switch(snapshot,"mic-b","first")
        snapshot=self.api.get_session(sid)[1]
        _,(status,response)=self.switch(snapshot,"mic-a","second")
        self.assertEqual(409,status);self.assertEqual("switch_in_progress",response["error"]["code"])
        final=self.wait(sid,lambda s:s["capture"]["switch_result"]=="rolled_back")
        self.assertEqual("mic-a",final["source"]["input_asset_or_device_id"])
        self.assertIsNone(final["latest_verification"])

    def test_healthy_pcm_slow_model_survives_startup_and_stop_defers_close(self):
        entered=threading.Event();release=threading.Event()
        original_factory=self.api._new_analyzer
        def factory():
            analyzer=original_factory();original=analyzer.analyze
            def blocked(window,context):
                entered.set();release.wait(5);return original(window,context)
            analyzer.analyze=blocked
            return analyzer
        self.api._new_analyzer=factory
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        self.assertTrue(entered.wait(2))
        time.sleep(.7)
        snapshot=self.api.get_session(sid)[1]
        self.assertEqual("listening",snapshot["capture"]["state"])
        self.assertFalse(snapshot["capture"]["frame_fresh"])
        self.assertFalse(self.api.live_audio.tasks[sid].is_alive())
        analyzer=self.api.runtime_session(sid).analyzer
        begin=time.monotonic()
        self.api.post_action(sid,command(snapshot,"slow-stop","stop"))
        self.assertLess(time.monotonic()-begin,.5)
        self.assertTrue(all(s.closed for s in self.backend.streams))
        self.assertFalse(analyzer.closed)
        release.set()
        self.api.live_audio.closers[sid].join(2)
        self.assertTrue(analyzer.closed)
        self.assertIsNone(self.api.get_session(sid)[1]["latest_frame"])

    def test_alternating_timestamp_diagnostics_do_not_starve_bound_controls(self):
        self.backend.alternate_timing=True;entered=threading.Event();release=threading.Event()
        original_factory=self.api._new_analyzer
        def factory():
            analyzer=original_factory();original=analyzer.analyze
            def blocked(window,context):
                entered.set();release.wait(5);return original(window,context)
            analyzer.analyze=blocked;return analyzer
        self.api._new_analyzer=factory
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        try:
            self.assertTrue(entered.wait(2))
            snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="listening" and not self.api.live_audio.tasks[sid].is_alive())
            version=snapshot["state_version"];time.sleep(.2)
            snapshot=self.api.get_session(sid)[1]
            self.assertEqual(version,snapshot["state_version"])
            status,result=self.api.post_action(sid,command(snapshot,"flap-pause","pause"))
            self.assertEqual(200,status);snapshot=result["snapshot"]
            self.switch(snapshot,"mic-b","flap-switch")
            snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="paused" and s["capture"]["switch_result"]=="applied")
            status,result=self.api.post_action(sid,command(snapshot,"flap-resume","resume"))
            self.assertEqual(200,status)
            snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="listening" and not self.api.live_audio.tasks[sid].is_alive())
            version=snapshot["state_version"];time.sleep(.2);snapshot=self.api.get_session(sid)[1]
            self.assertEqual(version,snapshot["state_version"])
            status,_=self.api.post_action(sid,command(snapshot,"flap-stop","stop"))
            self.assertEqual(200,status)
        finally:
            release.set()

    def test_physical_fault_during_inference_fences_completed_old_window(self):
        entered=threading.Event();release=threading.Event();calls=[]
        original_factory=self.api._new_analyzer
        def factory():
            analyzer=original_factory();original=analyzer.analyze
            def blocked(window,context):
                calls.append(window.sample_start)
                if len(calls)==2:entered.set();release.wait(3)
                return original(window,context)
            analyzer.analyze=blocked;return analyzer
        self.api._new_analyzer=factory
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        try:
            snapshot=self.wait(sid,lambda s:s["capture"]["state"]=="active")
            self.assertIsNotNone(snapshot["latest_frame"]);self.assertTrue(entered.wait(2))
            self.backend.status=True;time.sleep(.08);self.backend.status=False
            self.assertGreater(self.api.workers[sid].audio_input.discontinuities,0)
            suppressed=self.wait(sid,lambda s:not s["capture"]["frame_fresh"] and s["latest_frame"] is None)
            self.assertEqual(["capture_dropout"],suppressed["capture"]["reason_codes"])
            release.set()
            self.wait(sid,lambda s:any(frame["quality"]["dropout"] for frame in self.api.runtime_session(sid)._frames))
            frames=self.api.runtime_session(sid)._frames
            self.assertNotIn(calls[1],[frame["sample_start"] for frame in frames])
            self.assertTrue(any(frame["quality"]["dropout"] for frame in frames))
            self.assertTrue(all(p.get("adjustment_hint") is None for p in self.api.get_session(sid)[1]["perception"]))
        finally:release.set()

    def test_raw_detection_remains_separate_from_advice_and_staleness(self):
        snapshot=self.start();sid=snapshot["session_id"];session=self.api.runtime_session(sid)
        original=session.analyzer.analyze
        def scripted(window,context):
            session.analyzer.queue(FakeEvidenceSpec(deltas_db={"bass":0},inactive=frozenset({"guitar"}),unsupported=frozenset({"drums"})))
            return original(window,context)
        session.analyzer.analyze=scripted
        snapshot=self.wait(sid,lambda s:s["perception"][0]["state"]=="detected")
        bass,guitar,drums=snapshot["perception"]
        self.assertTrue(bass["action_abstained"])
        self.assertFalse(bass["numerical_advice_allowed"])
        self.assertEqual("not_heard",guitar["state"])
        self.assertEqual("unsupported",drums["state"])
        self.assertIsNone(snapshot["latest_frame"]["instruments"][0]["confidence"]["probability"])
        # Raw evidence cannot survive publication freshness expiry.
        worker=self.api.workers[sid];worker.stop();worker.max_age_s=.001
        snapshot=self.wait(sid,lambda s:s["latest_frame"] is None)
        self.assertFalse(snapshot["capture"]["frame_fresh"])
        self.assertTrue(all(x["state"]=="uncertain" for x in snapshot["perception"]))

    def test_file_acquisition_startup_does_not_wait_for_slow_model(self):
        entered=threading.Event();release=threading.Event()
        factory=self.api._new_analyzer
        def slow_factory():
            analyzer=factory();original=analyzer.analyze
            def blocked(window,context):
                entered.set();release.wait(3);return original(window,context)
            analyzer.analyze=blocked
            return analyzer
        self.api._new_analyzer=slow_factory
        _,asset=self.api.upload_audio(wav_bytes([.1]*48000,sample_rate=48000),filename="file-live.wav")
        request=dict(self.request,source=dict(input_kind="uploaded_file",input_asset_or_device_id=asset["asset_id"]))
        _,snapshot=self.api.create_session(request);sid=snapshot["session_id"]
        try:
            self.assertTrue(entered.wait(2));time.sleep(.7)
            snapshot=self.api.get_session(sid)[1]
            self.assertEqual("listening",snapshot["capture"]["state"])
            self.assertFalse(self.api.live_audio.tasks[sid].is_alive())
            self.assertFalse(snapshot["capture"]["frame_fresh"])
            self.assertIsNone(snapshot["capture"]["native_device_id"])
        finally:release.set()

    def test_repeated_switch_keeps_capture_running_with_one_blocked_inference(self):
        snapshot=self.start();sid=snapshot["session_id"];session=self.api.runtime_session(sid)
        entered=threading.Event();release=threading.Event();original=session.analyzer.analyze
        calls=[]
        def blocked(window,context):
            calls.append(window.clock_id);entered.set();release.wait(5)
            return original(window,context)
        session.analyzer.analyze=blocked
        try:
            self.assertTrue(entered.wait(2))
            for i,identity in enumerate(("mic-b","mic-a","mic-b")):
                old=self.api.get_session(sid)[1]
                self.switch(old,identity,f"bounded-switch-{i}")
                snapshot=self.wait(sid,lambda s:s["capture"]["switch_result"]=="applied")
                self.assertEqual("listening",snapshot["capture"]["state"])
                self.assertFalse(snapshot["capture"]["frame_fresh"])
                self.assertGreater(self.api.workers[sid].audio_input._next_sample,0)
                self.assertLessEqual(len(self.api.live_audio.retired.get(sid,[])),1)
            self.assertEqual(1,len(calls))
            self.assertTrue(all(s.closed for s in self.backend.streams[:-1]))
        finally:release.set()
        snapshot=self.wait(sid,lambda s:s["capture"]["frame_fresh"])
        self.assertEqual(snapshot["source"]["clock_id"],snapshot["latest_frame"]["clock_id"])
        self.assertNotEqual(calls[0],calls[-1])

    def test_restart_resume_reconstructs_analyzer_and_mismatch_stays_suspended(self):
        old=self.start();sid=old["session_id"]
        self.api.close()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=1024,hop_size_samples=1024,
            analysis_sample_rate_hz=48000,native_backend=self.backend,managed_audio=True)
        snapshot=self.api.get_session(sid)[1]
        original_factory=self.api._new_analyzer
        def incompatible():
            analyzer=original_factory();analyzer.MODEL=dict(analyzer.MODEL,model_bundle_id="different-bundle")
            return analyzer
        self.api._new_analyzer=incompatible
        count=len(self.backend.opens)
        self.api.post_action(sid,command(snapshot,"resume-after-restart","resume"))
        failed=self.wait(sid,lambda s:s["capture"]["state"]=="unavailable")
        self.assertIn("incompatible_reference_model_profile",str(failed["capture"]["reason_codes"]))
        self.assertEqual(count,len(self.backend.opens))
        self.assertIsNone(failed["latest_frame"])
        self.api._new_analyzer=original_factory
        self.switch(failed,"mic-b","correct-model")
        current=self.wait(sid,lambda s:s["capture"]["state"]=="active")
        self.assertEqual(old["active_reference"],current["active_reference"])

    def test_pending_native_open_coalesces_repeated_pause_resume(self):
        entered=threading.Event();release=threading.Event();original=self.backend.open
        def blocked(**kwargs):
            entered.set();release.wait(4);return original(**kwargs)
        self.backend.open=blocked
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        try:
            self.assertTrue(entered.wait(2));runner=self.api.live_audio.tasks[sid]
            for i in range(4):
                snapshot=self.api.get_session(sid)[1]
                self.api.post_action(sid,command(snapshot,f"pending-pause-{i}","pause"))
                snapshot=self.api.get_session(sid)[1]
                self.api.post_action(sid,command(snapshot,f"pending-resume-{i}","resume"))
                self.assertIs(runner,self.api.live_audio.tasks[sid])
                self.assertEqual(1,len(self.api.live_audio.pending_operations))
            self.assertIsNone(self.api.get_session(sid)[1]["latest_frame"])
        finally:release.set()
        self.wait(sid,lambda s:s["capture"]["state"]=="active")
        self.assertTrue(all(s.closed for s in self.backend.streams[:-1]))
