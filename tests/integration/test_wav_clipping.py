"""Raw stereo clipping must survive file/native downmix equally."""
import io
import struct
import unittest
import wave
from types import SimpleNamespace
from apps.api.service import _decode_pcm16_wav
from core.audio import FileAudioInput, SharedAudioPipeline
from core.audio.native import NativeMicAudioInput


class WavClippingTests(unittest.TestCase):
    def test_stereo_file_and_native_keep_clipping_hidden_by_downmix(self):
        raw_pcm=(32767,-16384,32767,-16384)
        stream=io.BytesIO()
        with wave.open(stream,"wb") as writer:
            writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(48000)
            writer.writeframes(struct.pack("<4h",*raw_pcm))
        rate,samples,channels,blocks=_decode_pcm16_wav(stream.getvalue())
        self.assertLess(max(samples),.3)
        file=FileAudioInput(input_asset_or_device_id="file",clock_id="f",sample_rate_hz=rate,
                           samples=samples,clipping_blocks=blocks,origin_monotonic_s=10)
        mic=NativeMicAudioInput(backend=None,device_id="mic",clock_id="m",sample_rate_hz=rate,
                                channels=2,block_size=2,clock=lambda:10)
        mic._callback(struct.pack("=4f",*(value/32768 for value in raw_pcm)),2,
                      SimpleNamespace(inputBufferAdcTime=1,currentTime=1),False)
        chunks=mic.chunks()
        try:
            native=next(chunks);uploaded=next(file.chunks())
            self.assertEqual(native.samples,uploaded.samples)
            self.assertEqual(.5,native.input_clipped_fraction)
            self.assertEqual(native.input_clipped_fraction,uploaded.input_clipped_fraction)
            planner=SharedAudioPipeline(window_size_samples=2)
            window=next(planner.iter_windows(file,session_id="s",analysis_run_id="r"))
            self.assertEqual(.5,window.input_clipped_fraction)
        finally:mic.close();chunks.close()
