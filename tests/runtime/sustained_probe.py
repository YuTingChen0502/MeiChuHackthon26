"""Reproducible paced sustained-runtime probe; synthetic PCM is not ML evidence.

Run: python -m tests.runtime.sustained_probe --seconds 1200 --output PATH
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

from apps.api.service import RuntimeAPI
from core.audio.types import AudioChunk
from core.runtime.worker import AudioWorker
from tests.integration.test_api_service import wav_bytes


def memory_bytes():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
                ('peak','working','paged_peak','paged','nonpaged_peak','nonpaged','pagefile','peak_pagefile')]
        value=Counters();value.cb=ctypes.sizeof(value)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),value.cb):
            raise ctypes.WinError()
        return value.working
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def run(seconds,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    rate=48000;window=rate*4;hop=rate
    api=RuntimeAPI(storage_dir=output.parent/'state',window_size_samples=window,hop_size_samples=hop,
                   available_audio_devices={'synthetic-soak'},managed_audio=False)
    _,project=api.create_project({'name':'CP2 reproducible synthetic sustained probe'})
    _,song=api.create_song(dict(project_id=project['project_id'],name='constant PCM transport probe',
        instruments=[dict(instrument_id=x,family=x) for x in ('guitar','bass','drums')]))
    _,asset=api.upload_audio(wav_bytes([.05]*window,sample_rate=rate),filename='synthetic-constant.wav')
    _,job=api.start_reference_job(song['song_id'],{'asset_id':asset['asset_id']});api.run_reference_job(job['job_id'])
    _,snapshot=api.create_session(dict(song_id=song['song_id'],reference_id=job['reference_id'],
        source=dict(input_kind='live_microphone',input_asset_or_device_id='synthetic-soak'),
        capture_fingerprint=dict(device_id='synthetic-soak',profile_id='synthetic-v1',native_sample_rate_hz=rate,
            channels=1,gain_setting=None,enhancements_verified_disabled=None,geometry_id=None,provenance='unverified')))
    session=api.runtime_session(snapshot['session_id']);done=threading.Event();cancel=threading.Event()
    origin=time.monotonic();samples=(.05,)*4800;measurements=[]
    class Source:
        def chunks(self):
            for start in range(0,int(seconds*rate),len(samples)):
                end=origin+(start+len(samples))/rate
                if cancel.wait(max(0,end-time.monotonic())):
                    return
                yield AudioChunk('live_microphone','synthetic-soak',session.source['clock_id'],rate,start,end,samples)
        def close(self):
            cancel.set()
    def observe(w,q,age):
        session.observe_window(w,quality=q,max_age_s=age)
        if len(measurements)==0 or w.sample_end/rate-measurements[-1]['audio_seconds']>=10:
            measurements.append(dict(audio_seconds=w.sample_end/rate,rss_bytes=memory_bytes(),
                frames=len(session._frames),hashes=len(session._frame_audio_hashes),events=len(session._events)))
        api.get_session(session.session_id)
    manifest=dict(git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        git_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('core/audio','core/runtime','core/profiles','roles/pa','apps/api','tests/runtime') for p in Path(root).glob('*.py')},
        python=platform.python_version(),platform=platform.platform(),config=dict(duration_s=seconds,rate_hz=rate,
        window_samples=window,hop_samples=hop,queue_capacity=2,max_age_s=2,chunk_samples=len(samples),
        seed=0,pcm_amplitude=.05,noise='none',snr_db=None,model='continuous-fake-abstaining',
        labels='No instrument/gain labels. Constant mono PCM tests transport and retention only.',
        dataset='Deterministic generated constant PCM; no external assets or train/test split.'),status='running')
    output.write_text(json.dumps(manifest,indent=2))
    worker=AudioWorker(audio_input=Source(),pipeline=api.pipeline,session_id=session.session_id,
        on_window=observe,on_end=lambda reason:done.set())
    worker.start()
    try:
        deadline=time.monotonic()+seconds+20
        while not done.wait(10):
            progress=dict(elapsed_s=time.monotonic()-origin,metrics=worker.metrics(),
                          memory=list(measurements))
            (output.parent/'progress.json').write_text(json.dumps(progress,indent=2))
            if time.monotonic()>deadline:
                raise RuntimeError('sustained_probe_timeout')
    finally:
        worker.stop();api.close()
    manifest.update(status='completed',elapsed_s=time.monotonic()-origin,metrics=worker.metrics(),memory=measurements,
        final_buffers=dict(frames=len(session._frames),hashes=len(session._frame_audio_hashes),events=len(session._events)),
        claims='Local synthetic paced runtime only; not native microphone, PN54, calibration or ML accuracy evidence.')
    output.write_text(json.dumps(manifest,indent=2))
    print(json.dumps({key:manifest[key] for key in ('status','elapsed_s','metrics','final_buffers')},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=1200)
    parser.add_argument('--output',required=True);args=parser.parse_args();run(args.seconds,args.output)
