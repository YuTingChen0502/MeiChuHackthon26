"""Actual candidate injection through Runtime; generated tone is transport data only."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
import time

from analyzers.separation.p1_candidate import make_p1_candidate_loader
from apps.api.config import runtime_options
from apps.api.service import RuntimeAPI
from core.audio import FileAudioInput, MicAudioInput
from tests.integration.test_api_service import wav_bytes


def run(candidate, output):
    started=time.monotonic()
    revision=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    dirty=bool(subprocess.check_output(["git","status","--porcelain"],text=True).strip())
    samples=[.15*math.sin(2*math.pi*110*i/44100) for i in range(176400)]
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        options=runtime_options(environment={"PA_MODEL_BUNDLE":str(candidate)},
            loader=make_p1_candidate_loader(cache_dir=root/"context-cache",candidate_mode=True,device="cpu"))
        api=RuntimeAPI(storage_dir=root/"state",window_size_samples=176400,hop_size_samples=44100,
            analysis_sample_rate_hz=44100,managed_audio=False,available_audio_devices={"synthetic-mic"},**options)
        try:
            health=api.health()[1]
            assert health["example_only"] is False
            _,project=api.create_project({"name":"Candidate Runtime integration only"})
            _,song=api.create_song({"project_id":project["project_id"],"name":"Generated 110 Hz tone",
                "instruments":[{"instrument_id":x,"family":x} for x in ("bass","guitar","drums","vocals","keys")]})
            _,asset=api.upload_audio(wav_bytes(samples,sample_rate=44100),filename="generated-tone.wav")
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
            reference=api.run_reference_job(job["job_id"])[1]
            assert reference["status"]=="completed", reference
            frames={}
            for kind,adapter,identity in (("uploaded_file",FileAudioInput,asset["asset_id"]),
                                         ("live_microphone",MicAudioInput,"synthetic-mic")):
                _,snapshot=api.create_session({"song_id":song["song_id"],"reference_id":job["reference_id"],
                    "source":{"input_kind":kind,"input_asset_or_device_id":identity},
                    "capture_fingerprint":{"device_id":identity,"profile_id":"unverified-probe",
                        "native_sample_rate_hz":44100,"channels":1,"gain_setting":None,
                        "enhancements_verified_disabled":None,"geometry_id":None,"provenance":"unverified"}})
                session=api.runtime_session(snapshot["session_id"])
                audio=adapter(input_asset_or_device_id=identity,clock_id=session.source["clock_id"],
                    sample_rate_hz=44100,samples=api.assets[asset["asset_id"]]["samples"],origin_monotonic_s=time.monotonic())
                window=next(api.pipeline.iter_windows(audio,session_id=session.session_id,analysis_run_id="candidate-probe"))
                frame=session.observe_window(window)
                assert frame["example_only"] is False
                for row in frame["instruments"]:
                    assert row["status"] != "normal"
                    assert row["balance_deviation_db"] is None
                    assert row["confidence"]["probability"] is None
                    assert row["confidence"]["abstained"]
                assert session.baseline is None
                frames[kind]=frame
                # Close the session before loading another heavyweight candidate.
                session.analyzer.close()
            report={"status":"passed","git_commit":revision,"git_dirty":dirty,
                "duration_s":time.monotonic()-started,"health":health,"reference_job":reference,"frames":frames,
                "material":"Deterministic generated 110 Hz sine, amplitude 0.15, 44100 Hz, four seconds, PCM16",
                "claim":"Actual CPU candidate injection/reference/cache/downstream gating only; no instrument labels, accuracy, native candidate inference, or calibration claim."}
        finally:
            api.close()
    Path(output).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","git_commit","git_dirty","duration_s","claim")}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.candidate,args.output)
