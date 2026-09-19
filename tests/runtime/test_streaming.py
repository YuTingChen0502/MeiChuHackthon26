"""Deterministic capture, backpressure, overlap and confidence regression tests."""
import copy
import struct
import threading
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace

from core.audio import FileAudioInput, SharedAudioPipeline
from core.audio.native import NativeMicAudioInput
from core.audio.types import AudioChunk
from core.runtime.worker import AudioWorker
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer, FakeEvidenceSpec
from core.runtime.deviation import FrameBuilder
from core.runtime.quality import quality_state
from roles.pa.policy import PersistentAnomalyPolicy


def windows(count=20, size=4, hop=1):
    source = FileAudioInput(input_asset_or_device_id='asset', clock_id='clock', sample_rate_hz=10,
                            samples=[.1] * count, origin_monotonic_s=1, chunk_size_samples=3)
    return list(SharedAudioPipeline(window_size_samples=size, hop_size_samples=hop).iter_windows(
        source, session_id='s', analysis_run_id='r'))


def context(window, analyzer):
    return dict(record_type='AnalyzerContext', schema_version='1.0', observation=window.identity(),
        model=analyzer.capabilities()['model'], instrument_config=dict(instrument_config_version=1,
        instruments=[dict(instrument_id=x, family=x) for x in ('guitar','bass','drums')]),
        target=dict(target_kind='reference', reference=dict(reference_id='ref', source_asset_hash='sha256:x'), baseline=None),
        comparison_regime='matched_excerpt', model_specific_context_asset='fake-context',
        observation_purpose='rehearsal', probe_instrument_id=None)


def frame(window, gain=4, real=False):
    analyzer = ContinuousFakeInstrumentAnalyzer([FakeEvidenceSpec(deltas_db=dict(guitar=gain,bass=0,drums=0))])
    ctx = context(window, analyzer)
    evidence = analyzer.analyze(window, ctx)
    evidence['example_only'] = not real
    return FrameBuilder().build(context=ctx, evidence=evidence, quality=quality_state(),
        frame_id=window.window_id, sequence=1, published_monotonic_s=20)


