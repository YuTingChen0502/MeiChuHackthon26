"""Actual generic ML loader through Runtime config; synthetic fixtures never accepted."""
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from analyzers.bundle_validation import validate_bundle
from analyzers.reference_contexts import ReferenceContextStore
from analyzers.tests import bundle_fixtures as bundles
from apps.api.config import runtime_options
from apps.api.service import RuntimeAPI, APIError
from core.audio import MicAudioInput
import test_api_service as fixtures


class ActualBundleTests(unittest.TestCase):
    def test_real_loader_mapping_bridge_durable_context_and_abstained_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/"bundle";bundles.write_bundle(bundle)
            cache={};created=[]
            def factory(value):
                backend=bundles.TestBackend(value,cache);created.append(backend);return backend
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(bundle),"PA_RUNTIME_STORAGE_DIR":str(root/"runtime")},
                                    registry={"test-only-adapter":factory})
            api=RuntimeAPI(storage_dir=root/"runtime",window_size_samples=8,available_audio_devices={"mic-1"},**options)
            try:
                self.assertEqual("test-only",api.health()[1]["provider"])
                self.assertFalse(api.health()[1]["example_only"])
                _,project=api.create_project({"name":"TEST ONLY actual loader"})
                _,song=api.create_song({"project_id":project["project_id"],"name":"Synthetic unaccepted fixture",
                                      "instruments":bundles.config()["instruments"]})
                self.assertEqual([],song["supported_families"])
                _,asset=api.upload_audio(fixtures.wav_bytes([.1]*16,sample_rate=8),filename="synthetic.wav")
                _,job=api.start_reference_job(song["song_id"],{"asset_id":asset["asset_id"]})
                self.assertEqual("completed",api.run_reference_job(job["job_id"])[1]["status"])
                _,snapshot=api.create_session({"song_id":song["song_id"],"reference_id":job["reference_id"],
                    "source":{"input_kind":"live_microphone","input_asset_or_device_id":"mic-1"},
                    "capture_fingerprint":{"device_id":"mic-1","profile_id":"test-unverified","native_sample_rate_hz":8,
                        "channels":1,"gain_setting":None,"enhancements_verified_disabled":None,"geometry_id":None,"provenance":"unverified"}})
                session=api.runtime_session(snapshot["session_id"])
                audio=MicAudioInput(input_asset_or_device_id="mic-1",clock_id=session.source["clock_id"],
                                    sample_rate_hz=8,samples=[.1]*8,origin_monotonic_s=10)
                window=next(api.pipeline.iter_windows(audio,session_id=session.session_id,analysis_run_id="test"))
                frame=session.observe_window(window)
                self.assertFalse(frame["example_only"])
                for instrument in frame["instruments"]:
                    self.assertIsNone(instrument["balance_deviation_db"])
                    self.assertTrue(instrument["confidence"]["abstained"])
                    self.assertIn("artifact_not_accepted",instrument["confidence"]["reasons"])
                self.assertTrue(any((root/"runtime"/"context-cache").iterdir()))
            finally:api.close()
            self.assertTrue(all(backend.closed for backend in created))

    def test_registry_object_is_preserved_and_synthetic_host_acceptance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/"bundle";bundles.write_bundle(bundle,with_results=True)
            registry=bundles.registry(context_store=ReferenceContextStore(root/"cache"))
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(bundle)},registry=registry)
            analyzer=options["analyzer_factory"]();analyzer.close()
            acceptance=asdict(bundles.acceptance(validate_bundle(bundle)))
            review=root/"host-review.json"
            review.write_text(json.dumps({"model":bundles.MODEL,"acceptance":acceptance}),encoding="utf-8")
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(bundle),"PA_HOST_REVIEW":str(review)},registry=registry)
            api=RuntimeAPI(storage_dir=root/"runtime",window_size_samples=8,**options)
            with self.assertRaises(APIError) as failure:api.health()
            self.assertEqual("model_unavailable",failure.exception.code)
            self.assertIn("Synthetic",str(failure.exception.__cause__))
            api.close()

    def test_actual_loader_unknown_adapter_and_hash_corruption_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle=Path(directory)/"bundle";bundles.write_bundle(bundle)
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(bundle),"PA_RUNTIME_STORAGE_DIR":str(Path(directory)/"runtime")})
            with self.assertRaisesRegex(ValueError,"not host-allowlisted"):options["analyzer_factory"]()
            (bundle/"weights.bin").write_bytes(b"corrupted fixture")
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(bundle)},registry=bundles.registry())
            with self.assertRaisesRegex(ValueError,"hash mismatch"):options["analyzer_factory"]()

    def test_backend_unavailable_state_is_diagnostic_not_identity_change(self):
        from analyzers.bundles import BackendUnavailable
        from core.runtime.real_analyzer import RealAnalyzerAdapter
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundles.write_bundle(root)
            # No acceptance: diagnostic shell deliberately never invokes backend
            # numerical perception, and state transitions must not alter identity.
            options=runtime_options(environment={"PA_MODEL_BUNDLE":str(root)},registry=bundles.registry())
            shell=options["analyzer_factory"]();adapter=RealAnalyzerAdapter(shell)
            prepared=adapter.prepare_reference([bundles.window()],bundles.config())
            context=bundles.context(asset=prepared["model_specific_context_asset"])
            original=shell.capabilities
            def unavailable():
                result=original();result["state"]="unavailable";return result
            shell.capabilities=unavailable
            evidence=adapter.analyze(bundles.window(),context)
            self.assertTrue(all(row["validity"]=="invalid" for row in evidence["measurements"]))
            adapter.close()
