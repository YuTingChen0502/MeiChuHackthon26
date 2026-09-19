"""Actual native session lifecycle smoke; never writes microphone PCM."""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from apps.api.service import RuntimeAPI
from core.audio.native import SoundDeviceBackend
from tests.integration.test_api_service import wav_bytes, command
from tests.runtime.sustained_probe import memory_bytes


def run(device_id, seconds, output, analysis_rate=48000, window_seconds=1, hop_seconds=.5):
    result={"git_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            "git_dirty":bool(subprocess.check_output(["git","status","--porcelain"],text=True).strip()),
            "analysis_rate_hz":analysis_rate,"window_seconds":window_seconds,"hop_seconds":hop_seconds,
            "recording":"No microphone PCM saved", "device_id":device_id,
            "claim":"Local native transport/lifecycle only; Fake abstains; no model/calibration/PN54 claim."}
    with tempfile.TemporaryDirectory() as directory:
        api=RuntimeAPI(storage_dir=directory,window_size_samples=int(analysis_rate*window_seconds),hop_size_samples=int(analysis_rate*hop_seconds),
                       analysis_sample_rate_hz=analysis_rate,native_backend=SoundDeviceBackend())
        try:
            _,project=api.create_project({"name":"Native lifecycle probe"})
            _,song=api.create_song({"project_id":project["project_id"],"name":"Synthetic reference only",
                "instruments":[{"instrument_id":x,"family":x} for x in ("guitar","bass","drums")]})
            _,asset=api.upload_audio(wav_bytes([.1]*int(48000*(window_seconds+1)),sample_rate=48000),filename="generated-reference.wav")
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]});api.run_reference_job(job["job_id"])
            _,snapshot=api.create_session({"song_id":song["song_id"],"reference_id":job["reference_id"],
                "source":{"input_kind":"live_microphone","input_asset_or_device_id":device_id},
                "capture_fingerprint":{"device_id":device_id,"profile_id":"unverified-native-probe",
                    "native_sample_rate_hz":48000,"channels":1,"gain_setting":None,
                    "enhancements_verified_disabled":None,"geometry_id":None,"provenance":"unverified"}})
            sid=snapshot["session_id"];runs=[];started=time.monotonic()
            for iteration in range(2):
                if iteration:
                    api.post_action(sid,command(api.get_session(sid)[1],"resume","resume"))
                worker=api.workers[sid]
                time.sleep(seconds)
                current=api.get_session(sid)[1]
                if current["song"]["workflow_state"] != "REHEARSAL" or worker.processed_windows < 2:
                    raise RuntimeError(f"native session did not stream: {current['suspension_reasons']}")
                runs.append({"metrics":worker.metrics(),"analysis_run_id":current["latest_frame"]["analysis_run_id"],
                    "callback_max_queue":worker.audio_input.max_queue_depth,
                    "callback_drops":worker.audio_input.dropped_packets,"adc_residual_s":worker.audio_input.max_adc_residual_s,
                    "rss_bytes":memory_bytes(),"all_abstained":all(x["confidence"]["abstained"] for x in current["latest_frame"]["instruments"])})
                api.post_action(sid,command(api.get_session(sid)[1],f"pause-{iteration}","pause"))
                assert worker.audio_input._stream is None
            assert runs[0]["analysis_run_id"] != runs[1]["analysis_run_id"]
            api.post_action(sid,command(api.get_session(sid)[1],"stop","stop"))
            result.update(duration_s=time.monotonic()-started,runs=runs,
                          final_workflow=api.get_session(sid)[1]["song"]["workflow_state"],
                          capture=api.runtime_session(sid).capture_fingerprint,status="passed")
        finally:
            api.close()
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id",required=True);parser.add_argument("--seconds-per-run",type=float,default=6)
    parser.add_argument("--output",required=True)
    parser.add_argument("--analysis-rate",type=int,default=48000)
    parser.add_argument("--window-seconds",type=float,default=1)
    parser.add_argument("--hop-seconds",type=float,default=.5)
    args=parser.parse_args()
    run(args.device_id,args.seconds_per_run,args.output,args.analysis_rate,args.window_seconds,args.hop_seconds)
