"""Immutable reference migration via retained byte identity, no implicit retarget."""
import base64
import copy
import io
import tempfile
import time
import unittest
import wave
from apps.api.service import RuntimeAPI,APIError
import test_api_service as fixture
import test_transport as transport
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer


class ReferenceReprepareTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=10,available_audio_devices={"mic-1"})
        self.song,self.asset,self.job,self.snapshot=fixture.RuntimeAPIServiceTests.create_rehearsal_session(self.api)
    def tearDown(self):self.api.close();self.temp.cleanup()
    def reprepare(self):return self.api.start_reference_job(self.song["song_id"],dict(reference_id=self.job["reference_id"]))
    def test_new_reference_uses_verified_original_bytes_without_mutating_old_session(self):
        old=copy.deepcopy(self.api.references[self.job["reference_id"]]);seen=[]
        class Analyzer(ContinuousFakeInstrumentAnalyzer):
            def prepare_reference(self,windows,instrument_config):
                def checked():
                    for window in windows:seen.extend(window.samples);yield window
                return super().prepare_reference(checked(),instrument_config)
        self.api.analyzer_factory=Analyzer
        self.api.assets[self.asset["asset_id"]]["samples"]=[.9]*20 # bytes, not stale decoded metadata, own reference analysis
        status,job=self.reprepare();self.assertEqual(202,status)
        self.assertEqual(self.asset["asset_id"],job["asset_id"])
        self.assertEqual("completed",self.api.run_reference_job(job["job_id"])[1]["status"])
        self.assertTrue(seen);self.assertTrue(all(abs(v-.1)<.001 for v in seen))
        self.assertEqual(old,self.api.references[self.job["reference_id"]])
        self.assertEqual(old,self.api.get_session(self.snapshot["session_id"])[1]["active_reference"])
        self.assertEqual(1,len(self.api.assets));self.assertNotEqual(self.job["reference_id"],job["reference_id"])
    def test_legacy_mono_exact_reconstruction_and_restart_preserve_upload_identity(self):
        self.api.assets[self.asset["asset_id"]].pop("encoded_audio")
        self.api._save_state();self.api.close()
        self.api=RuntimeAPI(storage_dir=self.temp.name,window_size_samples=10,available_audio_devices={"mic-1"})
        _,job=self.reprepare();self.assertEqual("completed",self.api.run_reference_job(job["job_id"])[1]["status"])
        new=self.api.references[job["reference_id"]]
        self.assertEqual(self.asset["content_hash"],new["source_asset_hash"])
        self.assertIn("encoded_audio",self.api.assets[self.asset["asset_id"]])
    def test_missing_tampered_and_unreconstructable_audio_fail_without_job_or_target_change(self):
        asset=self.api.assets[self.asset["asset_id"]];original=copy.deepcopy(asset)
        for change in ("missing", "tampered", "lossy"):
            self.api.assets[self.asset["asset_id"]]=copy.deepcopy(original)
            if change=="missing":self.api.assets.pop(self.asset["asset_id"])
            elif change=="tampered":self.api.assets[self.asset["asset_id"]]["encoded_audio"]=base64.b64encode(b"wrong bytes").decode()
            else:
                self.api.assets[self.asset["asset_id"]].pop("encoded_audio")
                self.api.assets[self.asset["asset_id"]]["samples"]=[.2]*20
            with self.subTest(change=change),self.assertRaises(APIError) as error:self.reprepare()
            self.assertEqual("reference_audio_unavailable",error.exception.code)
            self.assertEqual(1,len(self.api.jobs))
            self.assertEqual(self.job["reference_id"],self.api.songs[self.song["song_id"]]["reference_id"])
    def test_retained_stereo_works_but_discarded_stereo_and_custom_riff_cannot_be_invented(self):
        output=io.BytesIO()
        with wave.open(output,"wb") as writer:
            writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(10)
            writer.writeframes((b"\x01\x00\x02\x00")*20)
        for content in (output.getvalue(),self.custom_riff()):
            _,asset=self.api.upload_audio(content,filename="original.wav")
            _,job=self.api.start_reference_job(self.song["song_id"],dict(asset_id=asset["asset_id"]))
            self.assertEqual("completed",self.api.run_reference_job(job["job_id"])[1]["status"])
            self.api.assets[asset["asset_id"]].pop("encoded_audio")
            with self.assertRaises(APIError) as error:
                self.api.start_reference_job(self.song["song_id"],dict(reference_id=job["reference_id"]))
            self.assertEqual("reference_audio_unavailable",error.exception.code)
    @staticmethod
    def custom_riff():
        content=bytearray(fixture.wav_bytes([.1]*20));content.extend(b"JUNK"+(4).to_bytes(4,"little")+b"test")
        content[4:8]=(len(content)-8).to_bytes(4,"little")
        return bytes(content)
    def test_wrong_song_unknown_reference_and_mutually_exclusive_request(self):
        _,song=self.api.create_song(dict(project_id=self.song["project_id"],name="Other",instruments=[dict(instrument_id="bass",family="bass")]))
        with self.assertRaises(APIError) as error:
            self.api.start_reference_job(song["song_id"],dict(reference_id=self.job["reference_id"]))
        self.assertEqual("reference_song_mismatch",error.exception.code)
        with self.assertRaises(APIError) as error:self.api.start_reference_job(self.song["song_id"],dict(reference_id="missing"))
        self.assertEqual(404,error.exception.status)
        with self.assertRaises(APIError) as error:
            self.api.start_reference_job(self.song["song_id"],dict(reference_id=self.job["reference_id"],asset_id=self.asset["asset_id"]))
        self.assertEqual(422,error.exception.status)


class ReprepareTransportTests(unittest.TestCase):
    def test_existing_http_route_reuses_asset_and_requires_explicit_new_session(self):
        test=transport.TransportTests();test.setUp();self.addCleanup(test.tearDown)
        old=test.setup_session();route=f"/v1/songs/{old['song']['song_id']}/reference"
        status,job=test.request("POST",route,json_body=dict(reference_id=old["active_reference"]["reference_id"]))
        self.assertEqual(202,status)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            _,job=test.request("GET",f"/v1/jobs/{job['job_id']}")
            if job["status"]=="completed":break
            time.sleep(.02)
        self.assertEqual("completed",job["status"])
        self.assertEqual(1,len(test.runtime.sessions))
        _,retained=test.request("GET",f"/v1/sessions/{old['session_id']}")
        self.assertEqual(old["active_reference"],retained["active_reference"])
        status,new=test.request("POST","/v1/sessions",json_body=dict(song_id=old["song"]["song_id"],reference_id=job["reference_id"],
            workflow_policy="live_reference_v1",source=dict(input_kind="uploaded_file",input_asset_or_device_id=job["asset_id"])))
        self.assertEqual(201,status);self.assertNotEqual(old["session_id"],new["session_id"])
        self.assertEqual(job["reference_id"],new["active_reference"]["reference_id"])
        self.assertEqual(1,len(test.runtime.assets))
