"""Small compatibility checks for the newly frozen setup surface."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import ValidationError

from core.contracts.validation import SETUP, validate_record


class SetupWireTests(unittest.TestCase):
    def test_setup_payload_examples_and_invalid_instrument_types(self):
        examples = {
            "CreateProjectRequest": {"name": "Demo"},
            "ProjectResponse": {"project_id": "project-1", "name": "Demo"},
            "CreateSongRequest": {"project_id": "project-1", "name": "Song",
                                  "instruments": [{"instrument_id": "guitar", "family": "guitar"}]},
            "StartReferenceRequest": {"asset_id": "asset-1"},
            "AudioAssetResponse": {"asset_id": "asset-1", "content_hash": "sha256:example",
                                   "sample_rate_hz": 48000, "channels": 1, "duration_s": 60},
            "SetupError": {"error": {"code": "invalid_source", "message": "Unknown source.", "retryable": False}},
        }
        for name, record in examples.items():
            with self.subTest(name=name):
                validate_record(record, SETUP, name)
                validate_record(record, SETUP)
        malformed = copy.deepcopy(examples["CreateSongRequest"])
        malformed["instruments"][0]["family"] = ["guitar"]
        with self.assertRaises(ValidationError):
            validate_record(malformed, SETUP, "CreateSongRequest")

    def test_session_requires_selected_reference_and_server_owns_clock(self):
        fixtures = json.loads((Path(__file__).resolve().parents[3] /
                              "contracts/examples/pa_shared_v1.json").read_text(encoding="utf-8"))
        snapshot = fixtures["live_snapshot"]
        request = {"song_id": "song-1", "reference_id": "reference-1",
                   "source": {"input_kind": "live_microphone", "input_asset_or_device_id": "mic-1"},
                   "capture_fingerprint": snapshot["active_baseline"]["capture"]}
        validate_record(request, SETUP, "CreateSessionRequest")
        validate_record(fixtures["rehearsal_snapshot"], SETUP, "CreateSessionResponse")
        request["source"]["clock_id"] = "client-chosen-clock"
        with self.assertRaises(ValidationError):
            validate_record(request, SETUP, "CreateSessionRequest")
        del request["source"]["clock_id"]
        del request["reference_id"]
        with self.assertRaises(ValidationError):
            validate_record(request, SETUP, "CreateSessionRequest")

    def test_reference_job_completion_and_failure_are_explicit(self):
        job = {"job_id": "job-1", "kind": "reference_analysis", "status": "queued",
               "song_id": "song-1", "asset_id": "asset-1", "reference_id": "reference-1",
               "progress": 0, "error": None, "retryable": False}
        validate_record(job, SETUP, "ReferenceJob")
        job["status"] = "completed"
        with self.assertRaises(ValidationError):
            validate_record(job, SETUP, "ReferenceJob")
        job["progress"] = 1
        validate_record(job, SETUP, "ReferenceJob")
        job["status"] = "failed"
        with self.assertRaises(ValidationError):
            validate_record(job, SETUP, "ReferenceJob")
        job["error"] = "decode_failed"
        validate_record(job, SETUP, "ReferenceJob")


if __name__ == "__main__":
    unittest.main()
