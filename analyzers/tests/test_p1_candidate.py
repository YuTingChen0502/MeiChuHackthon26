"""Frozen P1 integration tests; fixtures are not new empirical model evidence."""
import copy
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

import numpy as np

from analyzers.separation.p1_bundle import validate_p1_bundle, DEFAULT_SPEC
from analyzers.separation.p1_candidate import P1CandidateAnalyzer, load_p1_candidate, make_p1_candidate_loader
from analyzers.separation.p1_runner import P1Runner, dual_mono
from core.audio.types import AudioWindow
from core.contracts.validation import validate_analyzer_pair

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "models/candidates/nano4-p1-adapted-mvp-v1"


def configured(families=("bass", "guitar", "drums", "vocals", "keys", "flute")):
    return {"instrument_config_version": 1, "instruments": [
        {"instrument_id": str(i), "family": family} for i, family in enumerate(families)]}


def window(samples=None, *, name="obs", start=0):
    return AudioWindow(name, "session", "run", "uploaded_file", name + "-asset", "clock", 44100,
                       start, start + 176400, 4.0 + start / 44100,
                       tuple(samples) if samples is not None else (0.01,) * 176400)


def context(analyzer, audio, prepared, config):
    return {
        "record_type": "AnalyzerContext", "schema_version": "1.0", "model": analyzer.capabilities()["model"],
        "observation": audio.identity(), "instrument_config": config,
        "target": {"target_kind": "reference",
                   "reference": {"reference_id": "ref", "source_asset_hash": "sha256:test-only"}, "baseline": None},
        "comparison_regime": "matched_excerpt",
        "model_specific_context_asset": prepared["model_specific_context_asset"],
        "observation_purpose": "rehearsal", "probe_instrument_id": None,
    }


class TestOnlyRunner:
    """Contract fixture only; production loader cannot select this through metadata."""
    profile_id = "test-only"
    profile = {"test_only": True}
    def __init__(self):
        self.calls = []
        self.closed = False
        self.level = -40.0
    def levels(self, samples):
        self.calls.append(samples)
        return {name: self.level for name in ("drums", "bass", "other", "vocals", "guitar", "piano")}
    def close(self):
        self.closed = True


