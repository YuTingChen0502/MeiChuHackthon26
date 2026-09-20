"""Physical live-reference capture/switch acceptance; retains no microphone PCM."""
import argparse
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from apps.api.service import RuntimeAPI
from core.audio.native import SoundDeviceBackend
from tests.integration.test_api_service import wav_bytes,command
from tests.runtime.sustained_probe import memory_bytes


def run(seconds,output):
    source_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    if subprocess.check_output(["git","status","--porcelain"],text=True).strip():raise RuntimeError("clean source required")
    backend=SoundDeviceBackend();raw=backend.discover()
    default=next(d for d in raw if d.is_default)
    with tempfile.TemporaryDirectory() as directory:
        api=RuntimeAPI(storage_dir=directory,window_size_samples=192000,hop_size_samples=48000,
            analysis_sample_rate_hz=48000,native_backend=backend,managed_audio=True)
        workers=[];operations=[];samples=[];started=time.monotonic()
        def remember():
            for worker in api.workers.values():
                if worker not in workers:workers.append(worker)
        def wait(sid,predicate,timeout=30):
            until=time.monotonic()+timeout
            while time.monotonic()<until:
                remember();snapshot=api.get_session(sid)[1]
                if predicate(snapshot):return snapshot
                time.sleep(.1)
            raise RuntimeError("acceptance timeout:"+json.dumps(snapshot["capture"]))
        def execute(sid,action,key,payload=None):
            snapshot=api.get_session(sid)[1]
            body=command(snapshot,key,action,payload)
            status,result=api.post_action(sid,body)
            if status!=200:raise RuntimeError(json.dumps(result))
            operations.append(dict(action=action,key=key,accepted_capture=result["snapshot"]["capture"],elapsed_s=time.monotonic()-started))
            return result["snapshot"]
        try:
            inventory=api.audio_devices()[1]
            _,project=api.create_project({"name":"Physical native acceptance"})
            _,song=api.create_song({"project_id":project["project_id"],"name":"Generated reference only",
                "instruments":[dict(instrument_id=x,family=x) for x in ("guitar","bass","drums")]})
            _,asset=api.upload_audio(wav_bytes([.1]*240000,sample_rate=48000),filename="generated.wav")
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]});api.run_reference_job(job["job_id"])
            request=dict(song_id=song["song_id"],reference_id=job["reference_id"],workflow_policy="live_reference_v1")
            _,snapshot=api.create_session(request);sid=snapshot["session_id"]
            snapshot=wait(sid,lambda s:s["capture"]["state"]=="active")
            initial_reference=snapshot["active_reference"]
            group=next(m["microphone_id"] for m in inventory["microphones"] if m["selection_kind"]!="system_default"
                and any(d.device_id==default.device_id for d in api.live_audio.inventory().resolve(m["microphone_id"])))
            for index,identity in enumerate((default.device_id,group,"unavailable-acceptance-input")):
                time.sleep(4)
                snapshot=api.get_session(sid)[1]
                execute(sid,"switch_microphone",f"physical-switch-{index}",dict(microphone_id=identity,
                    expected_source_generation=snapshot["capture"]["source_generation"]))
                snapshot=wait(sid,lambda s:s["capture"]["switch_result"] in ("applied","rolled_back","failed"))
                operations[-1]["terminal_capture"]=snapshot["capture"]
                snapshot=wait(sid,lambda s:s["capture"]["state"]=="active")
                assert snapshot["active_reference"]==initial_reference
            execute(sid,"pause","physical-pause")
            snapshot=api.get_session(sid)[1]
            execute(sid,"switch_microphone","paused-selection",dict(microphone_id=default.device_id,
                expected_source_generation=snapshot["capture"]["source_generation"]))
            wait(sid,lambda s:s["capture"]["state"]=="paused" and s["capture"]["switch_result"]=="applied")
            execute(sid,"resume","physical-resume")
            wait(sid,lambda s:s["capture"]["state"]=="active")
            next_measurement=0
            while sum(w.audio_input._next_sample/w.audio_input.sample_rate_hz for w in workers)<seconds:
                remember();snapshot=api.get_session(sid)[1]
                if snapshot["capture"]["state"]=="unavailable":raise RuntimeError(str(snapshot["capture"]))
                elapsed=time.monotonic()-started
                if elapsed>=next_measurement:
                    session=api.runtime_session(sid)
                    samples.append(dict(elapsed_s=elapsed,rss_bytes=memory_bytes(),frames=len(session._frames),
                        hashes=len(session._frame_audio_hashes),events=len(session._events),capture=snapshot["capture"]))
                    next_measurement=elapsed+10
                if elapsed>seconds+180:raise RuntimeError("bounded acceptance deadline exceeded")
                time.sleep(.25)
            execute(sid,"stop","physical-stop")
            assert api.get_session(sid)[1]["capture"]["state"]=="stopped"
            _,reopened=api.create_session(request)
            reopened=wait(reopened["session_id"],lambda s:s["capture"]["state"]=="active")
            execute(reopened["session_id"],"stop","reopened-stop")
            report=dict(status="passed",git_commit=source_sha,platform=platform.platform(),python=platform.python_version(),
                sounddevice=backend.module.__version__,duration_s=time.monotonic()-started,
                captured_seconds=sum(w.audio_input._next_sample/w.audio_input.sample_rate_hz for w in workers),
                inventory=inventory,operations=operations,memory=samples,
                runs=[dict(source_id=w.audio_input.device_id,clock_id=w.audio_input.clock_id,
                    sample_rate_hz=w.audio_input.sample_rate_hz,channels=w.audio_input.channels,clock_mode=w.audio_input.clock_mode,
                    adc_packets=w.audio_input.adc_packets,fallback_packets=w.audio_input.fallback_packets,
                    callback_drops=w.audio_input.dropped_packets,callback_discontinuities=w.audio_input.discontinuities,
                    callback_max_queue=w.audio_input.max_queue_depth,worker=w.metrics()) for w in workers],
                recording="No microphone PCM saved",model="ContinuousFakeInstrumentAnalyzer; uncalibrated acoustic claim absent",
                hardware_limits="Windows local only. Host aliases of one physical Realtek array are not two microphones. Linux/PN54 and second physical mic BLOCKED_EXTERNAL_HARDWARE.")
        finally:api.close()
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","git_commit","duration_s","captured_seconds","hardware_limits")}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds",type=float,default=600)
    parser.add_argument("--output",required=True)
    args=parser.parse_args();run(args.seconds,args.output)
