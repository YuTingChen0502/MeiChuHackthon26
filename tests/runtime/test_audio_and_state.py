import copy
import unittest

from core.audio import FileAudioInput, MicAudioInput, SharedAudioPipeline
from core.contracts.validation import PUBLIC, validate_record
from core.runtime.deviation import FrameBuilder
from core.runtime.fake_analyzer import FakeEvidenceSpec, FakeInstrumentAnalyzer
from core.runtime.quality import quality_state


class AudioAndStateTests(unittest.TestCase):
    def setUp(self):
        self.samples = [index / 100.0 for index in range(20)]
        self.pipeline = SharedAudioPipeline(window_size_samples=10, hop_size_samples=10)

    def test_file_and_microphone_converge_on_identical_pcm_windows(self):
        common = dict(
            clock_id="clock-1",
            sample_rate_hz=10,
            samples=self.samples,
            origin_monotonic_s=5.0,
            chunk_size_samples=4,
        )
        file_input = FileAudioInput(input_asset_or_device_id="asset-1", **common)
        mic_input = MicAudioInput(input_asset_or_device_id="mic-1", **common)
        file_windows = list(
            self.pipeline.iter_windows(file_input, session_id="session-1", analysis_run_id="file-run")
        )
        mic_windows = list(
            self.pipeline.iter_windows(mic_input, session_id="session-1", analysis_run_id="mic-run")
        )
        self.assertEqual(2, len(file_windows))
        self.assertEqual(
            [(item.samples, item.sample_start, item.sample_end, item.capture_end_monotonic_s) for item in file_windows],
            [(item.samples, item.sample_start, item.sample_end, item.capture_end_monotonic_s) for item in mic_windows],
        )
        self.assertEqual("uploaded_file", file_windows[0].input_kind)
        self.assertEqual("live_microphone", mic_windows[0].input_kind)

    def test_fake_output_is_explicitly_simulated_and_probe_uses_frozen_contract(self):
        analyzer = FakeInstrumentAnalyzer(
            [FakeEvidenceSpec(deltas_db={"guitar": 1, "bass": 0, "drums": 0})]
        )
        window = next(
            self.pipeline.iter_windows(
                MicAudioInput(
                    input_asset_or_device_id="mic-1",
                    clock_id="clock-1",
                    sample_rate_hz=10,
                    samples=self.samples[:10],
                    origin_monotonic_s=1,
                ),
                session_id="session-1",
                analysis_run_id="probe-run",
            )
        )
        config = {
            "instrument_config_version": 1,
            "instruments": [
                {"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")
            ],
        }
        context = {
            "record_type": "AnalyzerContext",
            "schema_version": "1.0",
            "observation": window.identity(),
            "model": copy.deepcopy(analyzer.MODEL),
            "instrument_config": config,
            "target": {
                "target_kind": "reference",
                "reference": {"reference_id": "reference-1", "source_asset_hash": "sha256:x"},
                "baseline": None,
            },
            "comparison_regime": "matched_excerpt",
            "model_specific_context_asset": "fake-context",
            "observation_purpose": "guided_probe",
            "probe_instrument_id": "guitar",
        }
        evidence = analyzer.analyze(window, context)
        self.assertTrue(evidence["example_only"])
        self.assertIn("simulated", evidence["model"]["model_bundle_id"])

    def test_common_gain_centers_to_normal(self):
        analyzer = FakeInstrumentAnalyzer(
            [FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 4, "drums": 4})]
        )
        window = next(
            self.pipeline.iter_windows(
                MicAudioInput(
                    input_asset_or_device_id="mic-1", clock_id="clock-1", sample_rate_hz=10,
                    samples=self.samples[:10], origin_monotonic_s=1,
                ),
                session_id="session-1", analysis_run_id="run-1",
            )
        )
        config = {"instrument_config_version": 1, "instruments": [
            {"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")
        ]}
        context = {
            "record_type": "AnalyzerContext", "schema_version": "1.0",
            "observation": window.identity(), "model": copy.deepcopy(analyzer.MODEL),
            "instrument_config": config,
            "target": {"target_kind": "reference", "reference": {
                "reference_id": "reference-1", "source_asset_hash": "sha256:x"}, "baseline": None},
            "comparison_regime": "matched_excerpt", "model_specific_context_asset": "context-1",
            "observation_purpose": "rehearsal", "probe_instrument_id": None,
        }
        evidence = analyzer.analyze(window, context)
        frame = FrameBuilder().build(
            context=context, evidence=evidence, quality=quality_state(), frame_id="frame-1", sequence=1,
            published_monotonic_s=2,
        )
        validate_record(frame, PUBLIC, "AnalysisFrame")
        self.assertEqual(4, frame["common_mode_gain_db"])
        self.assertEqual(["normal", "normal", "normal"], [item["status"] for item in frame["instruments"]])
        self.assertEqual([0, 0, 0], [item["balance_deviation_db"] for item in frame["instruments"]])

    def test_inactive_abstained_and_stale_are_never_normal_or_too_quiet(self):
        analyzer = FakeInstrumentAnalyzer(
            [FakeEvidenceSpec(deltas_db={"bass": 0, "drums": 0}, inactive=frozenset({"guitar"}))]
        )
        window = next(
            self.pipeline.iter_windows(
                MicAudioInput(
                    input_asset_or_device_id="mic-1", clock_id="clock-1", sample_rate_hz=10,
                    samples=self.samples[:10], origin_monotonic_s=1,
                ), session_id="session-1", analysis_run_id="run-1",
            )
        )
        config = {"instrument_config_version": 1, "instruments": [
            {"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")
        ]}
        context = {
            "record_type": "AnalyzerContext", "schema_version": "1.0", "observation": window.identity(),
            "model": copy.deepcopy(analyzer.MODEL), "instrument_config": config,
            "target": {"target_kind": "reference", "reference": {
                "reference_id": "reference-1", "source_asset_hash": "sha256:x"}, "baseline": None},
            "comparison_regime": "matched_excerpt", "model_specific_context_asset": "context-1",
            "observation_purpose": "rehearsal", "probe_instrument_id": None,
        }
        frame = FrameBuilder().build(
            context=context, evidence=analyzer.analyze(window, context),
            quality=quality_state(stale=True), frame_id="frame-1", sequence=1, published_monotonic_s=2,
        )
        guitar = frame["instruments"][0]
        self.assertEqual("inactive", guitar["status"])
        self.assertTrue(guitar["confidence"]["abstained"])
        self.assertIsNone(guitar["balance_deviation_db"])
        self.assertNotIn("normal", [item["status"] for item in frame["instruments"]])


if __name__ == "__main__":
    unittest.main()