class P1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = validate_p1_bundle(CANDIDATE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name)
        self.runner = TestOnlyRunner()
        self.analyzer = P1CandidateAnalyzer(self.bundle, self.runner, cache_dir=self.cache, candidate_mode=True)
        self.config = configured()
        self.audio = window()
        self.prepared = self.analyzer.prepare_reference([window(name="ref")], self.config)
        self.ctx = context(self.analyzer, self.audio, self.prepared, self.config)

    def tearDown(self):
        self.analyzer.close()
        self.temp.cleanup()

    def test_one_row_per_instrument_with_unsupported_and_unknown_null(self):
        evidence = self.analyzer.analyze(self.audio, self.ctx)
        validate_analyzer_pair(self.ctx, evidence)
        self.assertEqual(6, len(evidence["measurements"]))
        bass, *others = evidence["measurements"]
        self.assertEqual("valid", bass["validity"])
        self.assertEqual(-40, bass["source_level_db"])
        self.assertEqual([], bass["uncertainty_features"])
        for row in others:
            self.assertIsNone(row["source_level_db"])
            self.assertIsNone(row["target_source_level_db"])
            self.assertEqual("invalid", row["validity"])
            self.assertNotEqual("inactive", row["activity"])
        self.assertEqual(["INSUFFICIENT_EVIDENCE"], others[-1]["reason_codes"])
        self.assertIsNone(self.analyzer.calibration_metadata())
        self.assertIsNone(self.analyzer.acceptance_metadata())
        self.assertFalse(self.analyzer.capabilities()["production_authorized"])

    def test_default_unaccepted_never_returns_numerical_evidence(self):
        a = P1CandidateAnalyzer(self.bundle, TestOnlyRunner(), candidate_mode=False)
        try:
            p = a.prepare_reference([window(name="ref")], self.config)
            ev = a.analyze(self.audio, context(a, self.audio, p, self.config))
            self.assertTrue(all(r["source_level_db"] is None for r in ev["measurements"]))
            self.assertEqual([], a.capabilities()["supported_families"])
        finally:
            a.close()

    def test_same_family_multiple_instances_are_not_attributed_as_one(self):
        c = configured(("bass", "bass"))
        p = self.analyzer.prepare_reference([window(name="ref2")], c)
        ev = self.analyzer.analyze(self.audio, context(self.analyzer, self.audio, p, c))
        self.assertTrue(all(x["reason_codes"] == ["ambiguous_same_family_sources"] for x in ev["measurements"]))

    def test_no_labels_enter_inference_and_context_rejects_extra_labels(self):
        self.analyzer.analyze(self.audio, self.ctx)
        self.assertTrue(all(isinstance(x, tuple) for x in self.runner.calls))
        bad = copy.deepcopy(self.ctx)
        bad["ground_truth"] = {"bass_gain": 4}
        with self.assertRaises(Exception):
            self.analyzer.analyze(self.audio, bad)

    def test_frontend_profile_and_context_identity_fail_closed(self):
        for audio in (replace(self.audio, sample_rate_hz=48000), replace(self.audio, samples=(0.1,)),
                      replace(self.audio, samples=(float("nan"),) + self.audio.samples[1:])):
            with self.assertRaises(ValueError):
                self.analyzer.analyze(audio, self.ctx)
        bad = copy.deepcopy(self.ctx)
        bad["model"]["execution_profile_id"] = "different"
        with self.assertRaisesRegex(ValueError, "profile identity"):
            self.analyzer.analyze(self.audio, bad)

    def test_stable_texture_clipping_and_unmatched_span_abstain(self):
        cases = [
            (self.audio, dict(self.ctx, comparison_regime="stable_texture"), "comparison_regime_unsupported"),
            (replace(self.audio, input_clipped_fraction=0.1), self.ctx, "clipping_outside_candidate_envelope"),
            (window(start=176400), self.ctx, "matched_reference_span_unavailable"),
        ]
        for audio, ctx, reason in cases:
            ctx = copy.deepcopy(ctx)
            ctx["observation"] = audio.identity()
            ev = self.analyzer.analyze(audio, ctx)
            self.assertEqual([reason], ev["measurements"][0]["reason_codes"])
            self.assertIsNone(ev["measurements"][0]["source_level_db"])

    def test_live_reference_executes_before_uncalibrated_publication(self):
        mic = replace(self.audio, input_kind="live_microphone", clock_id="mic-clock",
                      analysis_run_id="mic-run", input_asset_or_device_id="mic-device")
        ctx = dict(self.ctx, observation=mic.identity(), observation_purpose="live")
        before = len(self.runner.calls)
        evidence = self.analyzer.analyze(mic, ctx)
        self.assertEqual(before + 1, len(self.runner.calls))
        validate_analyzer_pair(ctx, evidence)
        row = evidence["measurements"][0]
        self.assertEqual("valid", row["validity"])
        self.assertEqual(-40, row["source_level_db"])
        self.assertIn("real_room_not_validated", row["reason_codes"])
        self.assertIn("uncalibrated_candidate", row["reason_codes"])
        self.assertIsNone(self.analyzer.calibration_metadata())

    def test_model_runs_without_bass_configuration_or_numeric_target(self):
        for families, ref_level in ((("drums", "guitar"), -40.0), (("bass",), None)):
            c = configured(families)
            self.runner.level = ref_level
            prepared = self.analyzer.prepare_reference([window(name="ref-case")], c)
            self.runner.level = -40.0
            mic = replace(self.audio, input_kind="live_microphone")
            ctx = context(self.analyzer, mic, prepared, c)
            ctx["observation_purpose"] = "live"
            before = len(self.runner.calls)
            evidence = self.analyzer.analyze(mic, ctx)
            self.assertEqual(before + 1, len(self.runner.calls))
            self.assertTrue(all(r["source_level_db"] is None for r in evidence["measurements"]))

    def test_relative_hop_and_restart_matching_without_alignment_guessing(self):
        refs = [replace(window(name="ref-" + str(i), start=i*44100),
                        input_asset_or_device_id="reference-file") for i in range(2)]
        prepared = self.analyzer.prepare_reference(refs, self.config)
        for start, clock, expected in ((0, "generation1", "ref-0"),
                                       (44100, "generation1", "ref-1"),
                                       (0, "generation2", "ref-0")):
            mic = replace(window(start=start), input_kind="live_microphone", clock_id=clock)
            ctx = context(self.analyzer, mic, prepared, self.config)
            ctx["observation_purpose"] = "live"
            self.assertEqual(expected, self.analyzer.analyze(mic, ctx)["matched_context_window_id"])
        mic = replace(window(start=88200), input_kind="live_microphone")
        ctx = context(self.analyzer, mic, prepared, self.config)
        before = len(self.runner.calls)
        ev = self.analyzer.analyze(mic, ctx)
        self.assertEqual(before + 1, len(self.runner.calls))
        self.assertIsNone(ev["matched_context_window_id"])
        self.assertTrue(all(r["source_level_db"] is None and r["target_source_level_db"] is None
                            for r in ev["measurements"]))
        self.assertEqual(["matched_reference_span_unavailable"], ev["measurements"][0]["reason_codes"])

    def test_silent_source_does_not_become_supported_normal(self):
        self.runner.level = None
        ev = self.analyzer.analyze(self.audio, self.ctx)
        self.assertEqual(["source_below_activity_floor"], ev["measurements"][0]["reason_codes"])
        self.assertIsNone(ev["measurements"][0]["source_level_db"])

    def test_durable_cache_reuse_and_target_binding(self):
        self.analyzer.analyze(self.audio, self.ctx)
        self.analyzer.close()
        a = P1CandidateAnalyzer(self.bundle, TestOnlyRunner(), cache_dir=self.cache, candidate_mode=True)
        try:
            ev = a.analyze(self.audio, self.ctx)
            self.assertEqual("valid", ev["measurements"][0]["validity"])
            bad = copy.deepcopy(self.ctx)
            bad["target"]["reference"]["reference_id"] = "other-reference"
            self.assertEqual(["reference_target_binding_mismatch"],
                             a.analyze(self.audio, bad)["measurements"][0]["reason_codes"])
        finally:
            a.close()

    def test_reference_rejects_mixed_input_timelines(self):
        one = window(name="reference", start=0)
        two = replace(window(name="reference", start=44100), input_asset_or_device_id="another-asset")
        with self.assertRaisesRegex(ValueError, "incompatible input timelines"):
            self.analyzer.prepare_reference([one, two], self.config)

    def test_corrupt_or_missing_reference_context(self):
        key = self.prepared["model_specific_context_asset"].split(":")[1]
        file = self.cache / (key + ".json")
        original = file.read_bytes()
        file.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "cache hash"):
            self.analyzer.analyze(self.audio, self.ctx)
        file.unlink()
        self.assertEqual(["reference_context_unavailable"],
                         self.analyzer.analyze(self.audio, self.ctx)["measurements"][0]["reason_codes"])

    def test_close_is_idempotent_and_host_acceptance_is_rejected(self):
        self.analyzer.close()
        self.analyzer.close()
        self.assertTrue(self.runner.closed)
        with self.assertRaisesRegex(ValueError, "closed"):
            self.analyzer.analyze(self.audio, self.ctx)
        with self.assertRaisesRegex(ValueError, "production acceptance"):
            load_p1_candidate(CANDIDATE, acceptance={"pretend": "approved"})

    def test_amplitude_frontend_preserves_scale_and_channels_exactly(self):
        audio = np.linspace(-0.4, 0.4, 176400)
        original = dual_mono(audio)
        doubled = dual_mono(audio * 2)
        np.testing.assert_array_equal(original[0], original[1])
        np.testing.assert_array_equal(doubled, original * 2)
        self.assertLess(float(np.max(np.abs(doubled))), 1)

    def test_host_loader_callback_preserves_explicit_mode_and_identity(self):
        loader = make_p1_candidate_loader(cache_dir=self.cache, candidate_mode=True)
        with patch("analyzers.separation.p1_candidate.P1Runner", return_value=TestOnlyRunner()):
            loaded = loader(CANDIDATE, registry=None, expected_model=self.analyzer.capabilities()["model"])
            self.assertTrue(loaded.capabilities()["candidate_mode"])
            loaded.close()
        with patch("analyzers.separation.p1_candidate.P1Runner", return_value=TestOnlyRunner()):
            with self.assertRaisesRegex(ValueError, "Requested model/profile"):
                loader(CANDIDATE, expected_model={"wrong": "model"})


