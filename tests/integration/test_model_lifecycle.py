"""Model-independent resource ownership and unavailable/replacement scenarios."""
import copy
import tempfile
import unittest
from pathlib import Path
from apps.api.config import runtime_options
from apps.api.service import RuntimeAPI, APIError
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer
import test_api_service as fixtures


class Tracked(ContinuousFakeInstrumentAnalyzer):
    def __init__(self):
        super().__init__();self.closes=0
    def close(self):
        self.closes+=1;super().close()


class ModelLifecycleTests(unittest.TestCase):
    def api(self,path,factory=Tracked):
        return RuntimeAPI(storage_dir=path,window_size_samples=10,available_audio_devices={"mic-1"},analyzer_factory=factory)

    def test_health_song_reference_and_session_resources_close(self):
        created=[]
        def factory():
            model=Tracked();created.append(model);return model
        with tempfile.TemporaryDirectory() as directory:
            api=self.api(directory,factory)
            api.health();api.health()
            self.assertEqual(1,len(created));self.assertEqual(1,created[0].closes)
            snapshot=fixtures.RuntimeAPIServiceTests().create_rehearsal_session(api)[3]
            self.assertEqual([1,1,0],[model.closes for model in created])
            session=api.runtime_session(snapshot["session_id"])
            api.post_action(session.session_id,fixtures.command(session.snapshot(),"stop-owned","stop",{}))
            api.close();api.close()
            self.assertEqual([1,1,1],[model.closes for model in created])

    def test_missing_or_failed_bundle_never_uses_fake(self):
        def failed(): raise RuntimeError("load failed")
        with tempfile.TemporaryDirectory() as directory:
            for factory in (failed,runtime_options(environment={})["analyzer_factory"]):
                api=self.api(directory,factory)
                with self.assertRaises(APIError) as result: api.health()
                self.assertEqual("model_unavailable",result.exception.code)
                api.close()

    def test_explicit_loader_registry_and_acceptance_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def loader(path,**kw): calls.append((path,kw));return Tracked()
            allowed={"test-only":lambda value: None}
            options=runtime_options(environment={"PA_MODEL_BUNDLE":directory},registry=allowed,loader=loader)
            model=options["analyzer_factory"]();model.close()
            self.assertEqual(Path(directory),calls[0][0])
            self.assertEqual(allowed,calls[0][1]["registry"])
            self.assertIsNone(calls[0][1]["acceptance"])
            self.assertIsNone(options["evidence_policy"])

    def test_reference_load_failure_becomes_durable_failed_job(self):
        with tempfile.TemporaryDirectory() as directory:
            api=self.api(directory)
            fixtures.RuntimeAPIServiceTests().create_rehearsal_session(api)
            song=next(iter(api.songs.values()));asset=next(iter(api.assets.values()))
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
            api.analyzer_factory=lambda: (_ for _ in ()).throw(RuntimeError("failure"))
            _,result=api.run_reference_job(job["job_id"])
            self.assertEqual("failed",result["status"])
            api.close()
            restored=self.api(directory)
            self.assertEqual("failed",restored.get_job(job["job_id"])[1]["status"])
            restored.close()

    def test_restart_does_not_load_retired_model_and_interrupts_queued_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            api=self.api(directory);snapshot=fixtures.RuntimeAPIServiceTests().create_rehearsal_session(api)[3]
            song=next(iter(api.songs.values()));asset=next(iter(api.assets.values()))
            _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
            api.close()
            def forbidden(): raise AssertionError("historical model must not load")
            restored=self.api(directory,forbidden)
            state=restored.get_session(snapshot["session_id"])[1]
            self.assertEqual(snapshot["execution"],state["execution"])
            self.assertIn("runtime_restart_requires_new_session",state["suspension_reasons"])
            self.assertEqual("failed",restored.get_job(job["job_id"])[1]["status"])
            restored.close()

    def test_changed_factory_identity_rejected_and_closed(self):
        created=[]
        def factory():
            model=Tracked()
            if created:
                original=model.capabilities
                def changed():
                    value=original();value["model"]["model_bundle_id"]="replacement";return value
                model.capabilities=changed
            created.append(model);return model
        with tempfile.TemporaryDirectory() as directory:
            api=self.api(directory,factory);api.health()
            with self.assertRaises(APIError) as error: api._new_analyzer()
            self.assertEqual("model_identity_changed",error.exception.code)
            self.assertEqual([1,1],[model.closes for model in created]);api.close()