class StreamingTests(unittest.TestCase):
    def test_infinite_iterator_is_consumed_incrementally(self):
        consumed = []
        def chunks():
            for start in range(1000000):
                consumed.append(start)
                yield AudioChunk('uploaded_file','a','c',10,start,1+(start+1)/10,(.2,))
        stream = SharedAudioPipeline(window_size_samples=40,hop_size_samples=10).windows_from_chunks(
            chunks(),session_id='s',analysis_run_id='r')
        first, second = next(stream), next(stream)
        self.assertEqual((0,40,10,50), (first.sample_start,first.sample_end,second.sample_start,second.sample_end))
        self.assertEqual(50,len(consumed))
        stream.close()

    def test_overlap_identity_and_amplitude(self):
        result=windows()
        self.assertEqual(17,len(result))
        for i,w in enumerate(result):
            self.assertEqual((i,i+4),(w.sample_start,w.sample_end))
            self.assertAlmostEqual(1+(i+4)/10,w.capture_end_monotonic_s)
            self.assertEqual((.1,)*4,w.samples)

    def test_gap_clock_change_and_nonfinite_are_rejected(self):
        first=AudioChunk('uploaded_file','a','c',10,0,1.2,(.2,.2))
        for bad in (replace(first,sample_start=3,capture_end_monotonic_s=1.5),
                    replace(first,sample_start=2,capture_end_monotonic_s=99),
                    replace(first,sample_start=2,capture_end_monotonic_s=1.4,clock_id='other'),
                    replace(first,sample_start=2,capture_end_monotonic_s=1.4,samples=(float('nan'),.2))):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                list(SharedAudioPipeline(window_size_samples=4).windows_from_chunks([first,bad],session_id='s',analysis_run_id='r'))

    def test_nonfake_never_inherits_simulated_confidence(self):
        result=frame(windows()[0],real=True)
        self.assertFalse(result['example_only'])
        self.assertIsNone(result['common_mode_gain_db'])
        for state in result['instruments']:
            self.assertEqual('uncalibrated',state['confidence']['calibration_status'])
            self.assertTrue(state['confidence']['abstained'])
            self.assertIsNone(state['confidence']['probability'])
            self.assertIsNone(state['confidence']['prediction_interval_db'])
            self.assertIsNone(state['balance_deviation_db'])

    def test_overlapping_windows_do_not_count_as_independent_support(self):
        policy=PersistentAnomalyPolicy(required_frames=2)
        items=windows()
        for window in items[:4]:
            self.assertIsNone(policy.observe(frame(window)))
        result=policy.observe(frame(items[4]))
        self.assertIsNotNone(result)
        self.assertEqual([items[0].window_id,items[4].window_id],result[1])

    def test_worker_drops_old_work_and_records_discontinuities(self):
        entered,release,done=threading.Event(),threading.Event(),threading.Event()
        received=[]
        class Source:
            def chunks(self):
                for start in range(0,100,4):
                    yield AudioChunk('uploaded_file','a','c',10,start,1+(start+4)/10,(.1,)*4)
                    if start==0:
                        entered.wait(2)
                release.set()
        def observe(window,quality,age):
            if not received:
                entered.set()
                release.wait(2)
            received.append((window,quality))
        worker=AudioWorker(audio_input=Source(),pipeline=SharedAudioPipeline(window_size_samples=4),
            session_id='s',on_window=observe,on_end=lambda r:done.set(),clock=lambda:11,max_age_s=20,queue_capacity=2)
        worker.start()
        self.assertTrue(done.wait(3))
        worker.stop()
        self.assertGreater(worker.dropped_windows,0)
        self.assertLessEqual(worker.max_queue_depth,2)
        self.assertTrue(received[-1][1]['dropout']) if len(received)==2 else self.assertTrue(received[1][1]['dropout'])

    def test_worker_stale_windows_never_reach_analyzer(self):
        done=threading.Event();received=[]
        source=FileAudioInput(input_asset_or_device_id='a',clock_id='c',sample_rate_hz=10,
            samples=[.1]*40,origin_monotonic_s=1,chunk_size_samples=4)
        worker=AudioWorker(audio_input=source,pipeline=SharedAudioPipeline(window_size_samples=4),
            session_id='s',on_window=lambda *a:received.append(a),on_end=lambda r:done.set(),clock=lambda:100)
        worker.start();self.assertTrue(done.wait(2));worker.stop()
        self.assertEqual([],received);self.assertGreater(worker.stale_windows,0)

    def test_callback_backpressure_preserves_sample_holes(self):
        mic=NativeMicAudioInput(backend=None,device_id='mic',clock_id='clock',sample_rate_hz=10,
                               block_size=2,queue_capacity=1,clock=lambda:100)
        raw=struct.pack('=2f',.125,-.25)
        timing=lambda adc:SimpleNamespace(inputBufferAdcTime=adc,currentTime=adc+.2)
        mic._callback(raw,2,timing(1),False)
        mic._callback(raw,2,timing(1.2),False)
        stream=mic.chunks();first=next(stream)
        mic._callback(raw,2,timing(1.4),False);third=next(stream)
        self.assertEqual((0,4),(first.sample_start,third.sample_start))
        self.assertEqual(1,mic.dropped_packets)
        self.assertEqual((.125,-.25),third.samples)
        mic.close();stream.close()

    def test_missing_adc_uses_sample_count_fallback(self):
        mic=NativeMicAudioInput(backend=None,device_id='mic',clock_id='clock',sample_rate_hz=10,
            block_size=2,clock=lambda:10)
        mic._callback(struct.pack('=2f',.1,.2),2,SimpleNamespace(inputBufferAdcTime=0,currentTime=1),False)
        stream=mic.chunks();chunk=next(stream)
        self.assertEqual((0,2),(chunk.sample_start,chunk.sample_end))
        self.assertEqual(10,chunk.capture_end_monotonic_s)
        self.assertEqual('monotonic_fallback',mic.clock_mode)
        self.assertIsNone(mic.error)
        mic.close();stream.close()

    def test_capture_gap_produces_new_run_and_no_straddling_window(self):
        done=threading.Event();seen=[]
        class Source:
            def chunks(self):
                for start in (0,2,9,11):
                    yield AudioChunk('live_microphone','m','c',10,start,1+(start+2)/10,(.1,)*2)
        worker=AudioWorker(audio_input=Source(),pipeline=SharedAudioPipeline(window_size_samples=4),session_id='s',
            on_window=lambda w,q,a:seen.append((w,q)),on_end=lambda r:done.set(),clock=lambda:3,max_age_s=5)
        worker.start();self.assertTrue(done.wait(2));worker.stop()
        self.assertEqual([(0,4),(9,13)],[(w.sample_start,w.sample_end) for w,q in seen])
        self.assertNotEqual(seen[0][0].analysis_run_id,seen[1][0].analysis_run_id)
        self.assertTrue(seen[1][1]['dropout'])

    def test_native_timestamp_jitter_is_bounded_but_clock_jump_breaks_span(self):
        mic=NativeMicAudioInput(backend=None,device_id='mic',clock_id='clock',sample_rate_hz=48000,
                               block_size=1024,queue_capacity=8,clock=lambda:100)
        raw=struct.pack('=1024f',*([.1]*1024))
        for adc in (1,1+1024/48000+.003,1+2048/48000-.003):
            mic._callback(raw,1024,SimpleNamespace(inputBufferAdcTime=adc,currentTime=adc+.03),False)
        self.assertEqual(0,mic.discontinuities)
        mic._callback(raw,1024,SimpleNamespace(inputBufferAdcTime=4,currentTime=4.03),False)
        self.assertEqual(1,mic.discontinuities)
        values=mic.chunks()
        chunks=[next(values) for _ in range(4)]
        self.assertEqual(chunks[2].sample_end+1,chunks[3].sample_start)
        mic.close();values.close()

    def test_real_adapter_rejects_simulated_evidence_and_changed_identity(self):
        from core.runtime.real_analyzer import RealAnalyzerAdapter
        class ProductionBoundaryProbe(ContinuousFakeInstrumentAnalyzer):
            def capabilities(self):
                value=super().capabilities();value['example_only']=False;return value
        analyzer=ProductionBoundaryProbe()
        adapter=RealAnalyzerAdapter(analyzer)
        window=windows()[0]
        with self.assertRaisesRegex(ValueError,'simulated calibration'):
            adapter.analyze(window,context(window,adapter))
        ctx=context(window,adapter);ctx['observation']['sample_start']=999
        with self.assertRaisesRegex(ValueError,'runtime identity'):
            adapter.analyze(window,ctx)

    def test_live_and_file_pcm_produce_same_downstream_simulated_state(self):
        file_window=windows()[0]
        live_window=replace(file_window,input_kind='live_microphone',input_asset_or_device_id='native',analysis_run_id='live')
        self.assertEqual(frame(file_window)['instruments'],frame(live_window)['instruments'])

    def test_close_failure_still_notifies_and_joins_worker(self):
        done=threading.Event();reasons=[]
        class Source:
            def chunks(self):
                return iter(())
            def close(self):
                raise RuntimeError('driver_close_failure')
        def ended(reason):
            reasons.append(reason);done.set()
        worker=AudioWorker(audio_input=Source(),pipeline=SharedAudioPipeline(window_size_samples=4),
            session_id='s',on_window=lambda *args:None,on_end=ended)
        worker.start();self.assertTrue(done.wait(2));worker.stop()
        self.assertIn('driver_close_failure',reasons[0])
        self.assertFalse(worker._producer.is_alive())
        self.assertFalse(worker._consumer.is_alive())

    def test_native_clock_resolution_does_not_drop_slightly_future_boundary(self):
        for offset, expected_count in ((.01,1),(.2,0)):
            with self.subTest(offset=offset):
                done=threading.Event();seen=[]
                class Source:
                    def chunks(self):
                        yield AudioChunk('live_microphone','m','c',48000,0,10+offset,(.1,)*4)
                worker=AudioWorker(audio_input=Source(),pipeline=SharedAudioPipeline(window_size_samples=4),
                    session_id='s',on_window=lambda *args:seen.append(args),on_end=lambda r:done.set(),clock=lambda:10)
                worker.start();self.assertTrue(done.wait(2));worker.stop()
                self.assertEqual(expected_count,len(seen))

    def test_pcm16_positive_rail_is_not_missed_by_clipping_gate(self):
        from core.runtime.quality import pcm_clipped_fraction
        self.assertEqual(.5,pcm_clipped_fraction((32767/32768,-1.0,0.0,.5)))
        self.assertEqual(0.0,pcm_clipped_fraction((.1,-.5,.9)))


if __name__=='__main__':
    unittest.main()