class P1BundleTests(unittest.TestCase):
    def test_exact_frozen_archive_identity(self):
        bundle = validate_p1_bundle(CANDIDATE)
        self.assertEqual("b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229",
                         bundle.manifest["bundled_adapted_checkpoint"]["sha256"])
        self.assertEqual("3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0", bundle.manifest["source_repository_sha"])

    def test_missing_corrupt_base_and_adapted_files_fail_closed(self):
        bundle = validate_p1_bundle(CANDIDATE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in bundle.spec["files"]:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(bundle.data(name))
            validate_p1_bundle(root)
            for name in ("checkpoint.pt", bundle.manifest["upstream_pretrained_checkpoint"]["path"]):
                file = root / name
                original = file.read_bytes()
                file.write_bytes(b"corrupt")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    validate_p1_bundle(root)
                file.unlink()
                with self.assertRaisesRegex(ValueError, "Missing bundle file"):
                    validate_p1_bundle(root)
                file.write_bytes(original)
            spec = copy.deepcopy(bundle.spec)
            spec["bundle_id"] = "not-this-bundle"
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                validate_p1_bundle(root, trusted_spec=spec)

    def test_diagnostics_status_read_does_not_wait_for_model_execution(self):
        from analyzers.separation.p1_runner import _EXECUTION_LOCK
        runner = P1Runner.__new__(P1Runner)  # Diagnostic lock unit test; no simulated model execution.
        runner._diagnostics_lock = threading.Lock()
        runner._model_calls_started = 1
        runner._model_calls_completed = 0
        runner._last_inference = None
        finished = threading.Event()
        observed = []
        def read_status():
            observed.append(runner.execution_diagnostics())
            finished.set()
        with _EXECUTION_LOCK:
            thread = threading.Thread(target=read_status, daemon=True)
            thread.start()
            nonblocking = finished.wait(1)
        thread.join(2)
        self.assertTrue(nonblocking, "Status caller blocked behind actual inference lock")
        self.assertEqual(1, observed[0]["model_calls_started"])
        self.assertEqual(0, observed[0]["model_calls_completed"])

    def test_invalid_archive_pin_cannot_choose_alternate_upstream(self):
        spec = json.loads(DEFAULT_SPEC.read_text())
        spec["archive_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "archive hash"):
            validate_p1_bundle(CANDIDATE, trusted_spec=spec)


class P1ActualCPUSmokeTests(unittest.TestCase):
    def test_actual_reconstruction_determinism_and_published_smoke_parity(self):
        bundle = validate_p1_bundle(CANDIDATE)
        with patch("torch.hub.load_state_dict_from_url", side_effect=AssertionError("No network fallback")):
            runner = P1Runner(bundle, device="cpu")
        a = P1CandidateAnalyzer(bundle, runner, candidate_mode=True)
        try:
            def read(name):
                with wave.open(str(CANDIDATE / "runtime_smoke" / (name + ".wav"))) as w:
                    self.assertEqual((1, 4, 44100, 176400), (w.getnchannels(), w.getsampwidth(),
                                                           w.getframerate(), w.getnframes()))
                    return np.frombuffer(w.readframes(w.getnframes()), dtype="<i4").astype(np.float64) / 2147483648
            c = configured()
            ref, obs = window(read("reference"), name="reference"), window(read("observation"))
            prepared = a.prepare_reference([ref], c)
            ctx = context(a, obs, prepared, c)
            ctx["observation_purpose"] = "live"
            first = a.analyze(obs, ctx)
            file_diagnostics = a.execution_diagnostics()
            second = a.analyze(obs, ctx)
            self.assertEqual(first, second)
            mic = replace(obs, window_id="mic-window", input_kind="live_microphone",
                          clock_id="mic-clock", analysis_run_id="mic-run", input_asset_or_device_id="test-mic")
            mic_context = dict(ctx, observation=mic.identity())
            mic_evidence = a.analyze(mic, mic_context)
            validate_analyzer_pair(mic_context, mic_evidence)
            mic_diagnostics = a.execution_diagnostics()
            self.assertEqual(2, file_diagnostics["model_calls_completed"])  # reference + file
            self.assertEqual(4, mic_diagnostics["model_calls_completed"])  # repeat + mic
            self.assertEqual(4, mic_diagnostics["model_calls_started"])
            for field in ("source_levels_dbfs", "source_waveform_sha256", "source_order", "source_shape"):
                self.assertEqual(file_diagnostics["last_inference"][field], mic_diagnostics["last_inference"][field])
            self.assertEqual(["drums", "bass", "other", "vocals", "guitar", "piano"],
                             mic_diagnostics["last_inference"]["source_order"])
            for left, right in zip(first["measurements"], mic_evidence["measurements"]):
                self.assertEqual(left["source_level_db"], right["source_level_db"])
                self.assertEqual(left["validity"], right["validity"])
            # A dropout-shifted span has no reference match, but still runs all six sources.
            unmatched = replace(mic, sample_start=123, sample_end=176523)
            unmatched_ctx = dict(ctx, observation=unmatched.identity())
            unmatched_evidence = a.analyze(unmatched, unmatched_ctx)
            validate_analyzer_pair(unmatched_ctx, unmatched_evidence)
            unmatched_diag = a.execution_diagnostics()
            self.assertEqual(5, unmatched_diag["model_calls_completed"])
            self.assertEqual(mic_diagnostics["last_inference"]["source_waveform_sha256"],
                             unmatched_diag["last_inference"]["source_waveform_sha256"])
            self.assertIsNone(unmatched_evidence["matched_context_window_id"])
            self.assertTrue(all(r["source_level_db"] is None and r["target_source_level_db"] is None
                                for r in unmatched_evidence["measurements"]))
            self.assertEqual(["matched_reference_span_unavailable"],
                             unmatched_evidence["measurements"][0]["reason_codes"])
            validate_analyzer_pair(ctx, first)
            bass = first["measurements"][0]
            published = json.loads((CANDIDATE / "runtime_smoke/inference-run-1.json").read_text())
            expected = published["logical_output"]["family_evidence"][0]
            # Engineering cross-platform parity tolerance, not a tuned model/action threshold.
            self.assertAlmostEqual(bass["source_level_db"], expected["observation_source_level_dbfs"], delta=0.01)
            self.assertAlmostEqual(bass["target_source_level_db"], expected["reference_source_level_dbfs"], delta=0.01)
            for key in runner.base_hashes:
                self.assertNotEqual(runner.base_hashes[key], runner.adapted_hashes[key])
            self.assertEqual(runner.adapted_hashes, bundle.manifest["adaptation_identity"]["expected_adapted_module_sha256"])
            self.assertEqual("source_levels", first["evidence_mode"])
        finally:
            a.close()


if __name__ == "__main__":
    unittest.main()
