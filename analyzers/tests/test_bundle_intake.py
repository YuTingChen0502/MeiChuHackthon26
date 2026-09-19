import copy
import hashlib
import json
import tempfile
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from analyzers.bundle_validation import inspect_remote_metadata, validate_bundle
from analyzers.bundles import BackendRegistry, BackendUnavailable, load_bundle
from analyzers.reference_contexts import ReferenceContextStore
from analyzers.tests.bundle_fixtures import (
    MODEL, TestBackend, acceptance, config, context, registry, save_manifest, window, write_bundle,
)
from benchmarks.import_bundle import import_bundle
from benchmarks.import_remote_evidence import import_remote_evidence
from core.contracts.validation import validate_analyzer_pair


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.m = write_bundle(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def digest(self):
        return hashlib.sha256((self.source / "manifest.json").read_bytes()).hexdigest()

    def test_nano4_and_mi300_both_validate_without_choosing_backend(self):
        self.assertEqual("nano4", validate_bundle(self.source).manifest["origin"]["execution_site"])
        other = self.root / "mi300"
        write_bundle(other, site="mi300")
        self.assertEqual("mi300", validate_bundle(other).manifest["origin"]["execution_site"])
        for kind in ("separation", "hybrid"):
            self.m["backend"]["kind"] = kind
            save_manifest(self.source, self.m)
            self.assertEqual(kind, validate_bundle(self.source).manifest["backend"]["kind"])

    def test_hash_and_missing_file_rejected(self):
        (self.source / "weights.bin").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_bundle(self.source)
        (self.source / "weights.bin").unlink()
        with self.assertRaisesRegex(ValueError, "Missing bundle file"):
            validate_bundle(self.source)

    def test_malformed_duplicate_keys_and_unknown_manifest_fields_rejected(self):
        (self.source / "manifest.json").write_text('{"schema_version":"1.0","schema_version":"2.0"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_bundle(self.source)
        self.m["python_module"] = "execute.me"
        save_manifest(self.source, self.m)
        with self.assertRaisesRegex(ValueError, "manifest fields"):
            validate_bundle(self.source)

    def test_frontend_taxonomy_scale_and_profile_incompatibility(self):
        for key in ("frontend_id", "taxonomy_id", "level_scale_id"):
            bad = copy.deepcopy(self.m)
            bad["model"][key] = "incompatible"
            save_manifest(self.source, bad)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                validate_bundle(self.source)
        save_manifest(self.source, self.m)
        expected = dict(MODEL, execution_profile_id="wrong-profile")
        with self.assertRaisesRegex(ValueError, "Requested model"):
            load_bundle(self.source, registry=registry(), expected_model=expected)

    def test_centered_level_convention_cannot_be_mislabeled_as_source_delta(self):
        path = self.source / "scale.json"
        scale = json.loads(path.read_text())
        scale["quantity"] = "centered_balance"
        path.write_text(json.dumps(scale))
        self.m["files"]["scale"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        save_manifest(self.source, self.m)
        with self.assertRaisesRegex(ValueError, "source-level convention"):
            validate_bundle(self.source)

    def test_unknown_backend_does_not_import_manifest_code(self):
        with self.assertRaisesRegex(ValueError, "not host-allowlisted"):
            load_bundle(self.source, registry=BackendRegistry())

    def test_unaccepted_analyzer_propagates_identity_and_null_evidence(self):
        analyzer = load_bundle(self.source, registry=registry())
        prepared = analyzer.prepare_reference([window()], config())
        ctx = context(asset=prepared["model_specific_context_asset"])
        evidence = analyzer.analyze(window(), ctx)
        validate_analyzer_pair(ctx, evidence)
        self.assertEqual(MODEL, analyzer.capabilities()["model"])
        self.assertEqual([], analyzer.capabilities()["supported_families"])
        self.assertTrue(all(r["source_level_delta_db"] is None and r["validity"] == "invalid"
                            for r in evidence["measurements"]))
        analyzer.close()
        analyzer.close()
        with self.assertRaisesRegex(ValueError, "closed"):
            analyzer.analyze(window(), ctx)

    def test_synthetic_calibration_cannot_become_production(self):
        write_bundle(self.source, with_results=True)
        bundle = validate_bundle(self.source)
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            load_bundle(self.source, registry=registry(), acceptance=acceptance(bundle))

    def test_accepted_engineering_and_competition_lineage_are_distinct(self):
        # Simulated external declarations exercise authorization checks, not ML validity.
        write_bundle(self.source, declared_material="real_recorded", with_results=True)
        bundle = validate_bundle(self.source)
        analyzer = load_bundle(self.source, registry=registry(), acceptance=acceptance(bundle))
        prepared = analyzer.prepare_reference([window()], config())
        ctx = context(asset=prepared["model_specific_context_asset"])
        evidence = analyzer.analyze(window(), ctx)
        validate_analyzer_pair(ctx, evidence)
        self.assertTrue(all(r["validity"] == "valid" for r in evidence["measurements"]))
        self.assertNotIn("confidence", evidence)
        with self.assertRaisesRegex(ValueError, "MI300"):
            load_bundle(self.source, registry=registry(), acceptance=acceptance(bundle, use="competition"))

    def test_context_reopens_with_same_bundle_cache_and_binds_target_immutably(self):
        cache = {}
        first = load_bundle(self.source, registry=registry(
            cache=cache, context_store=ReferenceContextStore(self.root / "contexts")))
        prepared = first.prepare_reference([window()], config())
        ctx = context(asset=prepared["model_specific_context_asset"])
        first.analyze(window(), ctx)
        first.close()
        second = load_bundle(self.source, registry=registry(
            cache=cache, context_store=ReferenceContextStore(self.root / "contexts")))
        evidence = second.analyze(window(), ctx)
        self.assertEqual(["artifact_not_accepted"], evidence["measurements"][0]["reason_codes"])
        changed = copy.deepcopy(ctx)
        changed["target"]["reference"]["reference_id"] = "different"
        evidence = second.analyze(window(), changed)
        self.assertEqual(["reference_target_binding_mismatch"], evidence["measurements"][0]["reason_codes"])

    def test_context_missing_and_pcm_identity_mismatch_fail_safely(self):
        analyzer = load_bundle(self.source, registry=registry())
        evidence = analyzer.analyze(window(), context())
        self.assertEqual("reference_context_unavailable", evidence["measurements"][0]["reason_codes"][0])
        wrong = context()
        wrong["observation"]["window_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "PCM/window identity"):
            analyzer.analyze(window(), wrong)

    def test_bundle_changed_after_validation_is_rejected_before_factory(self):
        bundle = validate_bundle(self.source)
        (self.source / "weights.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            registry().instantiate(bundle)

    def test_directory_import_is_idempotent_and_never_changes_source(self):
        imported = import_bundle(self.source, self.root / "store", expected_manifest_sha256=self.digest())
        self.assertEqual(self.digest(), imported.manifest_sha256)
        same = import_bundle(self.source, self.root / "store", expected_manifest_sha256=self.digest())
        self.assertEqual(imported.root, same.root)
        self.assertTrue((self.source / "weights.bin").exists())

    def test_zip_path_traversal_and_import_size_limit(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../escape.py", "bad")
            z.write(self.source / "manifest.json", "manifest.json")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            import_bundle(archive, self.root / "store", expected_manifest_sha256=self.digest())
        with self.assertRaisesRegex(ValueError, "byte limit"):
            import_bundle(self.source, self.root / "store", expected_manifest_sha256=self.digest(), max_bytes=10)
        self.assertFalse((self.root / "escape.py").exists())
        self.assertEqual([], list((self.root / "store").glob(".intake-*")))

    def test_metadata_only_import_never_copies_checkpoint(self):
        (self.source / "weights.bin").unlink()
        receipt = import_remote_evidence(self.source, self.root / "evidence",
                                         expected_manifest_sha256=self.digest())
        destination = Path(receipt["metadata_path"])
        self.assertEqual(0, receipt["binary_bytes_copied"])
        self.assertFalse((destination / "weights.bin").exists())
        self.assertEqual("ARTIFACT_BYTES_NOT_VERIFIED", inspect_remote_metadata(destination)["status"])
        with self.assertRaisesRegex(ValueError, "Missing bundle file"):
            validate_bundle(destination)

    def test_backend_unavailable_abstains_and_tracks_state(self):
        write_bundle(self.source, declared_material="real_recorded", with_results=True)
        bundle = validate_bundle(self.source)
        class MissingDevice(TestBackend):
            def analyze(self, audio, ctx):
                raise BackendUnavailable("test device unavailable")
        r = BackendRegistry()
        r.register("test-only-adapter", lambda b: MissingDevice(b, {}))
        analyzer = load_bundle(self.source, registry=r, acceptance=acceptance(bundle))
        prepared = analyzer.prepare_reference([window()], config())
        ctx = context(asset=prepared["model_specific_context_asset"])
        evidence = analyzer.analyze(window(), ctx)
        validate_analyzer_pair(ctx, evidence)
        self.assertEqual("unavailable", analyzer.capabilities()["state"])
        self.assertTrue(all(x["source_level_delta_db"] is None for x in evidence["measurements"]))
        self.assertEqual(["backend_unavailable"], evidence["measurements"][0]["reason_codes"])

    def test_backend_invalid_output_is_rejected_and_constructor_mismatch_closes(self):
        write_bundle(self.source, declared_material="real_recorded", with_results=True)
        bundle = validate_bundle(self.source)
        class BadOutput(TestBackend):
            def analyze(self, audio, ctx):
                value = super().analyze(audio, ctx)
                value["model"]["execution_profile_id"] = "wrong"
                return value
        r = BackendRegistry()
        r.register("test-only-adapter", lambda b: BadOutput(b, {}))
        analyzer = load_bundle(self.source, registry=r, acceptance=acceptance(bundle))
        prepared = analyzer.prepare_reference([window()], config())
        with self.assertRaises(Exception):
            analyzer.analyze(window(), context(asset=prepared["model_specific_context_asset"]))
        backend = TestBackend(bundle, {})
        backend.capabilities = lambda: {"model": dict(MODEL, frontend_id="bad")}
        r2 = BackendRegistry()
        r2.register("test-only-adapter", lambda b: backend)
        with self.assertRaisesRegex(ValueError, "identity"):
            load_bundle(self.source, registry=r2)
        self.assertTrue(backend.closed)

    def test_mi300_competition_gate_and_accepted_context_reopen(self):
        write_bundle(self.source, site="mi300", declared_material="real_recorded", with_results=True)
        bundle = validate_bundle(self.source)
        r = registry(context_store=ReferenceContextStore(self.root / "contexts"))
        first = load_bundle(self.source, registry=r, acceptance=acceptance(bundle, use="competition"))
        prepared = first.prepare_reference([window()], config())
        ctx = context(asset=prepared["model_specific_context_asset"])
        first.close()
        second = load_bundle(self.source, registry=r, acceptance=acceptance(bundle, use="competition"))
        self.assertTrue(all(x["validity"] == "valid" for x in second.analyze(window(), ctx)["measurements"]))

    def test_valid_zip_intake_and_incomplete_evidence_rejection(self):
        archive = self.root / "good.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for p in self.source.iterdir():
                z.write(p, p.name)
        imported = import_bundle(archive, self.root / "store", expected_manifest_sha256=self.digest())
        self.assertEqual(self.digest(), imported.manifest_sha256)
        self.m["components"]["benchmark_reports"] = ["missing-report"]
        save_manifest(self.source, self.m)
        with self.assertRaisesRegex(ValueError, "Unknown component"):
            validate_bundle(self.source)

    def test_repository_evidence_rejects_signed_urls_and_credentials_without_disclosure(self):
        for value in (
            {"download": "https://example.invalid/file?X-Amz-Signature=sensitive-unit-fixture"},
            {"access_token": "sensitive-unit-fixture"},
            {"note": "Bearer sensitive-unit-fixture"},
        ):
            self.m = write_bundle(self.source)
            path = self.source / "env.json"
            metadata = json.loads(path.read_text())
            metadata.update(value)
            path.write_text(json.dumps(metadata))
            self.m["files"]["env"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            digest = self.m["files"]["env"]["sha256"]
            self.m["origin"]["environment_sha256"] = digest
            self.m["lineage"][-1]["environment_sha256"] = digest
            training_path = self.source / "training.json"
            training = json.loads(training_path.read_text())
            training["origin"]["environment_sha256"] = digest
            training["lineage_step"]["environment_sha256"] = digest
            training_path.write_text(json.dumps(training))
            self.m["files"]["training"]["sha256"] = hashlib.sha256(training_path.read_bytes()).hexdigest()
            save_manifest(self.source, self.m)
            with self.assertRaisesRegex(ValueError, "redacted, rehashed") as caught:
                import_remote_evidence(self.source, self.root / "evidence",
                                       expected_manifest_sha256=self.digest())
            self.assertNotIn("sensitive-unit-fixture", str(caught.exception))
            self.assertEqual([], list((self.root / "evidence").iterdir()))
            self.assertIn("sensitive-unit-fixture", path.read_text())  # source never silently sanitized

    def test_generic_loader_and_intake_do_not_require_numpy_or_torch(self):
        script = """
import importlib.abc
import sys
import tempfile
from pathlib import Path
class NoTrainingDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy', 'torch', 'torchaudio', 'demucs'}:
            raise ImportError('optional training dependency forbidden in generic intake')
sys.meta_path.insert(0, NoTrainingDependencies())
from analyzers.bundle_validation import validate_bundle
from analyzers.bundles import load_bundle
from analyzers.tests.bundle_fixtures import write_bundle, registry
from benchmarks.import_bundle import import_bundle
from benchmarks.import_remote_evidence import import_remote_evidence
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    write_bundle(root / 'source')
    bundle = validate_bundle(root / 'source')
    imported = import_bundle(root / 'source', root / 'store',
                             expected_manifest_sha256=bundle.manifest_sha256)
    import_remote_evidence(root / 'source', root / 'evidence',
                           expected_manifest_sha256=bundle.manifest_sha256)
    analyzer = load_bundle(imported.root, registry=registry())
    assert analyzer.capabilities()['supported_families'] == []
    analyzer.close()
"""
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                   cwd=Path(__file__).resolve().parents[2])
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_undeclared_cache_or_optimizer_file_is_rejected(self):
        (self.source / "optimizer.bin").write_bytes(b"should not be imported")
        self.m["files"]["optimizer"] = {"path": "optimizer.bin", "kind": "binary",
                                        "sha256": hashlib.sha256(b"should not be imported").hexdigest()}
        save_manifest(self.source, self.m)
        with self.assertRaisesRegex(ValueError, "Unreferenced files"):
            inspect_remote_metadata(self.source)


if __name__ == "__main__":
    unittest.main()
