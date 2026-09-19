"""Portable frontend/PortAudio contract tests; no microphone access."""
import math
import struct
import unittest
from types import SimpleNamespace
from core.audio import FileAudioInput, MicAudioInput, SharedAudioPipeline
from core.audio.frontend import AudioFrontend
from core.audio.native import NativeMicAudioInput, SoundDeviceBackend


class FrontendTests(unittest.TestCase):
    def render(self, kind, chunk_size):
        source = kind(input_asset_or_device_id="same", clock_id="clock", sample_rate_hz=44100,
                      samples=[.2*math.sin(i*.2) for i in range(4410)], origin_monotonic_s=10,
                      chunk_size_samples=chunk_size)
        return list(SharedAudioPipeline(window_size_samples=480,hop_size_samples=240,sample_rate_hz=48000)
                    .iter_windows(source,session_id="s",analysis_run_id="r"))

    def test_chunk_partition_and_file_mic_equivalence(self):
        first=self.render(FileAudioInput,113)
        second=self.render(MicAudioInput,1024)
        self.assertEqual(len(first),len(second))
        for a,b in zip(first,second):
            self.assertEqual(a.samples,b.samples)
            self.assertEqual((a.sample_start,a.sample_end,a.capture_end_monotonic_s),
                             (b.sample_start,b.sample_end,b.capture_end_monotonic_s))
            self.assertEqual(48000,a.sample_rate_hz)
        self.assertEqual((0,480),(first[0].sample_start,first[0].sample_end))
        self.assertEqual((240,720),(first[1].sample_start,first[1].sample_end))

    def test_downsampling_rejects_above_nyquist_and_preserves_dc(self):
        def convert(samples):
            source=FileAudioInput(input_asset_or_device_id="a",clock_id="c",sample_rate_hz=48000,
                                 samples=samples,origin_monotonic_s=10,chunk_size_samples=64)
            return [v for c in AudioFrontend(16000).chunks(source.chunks()) for v in c.samples][20:]
        dc=convert([.2]*4800)
        self.assertLess(max(abs(v-.2) for v in dc),1e-12)
        high=convert([math.sin(2*math.pi*16000*i/48000) for i in range(4800)])
        self.assertLess(sum(v*v for v in high)/len(high),.001)

    def test_native_stereo_downmix_runs_outside_callback(self):
        source=NativeMicAudioInput(backend=None,device_id="mic",clock_id="c",sample_rate_hz=10,
                                  channels=2,block_size=2,clock=lambda:10)
        source._callback(struct.pack("=4f",.25,.75,-.5,.5),2,
                         SimpleNamespace(inputBufferAdcTime=1,currentTime=1.2),False)
        stream=source.chunks();chunk=next(stream)
        self.assertEqual((.5,0),chunk.samples)
        self.assertEqual(2,chunk.sample_end)
        source.close();stream.close()

    def test_device_identity_survives_reordering_and_ambiguous_devices_are_withheld(self):
        class Module:
            devices=[dict(name="Mic A",hostapi=0,max_input_channels=2,default_samplerate=44100),
                     dict(name="Mic B",hostapi=0,max_input_channels=1,default_samplerate=48000)]
            def query_devices(self): return self.devices
            def query_hostapis(self): return [{"name":"Host"}]
            def check_input_settings(self,**kw):
                if (kw["channels"],kw["samplerate"]) != (2,44100): raise RuntimeError("format")
        module=Module();backend=SoundDeviceBackend(module)
        identity=backend.discover()[0].device_id
        module.devices.reverse()
        self.assertEqual(identity,backend.discover()[1].device_id)
        self.assertEqual({"channels":2,"sample_rate_hz":44100},backend.negotiate(device_id=identity,sample_rate_hz=48000))
        module.devices.append(dict(module.devices[1]))
        self.assertFalse(any(d.device_id==identity for d in backend.discover()))
