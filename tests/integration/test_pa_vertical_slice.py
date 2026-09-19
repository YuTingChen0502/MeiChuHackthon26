import copy
import tempfile
import unittest
from pathlib import Path

from apps.api.commands import CommandHandler, JsonCommandLedger
from core.audio import FileAudioInput, MicAudioInput, SharedAudioPipeline
from core.contracts.validation import (
    baseline_binding,
    event_binding,
    reference_binding,
    validate_event,
    validate_response,
    validate_snapshot,
)
from core.profiles import BaselineStore, ReferenceBuilder
from core.runtime import FakeEvidenceSpec, FakeInstrumentAnalyzer
from core.runtime.quality import quality_state
from roles.pa import PASession


class ManualClock:
    def __init__(self, value=1.0):
        self.value = value

    def __call__(self):
        return self.value


def command(snapshot, key, action, payload=None):
    return {
        "record_type": "SessionCommand",
        "schema_version": "1.0",
        "session_id": snapshot["session_id"],
        "idempotency_key": key,
        "expected_state_version": snapshot["state_version"],
        "reference": reference_binding(snapshot["active_reference"]),
        "baseline": baseline_binding(snapshot["active_baseline"]),
        "event": event_binding(snapshot["incident"]),
        "action": action,
        "payload": {} if payload is None else payload,
    }


class PAVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.clock = ManualClock()
        self.pipeline = SharedAudioPipeline(window_size_samples=10, hop_size_samples=10)
        self.config = {
            "instrument_config_version": 1,
            "instruments": [
                {"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")
            ],
        }
        self.analyzer = FakeInstrumentAnalyzer()
        reference_input = FileAudioInput(
            input_asset_or_device_id="uploaded-reference-asset",
            clock_id="reference-clock",
            sample_rate_hz=10,
            samples=[0.05] * 20,
            origin_monotonic_s=0,
        )
        self.reference = ReferenceBuilder(pipeline=self.pipeline, analyzer=self.analyzer).build(
            audio_input=reference_input,
            session_id="reference-preparation",
            analysis_run_id="reference-run",
            reference_id="reference-1",
            song_id="song-1",
            instrument_config=self.config,
        )
        self.baselines = BaselineStore()
        self.session = PASession(
            session_id="session-1",
            project_id="project-1",
            song_id="song-1",
            song_name="Checkpoint song",
            instrument_config=self.config,
            reference_profile=self.reference,
            source={"input_kind": "live_microphone", "input_asset_or_device_id": "mic-1", "clock_id": "clock-1"},
            capture_fingerprint={
                "device_id": "mic-1", "profile_id": "capture-fixed-v1", "native_sample_rate_hz": 10,
                "channels": 1, "gain_setting": "fixed", "enhancements_verified_disabled": True,
                "geometry_id": "demo-geometry", "provenance": "physical_verified",
            },
            analyzer=self.analyzer,
            baseline_store=self.baselines,
            monotonic_clock=self.clock,
            wall_clock=lambda: "2026-09-19T12:00:00+08:00",
            settling_policy_s=0.5,
            persistence_frames=2,
            event_retention=8,
        )
        self.ledger_path = Path(self.temporary.name) / "command-ledger.json"
        self.handler = CommandHandler(session=self.session, ledger=JsonCommandLedger(self.ledger_path))

    def tearDown(self):
        self.temporary.cleanup()

    def window(self, run_id, start_time):
        audio_input = MicAudioInput(
            input_asset_or_device_id="mic-1", clock_id="clock-1", sample_rate_hz=10,
            samples=[0.1] * 10, origin_monotonic_s=start_time,
        )
        return next(self.pipeline.iter_windows(audio_input, session_id="session-1", analysis_run_id=run_id))

    def apply(self, key, action, payload=None):
        response = self.handler.handle(command(self.session.snapshot(), key, action, payload))
        validate_response(response)
        self.assertEqual(200, response["http_status"], response.get("error"))
        return response

    def open_persistent_incident(self, prefix, start_time):
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 0, "drums": 0}),
            FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 0, "drums": 0}),
        )
        self.session.observe_window(self.window(f"{prefix}-1", start_time))
        self.assertIsNone(self.session.snapshot()["incident"])
        self.session.observe_window(self.window(f"{prefix}-2", start_time + 1))
        snapshot = self.session.snapshot()
        self.assertEqual("active", snapshot["incident_state"])
        self.assertEqual("too_loud", snapshot["incident"]["event"]["direction"])
        self.assertEqual("reduce_level", snapshot["recommendations"][0]["action"])
        self.assertEqual(-2, snapshot["recommendations"][0]["suggested_step_db"])

    def adjust_recheck_and_recover(self, prefix, corrected_start):
        self.apply(f"{prefix}-start-adjust", "start_adjustment")
        self.clock.value = corrected_start - 1.0
        completed = self.apply(
            f"{prefix}-complete-adjust",
            "complete_adjustment",
            {"adjustment_id": self.session.snapshot()["adjustment"]["adjustment_id"]},
        )
        adjustment_id = completed["snapshot"]["adjustment"]["adjustment_id"]
        cutoff = completed["snapshot"]["adjustment"]["verification_not_before_monotonic_s"]
        self.apply(f"{prefix}-recheck", "recheck", {"adjustment_id": adjustment_id})
        self.analyzer.queue(FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}))
        corrected = self.window(f"{prefix}-corrected", corrected_start)
        self.session.observe_window(corrected)
        snapshot = self.session.snapshot()
        self.assertEqual("recovered", snapshot["latest_verification"]["outcome"])
        self.assertGreaterEqual(
            snapshot["latest_verification"]["first_evidence_sample_start_monotonic_s"],
            cutoff,
        )
        return corrected, snapshot

    def test_complete_reference_rehearsal_baseline_live_verification_loop(self):
        self.assertIn("simulated", self.reference["model_bundle_id"])
        self.assertEqual("REHEARSAL", self.session.snapshot()["song"]["workflow_state"])

        self.open_persistent_incident("rehearsal", 2)
        corrected_window, recovered = self.adjust_recheck_and_recover("rehearsal", 12)
        self.assertEqual("REHEARSAL", recovered["song"]["workflow_state"])

        interval = {
            "analysis_run_id": corrected_window.analysis_run_id,
            "clock_id": corrected_window.clock_id,
            "sample_rate_hz": corrected_window.sample_rate_hz,
            "sample_start": corrected_window.sample_start,
            "sample_end": corrected_window.sample_end,
        }
        accept = command(
            self.session.snapshot(), "accept-1", "accept_baseline",
            {"interval": interval, "accepted_by": "human-pa", "reference_difference_accepted": True,
             "acceptance_note": "Human approved after a fresh rehearsal recheck."},
        )
        accepted = self.handler.handle(accept)
        self.assertEqual(200, accepted["http_status"])
        self.assertEqual("rehearsal", accepted["snapshot"]["session_mode"])
        self.assertTrue(accepted["snapshot"]["active_baseline"]["immutable"])
        self.assertEqual(1, self.baselines.count())

        # Retry is resolved from the durable ledger before its now-stale state binding.
        restarted_handler = CommandHandler(session=self.session, ledger=JsonCommandLedger(self.ledger_path))
        retried = restarted_handler.handle(accept)
        self.assertEqual(accepted, retried)
        self.assertEqual(1, self.baselines.count())

        stored_before_live = copy.deepcopy(self.session.snapshot()["active_baseline"])
        self.apply("start-live", "start_live")
        self.assertEqual("live", self.session.snapshot()["session_mode"])
        self.assertEqual("LIVE_MONITORING", self.session.snapshot()["song"]["workflow_state"])

        self.open_persistent_incident("live", 20)
        self.adjust_recheck_and_recover("live", 32)
        final = self.session.snapshot()
        self.assertEqual("LIVE_MONITORING", final["song"]["workflow_state"])
        self.assertEqual("recovered", final["latest_verification"]["outcome"])
        self.assertEqual(stored_before_live["baseline_id"], final["latest_frame"]["baseline_id"])
        self.assertEqual(stored_before_live["version"], final["latest_frame"]["baseline_version"])
        self.assertEqual(stored_before_live, final["active_baseline"])

        immutable_attempt = command(
            final, "accept-live", "accept_baseline",
            {"interval": interval, "accepted_by": "human-pa", "reference_difference_accepted": True,
             "acceptance_note": "must fail"},
        )
        rejected = self.handler.handle(immutable_attempt)
        self.assertEqual(409, rejected["http_status"])
        self.assertEqual("baseline_immutable_live", rejected["error"]["code"])
        self.assertEqual(stored_before_live, self.session.snapshot()["active_baseline"])

        prior_event_id = final["incident"]["event"]["event_id"]
        self.open_persistent_incident("live-second", 40)
        second = self.session.snapshot()
        self.assertNotEqual(prior_event_id, second["incident"]["event"]["event_id"])
        self.assertEqual("active", second["incident_state"])
        self.assertEqual(1, len(second["recommendations"]))
        audited_event_ids = [
            record["payload"]["event"]["event_id"]
            for record in self.session.audit_records()
            if record["kind"] in ("incident_opened", "incident_revised")
        ]
        self.assertIn(prior_event_id, audited_event_ids)
        self.assertIn(second["incident"]["event"]["event_id"], audited_event_ids)

    def test_stale_command_and_incompatible_profile_are_rejected(self):
        stale = command(self.session.snapshot(), "stale-command", "pause")
        self.analyzer.queue(FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}))
        self.session.observe_window(self.window("ordinary-frame", 2))
        # Ordinary frame publication does not invalidate commands by incrementing state_version.
        self.assertEqual(200, self.handler.handle(stale)["http_status"])

        older = command(self.session.snapshot(), "old-version", "resume")
        self.apply("stop-for-version-change", "stop")
        rejected = self.handler.handle(older)
        self.assertEqual(409, rejected["http_status"])
        self.assertEqual("stale_or_invalid_binding", rejected["error"]["code"])

    def test_model_profile_mismatch_blocks_live(self):
        self.analyzer.queue(FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}))
        accepted_window = self.window("baseline-source", 2)
        self.session.observe_window(accepted_window)
        interval = {
            "analysis_run_id": accepted_window.analysis_run_id, "clock_id": accepted_window.clock_id,
            "sample_rate_hz": accepted_window.sample_rate_hz,
            "sample_start": accepted_window.sample_start, "sample_end": accepted_window.sample_end,
        }
        self.apply(
            "accept-for-mismatch", "accept_baseline",
            {"interval": interval, "accepted_by": "human-pa", "reference_difference_accepted": True,
             "acceptance_note": "test baseline"},
        )
        self.session.execution["model_bundle_id"] = "different-model-bundle"
        rejected = self.handler.handle(command(self.session.snapshot(), "live-mismatch", "start_live"))
        self.assertEqual(409, rejected["http_status"])
        self.assertEqual("incompatible_profile", rejected["error"]["code"])
        self.assertEqual("rehearsal", self.session.snapshot()["session_mode"])

    def test_stale_evidence_cannot_create_incident(self):
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 6, "bass": 0, "drums": 0}),
            FakeEvidenceSpec(deltas_db={"guitar": 6, "bass": 0, "drums": 0}),
        )
        self.session.observe_window(self.window("stale-1", 2), quality=quality_state(stale=True))
        self.session.observe_window(self.window("stale-2", 3), quality=quality_state(stale=True))
        snapshot = self.session.snapshot()
        self.assertIsNone(snapshot["incident"])
        self.assertTrue(snapshot["latest_frame"]["instruments"][0]["confidence"]["abstained"])
        self.assertEqual("unknown", snapshot["latest_frame"]["instruments"][0]["status"])

    def test_capture_gap_resets_pending_incident_persistence(self):
        anomaly = FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 0, "drums": 0})
        self.analyzer.queue(anomaly, anomaly, anomaly, anomaly)
        self.session.observe_window(self.window("before-gap", 2))
        self.session.observe_window(self.window("gap", 3), quality=quality_state(dropout=True))
        self.session.observe_window(self.window("after-gap-1", 4))
        self.assertIsNone(self.session.snapshot()["incident"])
        self.session.observe_window(self.window("after-gap-2", 5))
        self.assertEqual("active", self.session.snapshot()["incident_state"])

    def test_pause_suppresses_incidents_and_recommendations(self):
        self.apply("pause", "pause")
        anomaly = FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 0, "drums": 0})
        self.analyzer.queue(anomaly, anomaly)
        self.session.observe_window(self.window("paused-1", 2))
        self.session.observe_window(self.window("paused-2", 3))
        snapshot = self.session.snapshot()
        self.assertEqual("SUSPENDED", snapshot["song"]["workflow_state"])
        self.assertIsNone(snapshot["incident"])
        self.assertEqual([], snapshot["recommendations"])

        rejected = self.handler.handle(
            command(snapshot, "paused-recheck", "recheck", {"adjustment_id": None})
        )
        self.assertEqual(409, rejected["http_status"])
        self.assertEqual("session_suspended", rejected["error"]["code"])
        self.assertEqual("SUSPENDED", rejected["snapshot"]["song"]["workflow_state"])
        self.assertEqual(["operator_paused"], rejected["snapshot"]["suspension_reasons"])

    def test_pause_disarms_verification_and_keeps_audio_diagnostic_only(self):
        self.open_persistent_incident("pause-verification", 2)
        self.apply("pause-verification-start", "start_adjustment")
        self.clock.value = 10
        adjustment_id = self.session.snapshot()["adjustment"]["adjustment_id"]
        self.apply(
            "pause-verification-complete",
            "complete_adjustment",
            {"adjustment_id": adjustment_id},
        )
        self.apply(
            "pause-verification-recheck", "recheck", {"adjustment_id": adjustment_id}
        )
        self.apply("pause-during-verification", "pause")
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0})
        )
        self.session.observe_window(self.window("paused-corrected", 12))
        snapshot = self.session.snapshot()
        self.assertEqual("SUSPENDED", snapshot["song"]["workflow_state"])
        self.assertIsNone(snapshot["latest_verification"])
        self.assertFalse(self.session.export_state()["verification_armed"])

    def test_rejected_command_preserves_pending_detector_streak(self):
        anomaly = FakeEvidenceSpec(deltas_db={"guitar": 4, "bass": 0, "drums": 0})
        self.analyzer.queue(anomaly, anomaly)
        self.session.observe_window(self.window("pending-before-rejection", 2))
        rejected = self.handler.handle(
            command(self.session.snapshot(), "invalid-resume", "resume")
        )
        self.assertEqual(409, rejected["http_status"])
        self.session.observe_window(self.window("pending-after-rejection", 3))
        self.assertEqual("active", self.session.snapshot()["incident_state"])

    def test_failed_observation_persistence_restores_session_state(self):
        before = self.session.export_state()

        def fail_persistence(_state):
            raise OSError("simulated observation persistence failure")

        self.session.set_persistence_callback(fail_persistence)
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0})
        )
        try:
            with self.assertRaises(OSError):
                self.session.observe_window(self.window("failed-observation", 2))
        finally:
            self.session.set_persistence_callback(None)
        self.assertEqual(before, self.session.export_state())

    def test_unresolved_adjustment_blocks_baseline_and_live_promotion(self):
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0})
        )
        accepted_window = self.window("unresolved-baseline", 2)
        self.session.observe_window(accepted_window)
        interval = {
            "analysis_run_id": accepted_window.analysis_run_id,
            "clock_id": accepted_window.clock_id,
            "sample_rate_hz": accepted_window.sample_rate_hz,
            "sample_start": accepted_window.sample_start,
            "sample_end": accepted_window.sample_end,
        }
        self.apply(
            "unresolved-accept-first",
            "accept_baseline",
            {
                "interval": interval,
                "accepted_by": "human-pa",
                "reference_difference_accepted": True,
                "acceptance_note": "initial baseline",
            },
        )
        self.apply("unresolved-start-adjustment", "start_adjustment")
        for key, action, payload in (
            (
                "unresolved-accept-again",
                "accept_baseline",
                {
                    "interval": interval,
                    "accepted_by": "human-pa",
                    "reference_difference_accepted": True,
                    "acceptance_note": "must not replace during adjustment",
                },
            ),
            ("unresolved-start-live", "start_live", {}),
        ):
            rejected = self.handler.handle(
                command(self.session.snapshot(), key, action, payload)
            )
            self.assertEqual(409, rejected["http_status"])
            self.assertEqual("unresolved_adjustment", rejected["error"]["code"])

    def test_stopped_session_rejects_fresh_commands(self):
        self.apply("stop", "stop")
        stopped = self.session.snapshot()
        response = self.handler.handle(command(stopped, "recheck-after-stop", "recheck", {"adjustment_id": None}))
        self.assertEqual(409, response["http_status"])
        self.assertEqual("session_stopped", response["error"]["code"])
        self.assertEqual("STOPPED", self.session.snapshot()["song"]["workflow_state"])

    def test_silence_or_disconnection_is_inconclusive_not_recovered(self):
        self.open_persistent_incident("silence", 2)
        self.apply("silence-start", "start_adjustment")
        self.clock.value = 10
        adjustment_id = self.session.snapshot()["adjustment"]["adjustment_id"]
        self.apply("silence-complete", "complete_adjustment", {"adjustment_id": adjustment_id})
        self.apply("silence-recheck", "recheck", {"adjustment_id": adjustment_id})
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"bass": 0, "drums": 0}, inactive=frozenset({"guitar"}))
        )
        self.session.observe_window(self.window("silence-after", 12), quality=quality_state(dropout=True))
        snapshot = self.session.snapshot()
        self.assertEqual("inconclusive", snapshot["latest_verification"]["outcome"])
        self.assertFalse(snapshot["latest_verification"]["source_observable"])
        self.assertIsNotNone(snapshot["incident"])
        self.assertNotEqual("resolved", snapshot["incident"]["event"]["state"])

    def test_partial_verification_permits_another_human_correction(self):
        self.open_persistent_incident("partial", 2)
        self.apply("partial-start", "start_adjustment")
        self.clock.value = 10
        adjustment_id = self.session.snapshot()["adjustment"]["adjustment_id"]
        self.apply("partial-complete", "complete_adjustment", {"adjustment_id": adjustment_id})
        self.apply("partial-recheck", "recheck", {"adjustment_id": adjustment_id})
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 3, "bass": 0, "drums": 0})
        )
        self.session.observe_window(self.window("partial-after", 12))
        snapshot = self.session.snapshot()
        self.assertEqual("partial", snapshot["latest_verification"]["outcome"])
        self.assertEqual("active", snapshot["incident_state"])
        self.assertIsNone(snapshot["adjustment"])

        second = self.apply("partial-second-start", "start_adjustment")["snapshot"]
        self.assertEqual("adjusting", second["incident_state"])
        self.assertNotEqual(adjustment_id, second["adjustment"]["adjustment_id"])

    def test_reconnect_gap_returns_authoritative_snapshot_event(self):
        self.session.event_retention = 2
        self.analyzer.queue(
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}),
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}),
            FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}),
        )
        for index in range(3):
            self.session.observe_window(self.window(f"normal-{index}", 2 + index))
        events = self.session.events_after(0)
        self.assertEqual(1, len(events))
        validate_event(events[0])
        self.assertEqual("SessionSnapshot", events[0]["payload"]["record_type"])
        self.assertEqual(events[0]["event_sequence"], events[0]["payload"]["event_sequence"])
        validate_snapshot(events[0]["payload"])


if __name__ == "__main__":
    unittest.main()
