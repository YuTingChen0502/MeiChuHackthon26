"""Explicit deletion is durable and fences asynchronous capture/model work."""
import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from contextlib import closing

from apps.api.service import RuntimeAPI,APIError
from apps.api.persistence import DeletedSessionError,SQLiteRuntimeStore
import test_api_service as api_fixture
from test_api_service import command,wav_bytes
from test_live_reference_runtime import Backend


class SessionDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.backend=Backend()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=1024,hop_size_samples=1024,
            analysis_sample_rate_hz=48000,native_backend=self.backend,managed_audio=True)
        _,project=self.api.create_project({"name":"Delete test"})
        _,song=self.api.create_song(dict(project_id=project["project_id"],name="Shared song",
            instruments=[dict(instrument_id="bass",family="bass")]))
        _,asset=self.api.upload_audio(wav_bytes([.1]*4096,sample_rate=48000),filename="generated.wav")
        _,job=self.api.start_reference_job(song["song_id"],dict(asset_id=asset["asset_id"]))
        self.api.run_reference_job(job["job_id"])
        self.request=dict(song_id=song["song_id"],reference_id=job["reference_id"],workflow_policy="live_reference_v1")
    def tearDown(self):
        self.api.close();self.temp.cleanup()
    def wait(self,predicate,timeout=3):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return
            time.sleep(.01)
        self.fail("condition did not complete")
    def start(self):
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        self.wait(lambda:self.api.get_session(sid)[1]["capture"]["state"]=="active" and
            not self.api.live_audio.tasks[sid].is_alive())
        return self.api.get_session(sid)[1]
    def assert_missing(self,sid):
        with self.assertRaises(APIError) as error:self.api.get_session(sid)
        self.assertEqual(404,error.exception.status)
        self.assertNotIn(sid,self.api.handlers)
        self.assertFalse(any(s["session_id"]==sid for s in self.api._store.load_sessions()))
    def test_stopped_delete_removes_only_session_records_and_survives_restart(self):
        first=self.start();sid=first["session_id"];other=self.start()
        self.api.post_action(sid,command(self.api.get_session(sid)[1],"stop-before-delete","stop"))
        state=self.api.runtime_session(sid).export_state()
        retained=copy.deepcopy(self.api._runtime_state_payload())
        # Existing baseline records are shared immutable assets, outside deletion.
        with closing(sqlite3.connect(self.api._store.path)) as con:
            con.execute("INSERT INTO baselines VALUES(?,?,?)",("retained-baseline",1,'{}'))
            con.commit()
        self.assertEqual((200,dict(session_id=sid,deleted=True)),self.api.delete_session(sid))
        self.assertEqual((200,dict(session_id=sid,deleted=True)),self.api.delete_session(sid))
        self.assert_missing(sid)
        self.assertEqual(retained,self.api._runtime_state_payload())
        self.assertEqual(other["session_id"],self.api.get_session(other["session_id"])[1]["session_id"])
        with closing(sqlite3.connect(self.api._store.path)) as con:
            for table in ("sessions","commands","session_audit"):
                self.assertEqual(0,con.execute(f"SELECT count(*) FROM {table} WHERE session_id=?",(sid,)).fetchone()[0])
            self.assertEqual(1,con.execute("SELECT count(*) FROM baselines").fetchone()[0])
        self.api.close()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=1024,hop_size_samples=1024,
            analysis_sample_rate_hz=48000,native_backend=self.backend,managed_audio=True)
        self.assert_missing(sid)
        with self.assertRaises(DeletedSessionError):self.api._store.save_session(state)
        third=self.start();self.assertGreater(int(third["session_id"].split("-")[1]),int(other["session_id"].split("-")[1]))
    def test_inflight_live_inference_is_fenced_and_model_close_is_deferred(self):
        snapshot=self.start();sid=snapshot["session_id"];session=self.api.runtime_session(sid)
        worker=self.api.workers[sid];analyzer=session.analyzer
        original=analyzer.analyze;entered=threading.Event();release=threading.Event()
        def blocked(window,context):
            entered.set();release.wait(4);return original(window,context)
        analyzer.analyze=blocked
        try:
            self.assertTrue(entered.wait(2));begin=time.monotonic()
            self.api.delete_session(sid)
            self.assertLess(time.monotonic()-begin,.7)
            self.assert_missing(sid)
            self.assertTrue(all(s.closed for s in self.backend.streams))
            self.assertFalse(analyzer.closed)
            self.assertFalse(worker.on_window(None,{},2))
            worker.on_end("late-disconnect")
            with self.assertRaises(APIError) as error:self.api.post_action(sid,command(snapshot,"late-command","stop"))
            self.assertEqual(404,error.exception.status)
        finally:release.set()
        self.wait(lambda:analyzer.closed)
        self.assert_missing(sid)
    def test_delete_pending_open_closes_late_stream_without_capture(self):
        entered=threading.Event();release=threading.Event();original=self.backend.open
        def blocked(**kwargs):entered.set();release.wait(4);return original(**kwargs)
        self.backend.open=blocked
        _,snapshot=self.api.create_session(self.request);sid=snapshot["session_id"]
        try:
            self.assertTrue(entered.wait(2));self.api.delete_session(sid);self.assert_missing(sid)
        finally:release.set()
        self.wait(lambda:self.backend.streams and all(s.closed for s in self.backend.streams))
        self.assertTrue(all(s.thread is None for s in self.backend.streams))
        self.assert_missing(sid)
    def test_every_durable_writer_rejects_deleted_state_even_from_second_store(self):
        snapshot=self.start();sid=snapshot["session_id"];state=self.api.runtime_session(sid).export_state()
        runtime=copy.deepcopy(self.api._runtime_state_payload());other=SQLiteRuntimeStore(self.api._store.path)
        self.api.delete_session(sid)
        for operation in (
            lambda:other.save_session(state),
            lambda:other.save_runtime_and_session(runtime,state),
            lambda:other.record_command(session_id=sid,idempotency_key="late",command_text="{}",response={},session_state=state)):
            with self.assertRaises(DeletedSessionError):operation()
        self.assert_missing(sid)
    def test_failed_durable_delete_is_not_success_and_can_retry(self):
        snapshot=self.start();sid=snapshot["session_id"]
        with patch.object(self.api._store,"delete_session",side_effect=RuntimeError("disk unavailable")):
            with self.assertRaises(APIError) as error:self.api.delete_session(sid)
            self.assertEqual(503,error.exception.status)
        self.assertEqual("unavailable",self.api.get_session(sid)[1]["capture"]["state"])
        self.assertFalse(self.api._store.is_deleted(sid))
        self.api.delete_session(sid);self.assert_missing(sid)
    def test_missing_delete_idempotent_and_reserved_id_never_reused(self):
        for identity in ("absent", "session-1"):
            self.assertEqual(self.api.delete_session(identity),self.api.delete_session(identity))
        snapshot=self.start();self.assertEqual("session-2",snapshot["session_id"])

    def test_legacy_inference_delete_releases_capture_before_model_finishes(self):
        request=dict(self.request);request.pop("workflow_policy")
        request.update(source=dict(input_kind="live_microphone",input_asset_or_device_id="mic-a"),
            capture_fingerprint=dict(device_id="mic-a",profile_id="unverified",native_sample_rate_hz=48000,
                channels=1,gain_setting=None,enhancements_verified_disabled=None,geometry_id=None,provenance="unverified"))
        _,snapshot=self.api.create_session(request);sid=snapshot["session_id"];session=self.api.runtime_session(sid)
        analyzer=session.analyzer;original=analyzer.analyze;entered=threading.Event();release=threading.Event()
        def blocked(window,context):entered.set();release.wait(4);return original(window,context)
        analyzer.analyze=blocked
        try:
            self.assertTrue(entered.wait(2));begin=time.monotonic()
            self.api.delete_session(sid);self.assertLess(time.monotonic()-begin,.7)
            self.assertTrue(all(s.closed for s in self.backend.streams));self.assertFalse(analyzer.closed)
        finally:release.set()
        self.wait(lambda:analyzer.closed)
        self.assertNotIn(sid,self.api._failed_analyzers)
        self.assert_missing(sid)

    def test_sql_failure_rolls_back_tombstone_and_all_deleted_records(self):
        snapshot=self.start();sid=snapshot["session_id"]
        self.api.post_action(sid,command(self.api.get_session(sid)[1],"pause-audit","pause"))
        with closing(sqlite3.connect(self.api._store.path)) as con:
            con.execute("INSERT OR IGNORE INTO session_audit VALUES(?,?,?)",(sid,999,'{}'))
            con.execute("CREATE TRIGGER reject_delete BEFORE DELETE ON session_audit BEGIN SELECT RAISE(ABORT,'injected'); END")
            con.commit()
        with self.assertRaises(APIError):self.api.delete_session(sid)
        self.assertFalse(self.api._store.is_deleted(sid))
        with closing(sqlite3.connect(self.api._store.path)) as con:
            for table in ("sessions","commands","session_audit"):
                self.assertGreater(con.execute(f"SELECT count(*) FROM {table} WHERE session_id=?",(sid,)).fetchone()[0],0)
            con.execute("DROP TRIGGER reject_delete");con.commit()
        self.api.delete_session(sid);self.assert_missing(sid)

    def test_late_persistence_callback_cancels_without_breaking_other_sessions(self):
        snapshot=self.start();sid=snapshot["session_id"];state=self.api.runtime_session(sid).export_state()
        other=self.start();original=self.api._store.save_session
        entered=threading.Event();release=threading.Event();failures=[]
        def delayed(value):
            if value["session_id"]==sid:entered.set();release.wait(3)
            return original(value)
        def writer():
            try:self.api._save_session_state(sid,state)
            except Exception as exc:failures.append(exc)
        with patch.object(self.api._store,"save_session",side_effect=delayed):
            thread=threading.Thread(target=writer);thread.start()
            try:
                self.assertTrue(entered.wait(2));self.api.delete_session(sid)
            finally:release.set();thread.join(2)
        self.assertEqual([],failures);self.assert_missing(sid)
        self.assertTrue(self.api.live_audio._monitor.is_alive())
        self.assertEqual("active",self.api.get_session(other["session_id"])[1]["capture"]["state"])

    def test_command_racing_delete_cannot_recreate_command_ledger(self):
        snapshot=self.start();sid=snapshot["session_id"];handler=self.api.handlers[sid]
        original=handler.handle;entered=threading.Event();release=threading.Event();failures=[]
        def delayed(body):entered.set();release.wait(3);return original(body)
        def invoke(operation):
            try:operation()
            except Exception as exc:failures.append(exc)
        with patch.object(handler,"handle",side_effect=delayed):
            action=threading.Thread(target=invoke,args=(lambda:self.api.post_action(sid,command(snapshot,"racing-stop","stop")),))
            action.start();self.assertTrue(entered.wait(2))
            deletion=threading.Thread(target=invoke,args=(lambda:self.api.delete_session(sid),));deletion.start()
            release.set();action.join(2);deletion.join(2)
        self.assertEqual([],failures);self.assert_missing(sid)
        self.assertIsNone(self.api._store.get_command(sid,"racing-stop"))
        self.wait(lambda:sid not in self.api.live_audio.closers)
        for mapping in (self.api.live_audio.tasks,self.api.live_audio.retired,self.api.live_audio.cancellations,
                        self.api.live_audio.analyzer_locks,self.api.live_audio.scheduled_keys):
            self.assertNotIn(sid,mapping)


class LegacyDeletionTests(unittest.TestCase):
    def test_legacy_session_is_deleted_without_touching_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={"mic-1"})
            try:
                song,asset,job,snapshot=api_fixture.RuntimeAPIServiceTests.create_rehearsal_session(api)
                api.delete_session(snapshot["session_id"])
                self.assertIn(job["reference_id"],api.references)
                self.assertIn(asset["asset_id"],api.assets)
                self.assertIn(song["song_id"],api.songs)
                self.assertEqual([],api._store.load_sessions())
            finally:api.close()
