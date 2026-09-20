"""CP2 managed worker lifecycle and sustained session invariants."""
import tempfile
import time
import unittest
from types import SimpleNamespace

from apps.api.service import RuntimeAPI
from core.audio import FileAudioInput, SharedAudioPipeline
from core.runtime import FakeEvidenceSpec
from tests.integration import test_api_service as api_fixtures
from tests.integration.test_api_service import command
from tests.integration import test_pa_vertical_slice as pa_fixtures


class Backend:
    def __init__(self):
        self.streams=[]
        self.fail=False
    def discover(self):
        return [SimpleNamespace(device_id='mic-1')]
    def open(self,**kwargs):
        backend=self
        class Stream:
            closed=False
            def start(self):
                if backend.fail:
                    raise RuntimeError('test_open_failure')
            def abort(self):
                pass
            def close(self):
                self.closed=True
        stream=Stream();self.streams.append(stream);return stream


class ManagedWorkerTests(unittest.TestCase):
    def test_native_open_pause_resume_stop_and_old_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            backend=Backend()
            api=RuntimeAPI(storage_dir=directory,window_size_samples=10,native_backend=backend,managed_audio=True)
            self.addCleanup(api.close)
            _,_,_,snapshot=api_fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)
            sid=snapshot['session_id'];session=api.runtime_session(sid)
            self.assertEqual(1,len(backend.streams))
            self.assertFalse(session.capture_runtime_verified)
            self.assertEqual('unverified',session.capture_fingerprint['provenance'])
            self.assertIsNone(session.capture_fingerprint['enhancements_verified_disabled'])
            _,paused=api.post_action(sid,command(api.get_session(sid)[1],'pause','pause'))
            self.assertTrue(backend.streams[0].closed)
            resume=command(paused['snapshot'],'resume','resume')
            status,result=api.post_action(sid,resume);self.assertEqual(200,status)
            self.assertEqual(2,len(backend.streams))
            api.post_action(sid,command(api.get_session(sid)[1],'stop','stop'))
            self.assertTrue(backend.streams[-1].closed)
            status,retry=api.post_action(sid,resume)
            self.assertEqual(result,retry)
            self.assertEqual(2,len(backend.streams))
            self.assertEqual('STOPPED',api.get_session(sid)[1]['song']['workflow_state'])
            api.close()

    def test_native_failure_is_suspended_and_resume_reopens(self):
        with tempfile.TemporaryDirectory() as directory:
            backend=Backend();backend.fail=True
            api=RuntimeAPI(storage_dir=directory,window_size_samples=10,native_backend=backend,managed_audio=True)
            self.addCleanup(api.close)
            _,_,_,snap=api_fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)
            sid=snap['session_id']
            self.assertEqual('SUSPENDED',snap['song']['workflow_state'])
            self.assertIn('test_open_failure',snap['suspension_reasons'][0])
            backend.fail=False
            api.post_action(sid,command(snap,'resume','resume'))
            self.assertEqual(2,len(backend.streams))
            self.assertEqual('REHEARSAL',api.get_session(sid)[1]['song']['workflow_state'])
            api.close()

    def test_file_worker_eof_resume_new_run_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=5,hop_size_samples=5,
                           available_audio_devices={'mic-1'})
            _,asset,job,old=api_fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)
            api.managed_audio=True
            capture=dict(api.runtime_session(old['session_id']).capture_fingerprint)
            capture['device_id']=asset['asset_id']
            _,snap=api.create_session(dict(song_id=old['song']['song_id'],reference_id=job['reference_id'],
                source=dict(input_kind='uploaded_file',input_asset_or_device_id=asset['asset_id']),capture_fingerprint=capture))
            sid=snap['session_id']
            try:
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    snap=api.get_session(sid)[1]
                    if snap['song']['workflow_state']=='SUSPENDED':break
                    time.sleep(.02)
                self.assertEqual(['audio_eof'],snap['suspension_reasons'])
                old_run=snap['latest_frame']['analysis_run_id']
                self.assertTrue(snap['latest_frame']['example_only'])
                self.assertTrue(all(x['confidence']['abstained'] for x in snap['latest_frame']['instruments']))
                api.post_action(sid,command(snap,'resume-file','resume'))
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    latest=api.get_session(sid)[1]['latest_frame']
                    if latest and latest['analysis_run_id']!=old_run:break
                    time.sleep(.02)
                self.assertNotEqual(old_run,latest['analysis_run_id'])
            finally:
                api.close()


class SustainedSessionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pa_fixtures.PAVerticalSliceTests();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_overlap_baseline_counts_unique_seconds_and_nonoverlap_windows(self):
        f=self.fixture
        source=FileAudioInput(input_asset_or_device_id='mic-1',clock_id='clock-1',sample_rate_hz=10,
                             samples=[.1]*60,origin_monotonic_s=1,chunk_size_samples=3)
        # Adapt just the source kind; use the exact same shared PCM/framing.
        source.input_kind='live_microphone'
        ws=list(SharedAudioPipeline(window_size_samples=10,hop_size_samples=5).iter_windows(
            source,session_id='session-1',analysis_run_id='overlap'))
        for w in ws:
            f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0)))
            f.session.observe_window(w)
        payload=dict(interval=dict(analysis_run_id='overlap',clock_id='clock-1',sample_rate_hz=10,
                                  sample_start=0,sample_end=60),accepted_by='human',reference_difference_accepted=False,
                     acceptance_note=None)
        result=f.apply('accept-overlap','accept_baseline',payload)
        for item in result['snapshot']['active_baseline']['coverage']:
            self.assertEqual(6,item['valid_active_seconds'])
            self.assertEqual(6,item['qualified_nonoverlap_windows'])

    def test_frame_hash_and_event_history_are_bounded(self):
        f=self.fixture;f.session.frame_retention=8
        for i in range(35):
            f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0)))
            f.session.observe_window(f.window(f'run-{i}',i+1))
        self.assertEqual(8,len(f.session._frames))
        self.assertEqual(8,len(f.session._frame_audio_hashes))
        self.assertLessEqual(len(f.session._events),f.session.event_retention)
        old=dict(analysis_run_id='run-0',clock_id='clock-1',sample_rate_hz=10,sample_start=0,sample_end=10)
        result=f.handler.handle(command(f.session.snapshot(),'old','accept_baseline',dict(interval=old,
            accepted_by='human',reference_difference_accepted=True,acceptance_note=None)))
        self.assertEqual(422,result['http_status'])

    def test_slow_inference_is_stale_at_publication(self):
        f=self.fixture;w=f.window('slow',1);f.clock.value=2
        original=f.analyzer.analyze
        def slow(window,context):
            evidence=original(window,context);f.clock.value+=3;return evidence
        f.analyzer.analyze=slow
        f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=4,bass=0,drums=0)))
        result=f.session.observe_window(w,max_age_s=2)
        self.assertTrue(result['quality']['stale'])
        self.assertTrue(all(x['confidence']['abstained'] for x in result['instruments']))
        self.assertIsNone(f.session.incident)

    def test_candidate_completion_budget_accepts_six_seconds_but_rejects_over_twenty(self):
        for delay,stale in ((6,False),(20.01,True)):
            with self.subTest(delay=delay):
                f=self.fixture;w=f.window(f'candidate-{delay}',1);f.clock.value=2
                original=f.analyzer.analyze
                def slow(window,context):
                    evidence=original(window,context);f.clock.value+=delay;return evidence
                f.analyzer.analyze=slow
                f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=4,bass=0,drums=0)))
                result=f.session.observe_window(w,max_age_s=20)
                self.assertEqual(stale,result['quality']['stale'])
                f.analyzer.analyze=original

    def test_physical_gap_suppresses_old_verification_but_preserves_workflow(self):
        f=self.fixture;f.open_persistent_incident('gap-verification',2)
        f.apply('gap-start','start_adjustment');f.clock.value=10
        adjustment_id=f.session.snapshot()['adjustment']['adjustment_id']
        f.apply('gap-complete','complete_adjustment',{'adjustment_id':adjustment_id})
        f.apply('gap-recheck','recheck',{'adjustment_id':adjustment_id})
        f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0)))
        f.session.observe_window(f.window('gap-recovered',12))
        before=f.session.snapshot();self.assertIsNotNone(before['latest_verification'])
        incident=before['incident'];adjustment=before['adjustment']
        self.assertTrue(f.session.suppress_for_capture_gap())
        after=f.session.snapshot()
        self.assertIsNone(after['latest_verification'])
        self.assertEqual(incident,after['incident']);self.assertEqual(adjustment,after['adjustment'])

    def test_silent_pcm_cannot_be_scripted_into_recovery_or_normal(self):
        from dataclasses import replace
        f=self.fixture
        w=replace(f.window('silent',1),samples=(0.0,)*10)
        f.analyzer.queue(FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0)))
        result=f.session.observe_window(w)
        self.assertEqual('weak',result['quality']['comparability'])
        self.assertTrue(all(x['confidence']['abstained'] for x in result['instruments']))

    def test_durable_audit_is_immutable_and_not_lost_when_tail_is_trimmed(self):
        from apps.api.persistence import SQLiteRuntimeStore
        f=self.fixture
        store=SQLiteRuntimeStore(f.temporary.name+'/audit.sqlite3')
        f.session.set_persistence_callback(store.save_session)
        for i in range(140):
            f.session._audit('test-audit',{'index':i})
            store.save_session(f.session.export_state())
        self.assertEqual(128,len(f.session.audit_records()))
        self.assertEqual(140,len(store.load_audit('session-1')))
        state=f.session.export_state();state['audit_records'][-1]['payload']['index']=-1
        with self.assertRaisesRegex(ValueError,'immutable audit'):
            store.save_session(state)
        self.assertEqual(139,store.load_audit('session-1')[-1]['payload']['index'])

    def test_event_polling_does_not_write_unchanged_session(self):
        f=self.fixture;writes=[]
        f.session.set_persistence_callback(lambda state:writes.append(state))
        for _ in range(100):
            self.assertEqual([],f.session.events_after(0))
        self.assertEqual([],writes)

    def test_capture_rate_change_is_rejected_before_perception(self):
        from dataclasses import replace
        f=self.fixture;w=replace(f.window('rate-change',1),sample_rate_hz=20)
        with self.assertRaisesRegex(ValueError,'sample rate changed'):
            f.session.observe_window(w)
        self.assertIsNone(f.session.latest_frame)

    def test_verification_cutoff_includes_native_clock_uncertainty(self):
        f=self.fixture;f.open_persistent_incident('clock-guard',2)
        f.apply('adjust','start_adjustment');f.clock.value=10
        response=f.apply('complete','complete_adjustment',{'adjustment_id':f.session.adjustment['adjustment_id']})
        adjustment=response['snapshot']['adjustment'];cutoff=adjustment['verification_not_before_monotonic_s']
        f.apply('recheck','recheck',{'adjustment_id':adjustment['adjustment_id']})
        normal=FakeEvidenceSpec(deltas_db=dict(guitar=0,bass=0,drums=0))
        f.analyzer.queue(normal,normal)
        f.session.observe_window(f.window('too-close',cutoff+.01),clock_uncertainty_s=.05)
        self.assertIsNone(f.session.latest_verification)
        f.session.observe_window(f.window('fully-fresh',cutoff+.1),clock_uncertainty_s=.05)
        self.assertEqual('recovered',f.session.latest_verification['outcome'])

    def test_cp1_injected_fake_fixture_can_use_its_scripted_sample_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=10,available_audio_devices={'mic-1'})
            _,_,_,snap=api_fixtures.RuntimeAPIServiceTests.create_rehearsal_session(api)
            session=api.runtime_session(snap['session_id'])
            # The frozen UI smoke declares the nominal 48 kHz device while its
            # private Fake hook deliberately injects a tiny 10 Hz fixture.
            session.capture_fingerprint['native_sample_rate_hz']=48000
            source=FileAudioInput(input_asset_or_device_id='mic-1',clock_id=session.source['clock_id'],
                sample_rate_hz=10,samples=[.1]*10,origin_monotonic_s=1)
            source.input_kind='live_microphone'
            w=next(api.pipeline.iter_windows(source,session_id=session.session_id,analysis_run_id='fake-only'))
            result=session.observe_window(w)
            self.assertTrue(result['example_only'])
            self.assertFalse(session.capture_profile_enforced)

if __name__=='__main__':unittest.main()
