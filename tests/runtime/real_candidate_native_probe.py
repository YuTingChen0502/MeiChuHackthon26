"""Actual Windows native capture through the injected frozen P1 candidate.

Generated reference is transport material, not acoustic ground truth. No mic PCM is saved.
The first 32 seconds have reference coverage; later PCM must still run separation.
Missing comparison coverage remains invalid/null, never wrapped to the reference.
"""
import argparse
from collections import deque
import copy
import json
import math
import os
import platform
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request

from analyzers.separation.p1_candidate import make_p1_candidate_loader
from apps.api.config import runtime_options
from apps.api.service import RuntimeAPI
from apps.api.transport import create_app
from core.audio.native import SoundDeviceBackend
from tests.integration.test_api_service import wav_bytes,command
from tests.runtime.sustained_probe import memory_bytes


def run(storage,output,segment_seconds=20):
    root=Path(storage);root.mkdir(parents=True,exist_ok=True)
    sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    if subprocess.check_output(["git","status","--porcelain"],text=True).strip():raise RuntimeError("clean source required")
    if not 12<=segment_seconds<=900:raise ValueError("segment must be 12..900 seconds")
    calls=deque(maxlen=256);workers=[];snapshots=[];operations=[];segments=[];models=[]
    options=runtime_options(environment={"PA_MODEL_BUNDLE":"models/candidates/nano4-p1-adapted-mvp-v1"},
        loader=make_p1_candidate_loader(cache_dir=root/"context-cache",candidate_mode=True,device="cpu"))
    factory=options["analyzer_factory"]
    def instrumented():
        analyzer=factory();index=len(models);models.append(analyzer);original=analyzer.analyze
        def analyze(window,context):
            before=analyzer.execution_diagnostics();start=time.monotonic()
            evidence=original(window,context)
            after=analyzer.execution_diagnostics()
            calls.append(dict(model_instance=index,observation=window.identity(),started_monotonic_s=start,
                completed_monotonic_s=time.monotonic(),before=before,after=after,
                measurements=copy.deepcopy(evidence["measurements"])))
            return evidence
        analyzer.analyze=analyze
        return analyzer
    options["analyzer_factory"]=instrumented
    backend=SoundDeviceBackend()
    api=RuntimeAPI(storage_dir=root,window_size_samples=176400,hop_size_samples=44100,
        analysis_sample_rate_hz=44100,native_backend=backend,managed_audio=True,
        analysis_timing_profile_id="candidate_delayed_v1",**options)
    server=None;server_thread=None;began=time.monotonic()
    def remember():
        for worker in api.workers.values():
            if worker not in workers:workers.append(worker)
    def wait(sid,predicate,timeout=30):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            remember();snapshot=api.get_session(sid)[1]
            if predicate(snapshot):return snapshot
            time.sleep(.05)
        raise RuntimeError("native wait timeout:"+json.dumps(snapshot["capture"]))
    def execute(sid,action,key,payload=None):
        for attempt in range(3):
            snapshot=api.get_session(sid)[1]
            if action=="switch_microphone":payload["expected_source_generation"]=snapshot["capture"]["source_generation"]
            status,result=api.post_action(sid,command(snapshot,key+str(attempt),action,payload))
            if status==200:
                operations.append(dict(action=action,accepted=result["snapshot"]["capture"],wall_s=time.monotonic()-began))
                return result
            if result.get("error",{}).get("code")!="state_version_conflict":raise RuntimeError(str(result))
        raise RuntimeError("command did not stabilize")
    def measure(sid,label):
        snapshot=wait(sid,lambda s:s["capture"]["state"] in ("listening","active"))
        assert snapshot["analysis_timing"]["profile_id"]=="candidate_delayed_v1"
        clock=snapshot["source"]["clock_id"];start=time.monotonic();next_sample=0
        while True:
            remember();snapshot=api.get_session(sid)[1];elapsed=time.monotonic()-start
            matching=[c for c in calls if c["observation"]["clock_id"]==clock and c["after"]["model_calls_completed"]>c["before"]["model_calls_completed"]]
            if elapsed>=next_sample:
                session=api.runtime_session(sid);worker=api.workers[sid]
                snapshots.append(dict(label=label,elapsed_s=elapsed,rss_bytes=memory_bytes(),capture=snapshot["capture"],
                    perception=snapshot["perception"],latest_frame=snapshot["latest_frame"],worker=worker.metrics(),
                    frames=len(session._frames),hashes=len(session._frame_audio_hashes),events=len(session._events),
                    diagnostics=session.analyzer.analyzer.execution_diagnostics()))
                next_sample=elapsed+2
            if snapshot["capture"]["state"]=="unavailable":raise RuntimeError(str(snapshot["capture"]))
            if elapsed>=segment_seconds and matching:
                if time.monotonic()-matching[-1]["completed_monotonic_s"]>30:
                    raise RuntimeError("current-source real model execution stopped")
                break
            if elapsed>max(30,segment_seconds+30):raise RuntimeError("no completed current-generation model call")
            time.sleep(.1)
        segments.append(dict(label=label,clock_id=clock,duration_s=elapsed,completed_native_model_calls=len(matching)))
        print(json.dumps({"phase":"segment_complete",**segments[-1]}),flush=True)
    try:
        inventory=api.audio_devices()[1];raw=backend.discover();default=next(d for d in raw if d.is_default)
        group=next(m["microphone_id"] for m in inventory["microphones"] if m["selection_kind"]!="system_default"
            and any(d.device_id==default.device_id for d in api.live_audio.inventory().resolve(m["microphone_id"])))
        current_model=api.analyzer_capabilities()["model"]
        existing=next((j for j in api.jobs.values() if j["status"]=="completed" and
            api.songs[j["song_id"]]["name"]=="Generated reference - no acoustic labels" and
            api.reference_models.get(j["reference_id"])==current_model),None)
        if existing:
            job=existing;song=api.songs[job["song_id"]]
            print(json.dumps({"phase":"reuse_exact_compatible_reference","reference_id":job["reference_id"],"git_commit":sha}),flush=True)
        else:
            _,project=api.create_project({"name":"Actual native P1 engineering acceptance"})
            _,song=api.create_song({"project_id":project["project_id"],"name":"Generated reference - no acoustic labels",
                "instruments":[dict(instrument_id=x,family=x) for x in ("bass","guitar","drums","vocals","keys")]})
            samples=[.15*math.sin(2*math.pi*110*i/44100) for i in range(32*44100)]
            _,asset=api.upload_audio(wav_bytes(samples,sample_rate=44100),filename="generated-reference-32s.wav")
            del samples
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
            print(json.dumps({"phase":"reference_preparation","git_commit":sha,"seconds":32}),flush=True)
            result=api.run_reference_job(job["job_id"])[1]
            if result["status"]!="completed":raise RuntimeError(str(result))
        import uvicorn
        from websockets.sync.client import connect
        with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        os.environ["PA_ALLOWED_ORIGINS"]=f"http://127.0.0.1:{port}"
        server=uvicorn.Server(uvicorn.Config(create_app(api),host="127.0.0.1",port=port,
            log_level="error",loop="asyncio",http="h11",ws="websockets-sansio"))
        server_thread=threading.Thread(target=server.run,daemon=True);server_thread.start()
        while not server.started:time.sleep(.05)
        request=dict(song_id=song["song_id"],reference_id=job["reference_id"],workflow_policy="live_reference_v1")
        print(json.dumps({"phase":"native_capture_start","http_port":port}),flush=True)
        _,snapshot=api.create_session(request);sid=snapshot["session_id"]
        measure(sid,"initial-system-default")
        execute(sid,"pause","pause")
        paused=wait(sid,lambda s:s["capture"]["state"]=="paused")
        assert not paused["capture"]["frame_fresh"]
        execute(sid,"resume","resume")
        measure(sid,"pause-resume")
        transport=[]
        route=f"/v1/sessions/{sid}"
        for _ in range(2):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}"+route,timeout=5) as response:
                wire=json.load(response);assert wire["workflow_policy"]=="live_reference_v1"
            with connect(f"ws://127.0.0.1:{port}"+route+"/events?after_sequence=0",origin=f"http://127.0.0.1:{port}",close_timeout=1) as ws:
                event=json.loads(ws.recv(timeout=5));transport.append(dict(http=200,event_sequence=event["event_sequence"]))
        for i,identity in enumerate((default.device_id,group,"unavailable-physical-probe")):
            execute(sid,"switch_microphone",f"switch-{i}",dict(microphone_id=identity))
            terminal=wait(sid,lambda s:s["capture"]["switch_result"] in ("applied","rolled_back","failed"))
            operations[-1]["terminal"]=terminal["capture"]
            assert terminal["capture"]["switch_result"]==("rolled_back" if i==2 else "applied")
            assert terminal["active_reference"]["reference_id"]==job["reference_id"]
            measure(sid,f"switch-{i}")
        execute(sid,"stop","stop")
        _,reopened=api.create_session(request);sid2=reopened["session_id"]
        measure(sid2,"new-session-reopen");execute(sid2,"stop","reopen-stop")
        for task in api.live_audio.closers.values():task.join(30)
        completed_calls=[call for call in calls if call["after"]["model_calls_completed"]>call["before"]["model_calls_completed"]]
        processing=sorted(call["completed_monotonic_s"]-call["started_monotonic_s"] for call in completed_calls)
        result_ages=sorted(call["completed_monotonic_s"]-call["observation"]["capture_end_monotonic_s"] for call in completed_calls)
        percentile=lambda values,fraction:values[min(len(values)-1,int((len(values)-1)*fraction))] if values else None
        fresh_frames={sample["latest_frame"]["frame_id"] for sample in snapshots
            if sample["capture"]["frame_fresh"] and sample["latest_frame"] is not None}
        report=dict(status="passed_execution_not_accuracy",git_commit=sha,platform=platform.platform(),python=platform.python_version(),
            sounddevice=backend.module.__version__,elapsed_total_s=time.monotonic()-began,
            measured_native_s=sum(s["duration_s"] for s in segments),segments=segments,inventory=inventory,
            operations=operations,transport=transport,calls=list(calls),snapshots=snapshots,
            timing=dict(profile_id="candidate_delayed_v1",completed_model_calls=len(completed_calls),
                fresh_frame_count=len(fresh_frames),processing_p50_s=percentile(processing,.5),
                processing_p95_s=percentile(processing,.95),result_age_p50_s=percentile(result_ages,.5),
                result_age_p95_s=percentile(result_ages,.95),
                non_null_hints=sum(p.get("adjustment_hint") is not None for sample in snapshots for p in sample["perception"])),
            model=api.runtime_session(sid2)._model_identity,
            runs=[dict(device_id=w.audio_input.device_id,clock_id=w.audio_input.clock_id,rate=w.audio_input.sample_rate_hz,
                captured_seconds=w.audio_input._next_sample/w.audio_input.sample_rate_hz,
                callback_peak=w.audio_input.max_queue_depth,callback_drops=w.audio_input.dropped_packets,
                callback_discontinuities=w.audio_input.discontinuities,worker=w.metrics()) for w in workers],
            storage=str(root.resolve()),recording="No microphone PCM/stems saved. Generated reference only is persisted.",
            limits="Windows single Realtek array; aliases are not distinct physical microphones. Linux/PN54 and second microphone BLOCKED_EXTERNAL_HARDWARE. Candidate uncalibrated, bass-only matched digital support; no room accuracy or calibrated action claim.")
        Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps({k:report[k] for k in ("status","git_commit","elapsed_total_s","measured_native_s","limits")}),flush=True)
    finally:
        if not Path(output).exists():
            Path(output).write_text(json.dumps(dict(status="incomplete_failed_attempt",git_commit=sha,
                segments=segments,operations=operations,calls=list(calls),snapshots=snapshots),indent=2),encoding="utf-8")
        if server:server.should_exit=True
        if server_thread:server_thread.join(5)
        api.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage",required=True);parser.add_argument("--output",required=True)
    parser.add_argument("--segment-seconds",type=float,default=20)
    args=parser.parse_args();run(args.storage,args.output,args.segment_seconds)
