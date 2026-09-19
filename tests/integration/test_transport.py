import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from apps.api.service import RuntimeAPI
from apps.api.transport import create_app
from core.contracts.validation import baseline_binding, event_binding, reference_binding, validate_event

from test_api_service import wav_bytes


def session_command(snapshot, key, action, payload=None):
    return {
        "record_type": "SessionCommand", "schema_version": "1.0",
        "session_id": snapshot["session_id"], "idempotency_key": key,
        "expected_state_version": snapshot["state_version"],
        "reference": reference_binding(snapshot["active_reference"]),
        "baseline": baseline_binding(snapshot["active_baseline"]),
        "event": event_binding(snapshot["incident"]),
        "action": action, "payload": {} if payload is None else payload,
    }


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        runtime = RuntimeAPI(
            storage_dir=self.temporary.name,
            window_size_samples=10,
            available_audio_devices={"mic-1"},
            max_upload_bytes=256,
        )
        self.runtime = runtime
        self.ui_directory = Path(self.temporary.name) / "ui"
        self.ui_directory.mkdir()
        (self.ui_directory / "index.html").write_text(
            "<!doctype html><title>PA UI</title>", encoding="utf-8"
        )
        application = create_app(runtime, ui_directory=self.ui_directory)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        config = uvicorn.Config(
            application,
            host="127.0.0.1",
            port=self.port,
            workers=1,
            loop="asyncio",
            http="h11",
            ws="websockets-sansio",
            lifespan="on",
            log_level="error",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 5
        while not self.server.started and time.time() < deadline:
            time.sleep(0.02)
        if not self.server.started:
            self.fail("Uvicorn did not start")
        self.base = f"http://127.0.0.1:{self.port}"
        self.origin = "http://127.0.0.1:8000"

    def tearDown(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def request(self, method, path, *, json_body=None, body=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault("Origin", self.origin)
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            finally:
                exc.close()

    def setup_session(self):
        _, project = self.request("POST", "/v1/projects", json_body={"name": "Transport"})
        _, song = self.request("POST", "/v1/songs", json_body={
            "project_id": project["project_id"], "name": "Song",
            "instruments": [{"instrument_id": name, "family": name} for name in ("guitar", "bass", "drums")],
        })
        _, asset = self.request(
            "POST", "/v1/audio-assets", body=wav_bytes([0.1] * 20),
            headers={"Content-Type": "audio/wav", "X-Audio-Filename": "reference.wav"},
        )
        status, job = self.request(
            "POST", f"/v1/songs/{song['song_id']}/reference", json_body={"asset_id": asset["asset_id"]}
        )
        self.assertEqual(202, status)
        deadline = time.time() + 5
        while job["status"] not in ("completed", "failed") and time.time() < deadline:
            time.sleep(0.03)
            _, job = self.request("GET", f"/v1/jobs/{job['job_id']}")
        self.assertEqual("completed", job["status"])
        status, snapshot = self.request("POST", "/v1/sessions", json_body={
            "song_id": song["song_id"], "reference_id": job["reference_id"],
            "source": {"input_kind": "live_microphone", "input_asset_or_device_id": "mic-1"},
            "capture_fingerprint": {
                "device_id": "mic-1", "profile_id": "fixed-v1", "native_sample_rate_hz": 10,
                "channels": 1, "gain_setting": "fixed", "enhancements_verified_disabled": True,
                "geometry_id": "demo", "provenance": "physical_verified",
            },
        })
        self.assertEqual(201, status)
        self.assertTrue(snapshot["source"]["clock_id"].startswith("clock-"))
        return snapshot

    def test_http_setup_errors_and_async_reference_job(self):
        status, error = self.request("POST", "/v1/projects", body=b"{bad", headers={"Content-Type": "application/json"})
        self.assertEqual(422, status)
        self.assertEqual("malformed_json", error["error"]["code"])

        status, error = self.request(
            "POST", "/v1/projects", json_body={"name": "Blocked"},
            headers={"Origin": "http://evil.invalid"},
        )
        self.assertEqual(403, status)
        self.assertEqual("origin_forbidden", error["error"]["code"])
        self.setup_session()

    def test_websocket_replays_individual_events_and_stays_subscribed(self):
        snapshot = self.setup_session()
        uri = (
            f"ws://127.0.0.1:{self.port}/v1/sessions/{snapshot['session_id']}/events"
            f"?after_sequence={snapshot['event_sequence']}"
        )
        with connect(uri, origin=self.origin, open_timeout=5) as websocket:
            status, response = self.request(
                "POST", f"/v1/sessions/{snapshot['session_id']}/actions",
                json_body=session_command(snapshot, "pause-through-http", "pause"),
            )
            self.assertEqual(200, status)
            event = json.loads(websocket.recv(timeout=5))
            validate_event(event)
            self.assertEqual("SessionEvent", event["record_type"])
            self.assertEqual("SessionSnapshot", event["payload"]["record_type"])
            self.assertEqual(response["snapshot"]["state_version"], event["state_version"])
            self.assertNotIn("events", event)

    def test_command_conflicts_route_binding_and_invalid_websocket_cursors(self):
        snapshot = self.setup_session()
        path = f"/v1/sessions/{snapshot['session_id']}/actions"
        first = session_command(snapshot, "shared-key", "pause")
        status, response = self.request("POST", path, json_body=first)
        self.assertEqual(200, status)

        conflict = session_command(snapshot, "shared-key", "stop")
        status, response = self.request("POST", path, json_body=conflict)
        self.assertEqual(409, status)
        self.assertEqual("idempotency_conflict", response["error"]["code"])

        stale = session_command(snapshot, "stale-key", "stop")
        status, response = self.request("POST", path, json_body=stale)
        self.assertEqual(409, status)
        self.assertEqual("stale_or_invalid_binding", response["error"]["code"])

        status, response = self.request(
            "POST", f"/v1/sessions/{snapshot['session_id']}/baseline",
            json_body=session_command(response["snapshot"], "wrong-route", "pause"),
        )
        self.assertEqual(422, status)
        self.assertEqual("wrong_endpoint", response["error"]["code"])

        for cursor in (-1, response.get("snapshot", snapshot)["event_sequence"] + 100):
            uri = (
                f"ws://127.0.0.1:{self.port}/v1/sessions/{snapshot['session_id']}/events"
                f"?after_sequence={cursor}"
            )
            with self.assertRaises(InvalidStatus):
                connect(uri, origin=self.origin, open_timeout=5)

    def test_reference_worker_failure_is_pollable(self):
        _, project = self.request("POST", "/v1/projects", json_body={"name": "Failure"})
        _, song = self.request("POST", "/v1/songs", json_body={
            "project_id": project["project_id"], "name": "Too short",
            "instruments": [
                {"instrument_id": name, "family": name}
                for name in ("guitar", "bass", "drums")
            ],
        })
        _, asset = self.request(
            "POST", "/v1/audio-assets", body=wav_bytes([0.1] * 5),
            headers={"Content-Type": "audio/wav"},
        )
        status, job = self.request(
            "POST", f"/v1/songs/{song['song_id']}/reference",
            json_body={"asset_id": asset["asset_id"]},
        )
        self.assertEqual(202, status)
        deadline = time.time() + 5
        while job["status"] not in ("completed", "failed") and time.time() < deadline:
            time.sleep(0.03)
            _, job = self.request("GET", f"/v1/jobs/{job['job_id']}")
        self.assertEqual("failed", job["status"])
        self.assertIsNotNone(job["error"])

    def test_chunked_upload_is_bounded_and_same_origin_ui_is_served(self):
        with urllib.request.urlopen(self.base + "/apps/ui/", timeout=5) as response:
            self.assertEqual(200, response.status)
            self.assertIn(b"PA UI", response.read())

        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(
                "POST",
                "/v1/audio-assets",
                body=iter((b"x" * 200, b"y" * 100)),
                headers={"Content-Type": "audio/wav", "Origin": self.origin},
                encode_chunked=True,
            )
            response = connection.getresponse()
            payload = json.loads(response.read())
        finally:
            connection.close()
        self.assertEqual(413, response.status)
        self.assertEqual("audio_too_large", payload["error"]["code"])

    def test_idle_websocket_disconnect_stops_subscription_polling(self):
        snapshot = self.setup_session()
        original = self.runtime.connect_events
        calls = []
        calls_lock = threading.Lock()

        def counted(*args, **kwargs):
            with calls_lock:
                calls.append(time.monotonic())
            return original(*args, **kwargs)

        self.runtime.connect_events = counted
        uri = (
            f"ws://127.0.0.1:{self.port}/v1/sessions/{snapshot['session_id']}/events"
            f"?after_sequence={snapshot['event_sequence']}"
        )
        with connect(uri, origin=self.origin, open_timeout=5):
            time.sleep(0.12)
        time.sleep(0.15)
        with calls_lock:
            settled_count = len(calls)
        time.sleep(0.15)
        with calls_lock:
            self.assertEqual(settled_count, len(calls))


if __name__ == "__main__":
    unittest.main()
