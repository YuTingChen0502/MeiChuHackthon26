"""Native sample continuity when optional PortAudio timestamps are absent."""
import struct
import unittest
from types import SimpleNamespace
from core.audio.native import NativeMicAudioInput
from core.audio import SharedAudioPipeline


class NativeClockTests(unittest.TestCase):
    def make(self, capacity=8):
        self.now=10.0
        return NativeMicAudioInput(backend=None,device_id="mic",clock_id="clock",sample_rate_hz=100,
            block_size=10,queue_capacity=capacity,clock=lambda:self.now)
    def packet(self,mic,adc=None,status=False):
        timing=SimpleNamespace() if adc is None else SimpleNamespace(inputBufferAdcTime=adc,currentTime=adc+.1)
        mic._callback(struct.pack("=10f",*([.1]*10)),10,timing,status)
        self.now+=.1
    def test_missing_zero_nonfinite_then_valid_does_not_reanchor_or_fail(self):
        mic=self.make();stream=mic.chunks();chunks=[]
        for adc in (None,0,float("nan"),float("inf"),1.4,1.5):
            self.packet(mic,adc);chunks.append(next(stream))
        self.assertEqual(0,mic.discontinuities)
        self.assertEqual(4,mic.fallback_packets);self.assertEqual(2,mic.adc_packets)
        self.assertEqual("monotonic_fallback",mic.clock_mode)
        self.assertEqual("adc_sample_count",mic.timestamp_mode)
        self.assertEqual(list(range(0,60,10)),[c.sample_start for c in chunks])
        for i,c in enumerate(chunks):self.assertAlmostEqual(10+i*.1,c.capture_end_monotonic_s)
        windows=list(SharedAudioPipeline(window_size_samples=20,hop_size_samples=10).windows_from_chunks(
            chunks,session_id="s",analysis_run_id="r"))
        self.assertEqual(5,len(windows));mic.close();stream.close()
    def test_valid_adc_missing_metadata_and_return_keep_continuity(self):
        mic=self.make();stream=mic.chunks()
        for adc in (1,None,1.2):self.packet(mic,adc);next(stream)
        self.assertEqual("adc",mic.clock_mode);self.assertEqual(0,mic.discontinuities)
        self.packet(mic,4);chunk=next(stream)
        self.assertEqual(31,chunk.sample_start);self.assertEqual(1,mic.discontinuities)
        mic.close();stream.close()
    def test_status_and_late_fallback_explicitly_break_sample_spans(self):
        mic=self.make();stream=mic.chunks()
        self.packet(mic);first=next(stream)
        self.packet(mic,status=True);second=next(stream)
        self.now+=1;self.packet(mic);third=next(stream)
        self.assertEqual((0,11,22),(first.sample_start,second.sample_start,third.sample_start))
        self.assertEqual(2,mic.discontinuities);mic.close();stream.close()
    def test_fallback_queue_drop_is_visible_and_reopen_gets_new_identity(self):
        mic=self.make(capacity=1);stream=mic.chunks()
        self.packet(mic);self.packet(mic);first=next(stream)
        self.packet(mic);third=next(stream)
        self.assertEqual((0,20),(first.sample_start,third.sample_start))
        self.assertEqual(1,mic.dropped_packets);mic.close();stream.close()
        self.packet(mic);self.assertEqual(30,mic._next_sample)
        new=self.make();new.clock_id="new-clock";self.packet(new)
        stream=new.chunks();chunk=next(stream)
        self.assertEqual(0,chunk.sample_start);self.assertEqual("new-clock",chunk.clock_id)
        new.close();stream.close()
