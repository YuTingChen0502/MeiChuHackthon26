"""Local native capture probe. Retains exact PCM and a quantized convenience WAV.

Run only when microphone recording is authorized. Output stays outside the repository.
"""
import argparse
import hashlib
import json
import platform
import struct
import subprocess
import wave
from dataclasses import asdict
from pathlib import Path

from core.audio import FileAudioInput, SharedAudioPipeline
from core.audio.native import SoundDeviceBackend, NativeMicAudioInput


def run(device_id, seconds, output):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    backend=SoundDeviceBackend();devices=backend.discover()
    device=next(item for item in devices if item.device_id==device_id)
    source=NativeMicAudioInput(backend=backend,device_id=device_id,clock_id='native-validation',sample_rate_hz=48000)
    manifest=dict(git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        git_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_hash=hashlib.sha256(Path('core/audio/native.py').read_bytes()).hexdigest(),
        platform=platform.platform(),python=platform.python_version(),sounddevice=backend.module.__version__,
        inventory=[asdict(d) for d in devices],device=asdict(device),rate_hz=48000,channels=1,dtype='float32',
        block_samples=1024,queue_capacity=8,clock_tolerance_s=source.clock_tolerance_s,
        seed=None,noise_snr=None,labels='None; native transport/parity smoke only. Not ML or PN54 evidence.',
        provenance='unverified',gain_setting=None,enhancements_verified_disabled=None,geometry_id=None)
    chunks=[]
    try:
        source.start()
        count=0
        for chunk in source.chunks():
            chunks.append(chunk);count+=len(chunk.samples)
            if count>=seconds*48000:break
        samples=tuple(value for chunk in chunks for value in chunk.samples)
        raw=struct.pack(f'<{len(samples)}f',*samples);(folder/'capture.float32le').write_bytes(raw)
        with wave.open(str(folder/'capture.wav'),'wb') as writer:
            writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(48000)
            writer.writeframes(b''.join(struct.pack('<h',max(-32768,min(32767,round(v*32768)))) for v in samples))
        manifest.update(status='captured',sample_count=len(samples),dropped_packets=source.dropped_packets,
            discontinuities=source.discontinuities,max_queue_depth=source.max_queue_depth,
            max_adc_residual_s=source.max_adc_residual_s,raw_float_sha256=hashlib.sha256(raw).hexdigest(),
            wav_sha256=hashlib.sha256((folder/'capture.wav').read_bytes()).hexdigest(),
            clipped_fraction=sum(abs(v)>=1 for v in samples)/len(samples),
            sample_spans=[[c.sample_start,c.sample_end,c.capture_end_monotonic_s] for c in chunks],
            wav_note='PCM16 copy is quantized; float32le preserves exact source PCM.')
        pipeline=SharedAudioPipeline(window_size_samples=192000,hop_size_samples=48000)
        captured=list(pipeline.windows_from_chunks(chunks,session_id='native',analysis_run_id='native-run'))
        origin=chunks[0].capture_end_monotonic_s-len(chunks[0].samples)/48000
        replay=FileAudioInput(input_asset_or_device_id='captured-float',clock_id='native-validation',sample_rate_hz=48000,
                              samples=samples,origin_monotonic_s=origin,chunk_size_samples=777)
        replayed=list(pipeline.iter_windows(replay,session_id='replay',analysis_run_id='replay-run'))
        manifest['pcm_replay_parity']=bool(captured) and len(captured)==len(replayed) and all(
            (a.samples,a.sample_start,a.sample_end,a.capture_end_monotonic_s)==
            (b.samples,b.sample_start,b.sample_end,b.capture_end_monotonic_s) for a,b in zip(captured,replayed))
    except Exception as exc:
        manifest.update(status='failed',error=str(exc))
    finally:
        source.close()
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('inventory','sample_spans')},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--device-id',required=True)
    parser.add_argument('--seconds',type=float,default=6);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.device_id,args.seconds,args.output)
