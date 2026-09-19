"""Reference preparation progress and durable adapter-failure regression."""
import itertools
import tempfile
import threading
import unittest
from apps.api.service import RuntimeAPI
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer
from test_api_service import wav_bytes


class ReferenceJobProgressTests(unittest.TestCase):
    def setup_job(self, api):
        _,project=api.create_project({"name":"Reference progress"})
        _,song=api.create_song({"project_id":project["project_id"],"name":"Native setup reference",
            "instruments":[{"instrument_id":x,"family":x} for x in ("bass","guitar","drums")]})
        _,asset=api.upload_audio(wav_bytes([.1]*4096,sample_rate=1024),filename="generated.wav")
        _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
        return asset,job

    def test_pollable_progress_advances_before_analyzer_finishes(self):
        entered=threading.Event();release=threading.Event()
        class PausedFake(ContinuousFakeInstrumentAnalyzer):
            def prepare_reference(self, windows, config):
                iterator=iter(windows);first=next(iterator);entered.set()
                if not release.wait(5):
                    raise RuntimeError("test preparation timed out")
                return super().prepare_reference(itertools.chain([first],iterator),config)
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=1024,hop_size_samples=512,
                analysis_sample_rate_hz=1024,analyzer_factory=PausedFake)
            _,job=self.setup_job(api)
            worker=threading.Thread(target=api.run_reference_job,args=(job["job_id"],))
            try:
                worker.start();self.assertTrue(entered.wait(5))
                progress=api.get_job(job["job_id"])[1]
                self.assertEqual("running",progress["status"])
                self.assertGreater(progress["progress"],.1)
                self.assertLess(progress["progress"],.9)
                release.set();worker.join(5);self.assertFalse(worker.is_alive())
                result=api.get_job(job["job_id"])[1]
                self.assertEqual("completed",result["status"])
                self.assertEqual(1.0,result["progress"])
            finally:
                release.set();worker.join(5);api.close()

    def test_input_construction_failure_is_terminal_and_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=1024)
            asset,job=self.setup_job(api)
            api.assets[asset["asset_id"]]["clipping_blocks"]=[0.0]
            result=api.run_reference_job(job["job_id"])[1]
            self.assertEqual("failed",result["status"])
            self.assertEqual(1.0,result["progress"])
            self.assertIn("clipping block coverage mismatch",result["error"])
            api.close()
            restored=RuntimeAPI(storage_dir=directory,window_size_samples=1024)
            try:self.assertEqual(result,restored.get_job(job["job_id"])[1])
            finally:restored.close()
