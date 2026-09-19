import io
import tempfile
import unittest
import wave

from apps.api import RuntimeAPI
from core.audio import MicAudioInput
from core.contracts.validation import baseline_binding, event_binding, reference_binding, validate_event
from core.runtime import FakeEvidenceSpec


class Clock:
    def __init__(self):
        self.value = 1.0

    def __call__(self):
        return self.value


def wav_bytes(samples, sample_rate=10):
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        payload = b"".join(int(value * 32767).to_bytes(2, "little", signed=True) for value in samples)
        writer.writeframes(payload)
    return output.getvalue()


def command(snapshot, key, action, payload=None):
    return {
        "record_type": "SessionCommand", "schema_version": "1.0",
        "session_id": snapshot["session_id"], "idempotency_key": key,
        "expected_state_version": snapshot["state_version"],
        "reference": reference_binding(snapshot["active_reference"]),
        "baseline": baseline_binding(snapshot["active_baseline"]),
        "event": event_binding(snapshot["incident"]),
        "action": action, "payload": {} if payload is None else payload,
    }


class RuntimeAPIServiceTests(unittest.TestCase):
    def test_setup_upload_job_commands_and_reconnect_facade(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock()
            api = RuntimeAPI(
                storage_dir=directory,
                window_size_samples=10,
                monotonic_clock=clock,
                wall_clock=lambda: "2026-09-19T12:00:00+08:00",
            )
            status, project = api.create_project({"name": "Demo project"})
            self.assertEqual(201, status)
            status, song = api.create_song({
                "project_id": project["project_id"], "name": "Demo song",
                "instruments": [{"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")],
            })
            self.assertEqual(201, status)
            status, asset = api.upload_audio(wav_bytes([0.1] * 20), filename="reference.wav")
            self.assertEqual(201, status)
            status, job = api.start_reference_job(song["song_id"], {"asset_id": asset["asset_id"]})
            self.assertEqual(202, status)
            status, job = api.run_reference_job(job["job_id"])
            self.assertEqual("completed", job["status"])

            status, snapshot = api.create_session({
                "song_id": song["song_id"],
                "source": {"input_kind": "live_microphone", "input_asset_or_device_id": "mic-1", "clock_id": "clock-1"},
                "capture_fingerprint": {
                    "device_id": "mic-1", "profile_id": "fixed-v1", "native_sample_rate_hz": 10,
                    "channels": 1, "gain_setting": "fixed", "enhancements_verified_disabled": True,
                    "geometry_id": "demo", "provenance": "physical_verified",
                },
            })
            self.assertEqual(201, status)
            session_id = snapshot["session_id"]
            runtime = api.runtime_session(session_id)

            # Proactive human adjustment and recheck use server time and fresh audio,
            # but do not fabricate an anomaly or VerificationResult.
            status, response = api.post_action(session_id, command(snapshot, "adjust-start", "start_adjustment"))
            self.assertEqual(200, status)
            clock.value = 10
            snapshot = response["snapshot"]
            adjustment_id = snapshot["adjustment"]["adjustment_id"]
            status, response = api.post_action(
                session_id, command(snapshot, "adjust-complete", "complete_adjustment", {"adjustment_id": adjustment_id})
            )
            snapshot = response["snapshot"]
            status, response = api.post_action(
                session_id, command(snapshot, "adjust-recheck", "recheck", {"adjustment_id": adjustment_id})
            )
            runtime.analyzer.queue(FakeEvidenceSpec(deltas_db={"guitar": 0, "bass": 0, "drums": 0}))
            audio_input = MicAudioInput(
                input_asset_or_device_id="mic-1", clock_id="clock-1", sample_rate_hz=10,
                samples=[0.1] * 10, origin_monotonic_s=12,
            )
            window = next(api.pipeline.iter_windows(audio_input, session_id=session_id, analysis_run_id="accepted-run"))
            runtime.observe_window(window)
            snapshot = runtime.snapshot()
            self.assertIsNone(snapshot["adjustment"])
            self.assertIsNone(snapshot["latest_verification"])

            accept = command(snapshot, "accept", "accept_baseline", {
                "interval": {"analysis_run_id": "accepted-run", "clock_id": "clock-1", "sample_rate_hz": 10,
                             "sample_start": 0, "sample_end": 10},
                "accepted_by": "human-pa", "reference_difference_accepted": True,
                "acceptance_note": "approved in API integration test",
            })
            status, response = api.accept_baseline(session_id, accept)
            self.assertEqual(200, status)
            self.assertTrue(response["snapshot"]["active_baseline"]["immutable"])
            accept_response = response

            status, connected = api.connect_events(session_id)
            self.assertEqual(200, status)
            cursor = connected["cursor"]
            status, response = api.post_action(
                session_id, command(response["snapshot"], "start-live", "start_live")
            )
            status, resumed = api.connect_events(session_id, after_sequence=cursor)
            self.assertGreaterEqual(len(resumed["events"]), 1)
            for event in resumed["events"]:
                validate_event(event)

            restarted = RuntimeAPI(
                storage_dir=directory,
                window_size_samples=10,
                monotonic_clock=clock,
                wall_clock=lambda: "2026-09-19T12:00:00+08:00",
            )
            status, restored = restarted.get_session(session_id)
            self.assertEqual(200, status)
            self.assertEqual("SUSPENDED", restored["song"]["workflow_state"])
            self.assertIn("runtime_restart_requires_new_session", restored["suspension_reasons"])
            self.assertTrue(restored["active_baseline"]["immutable"])

            # A completed command retry survives a new RuntimeAPI instance and is
            # returned before the restored session's newer restart-suspension state.
            status, retried = restarted.accept_baseline(session_id, accept)
            self.assertEqual(200, status)
            self.assertEqual(accept_response, retried)

            status, resume = restarted.post_action(
                session_id, command(restored, "resume-after-restart", "resume")
            )
            self.assertEqual(409, status)
            self.assertEqual("new_session_required", resume["error"]["code"])

            status, new_session = restarted.create_session({
                "song_id": song["song_id"],
                "source": {"input_kind": "live_microphone", "input_asset_or_device_id": "mic-2", "clock_id": "clock-2"},
                "capture_fingerprint": {
                    "device_id": "mic-2", "profile_id": "fixed-v1", "native_sample_rate_hz": 10,
                    "channels": 1, "gain_setting": "fixed", "enhancements_verified_disabled": True,
                    "geometry_id": "demo", "provenance": "physical_verified",
                },
            })
            self.assertEqual(201, status)
            self.assertEqual("session-2", new_session["session_id"])


if __name__ == "__main__":
    unittest.main()
