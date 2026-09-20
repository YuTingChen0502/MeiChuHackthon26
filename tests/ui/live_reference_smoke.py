"""Loopback-only UI integration harness. Fake inference and injected PCM; no hardware.

Run normally for the real RuntimeAdapter HTTP/WS smoke, or --serve for browser QA.
The test-only scenario route exists solely in this harness, never in production UI/API.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/integration")]
import uvicorn
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from apps.api.service import RuntimeAPI
from apps.api.transport import create_app
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer, FakeEvidenceSpec
from core.runtime.deviation import FrameBuilder
from test_api_service import wav_bytes
from test_live_reference_runtime import Backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--hint-smoke", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    phase = {"guitar": 0, "global": 0, "trial": False, "reprepare": False}
    backend = Backend()  # Always injected; never instantiate a physical native backend.

    class ScriptedFake(ContinuousFakeInstrumentAnalyzer):
        def analyze(self, window, context):
            families = [item["instrument_id"] for item in context["instrument_config"]["instruments"]]
            self.queue(FakeEvidenceSpec(
                deltas_db={item: phase["global"] + (phase["guitar"] if item == "guitar" else 0) for item in families},
                invalid_reasons={item: "reference_context_reprepare_required" for item in families} if phase["reprepare"] else {}))
            result = super().analyze(window, context)
            if phase["trial"]:
                for item in result["measurements"]:
                    if item["validity"] == "valid":
                        item["reason_codes"] += ["uncalibrated_candidate", "family_attribution_unvalidated"]
            return result

    class TrialFrameBuilder(FrameBuilder):
        # Test-only uncalibrated confidence, while frame/evidence example_only stay
        # true. Runtime derives the hint from scripted measurements; no hint or
        # direction is injected. Ordinary Fake calibrated coverage is unchanged.
        @staticmethod
        def _confidence(**values):
            if phase["trial"]:
                values["example_only"] = False
            return FrameBuilder._confidence(**values)

    with tempfile.TemporaryDirectory(prefix="harmonix-ui-live-reference-") as directory:
        reference = wav_bytes([.1] * (48000 * (120 if args.serve else 25)), sample_rate=48000)
        reference_path = Path(directory) / "synthetic-reference.wav"
        reference_path.write_bytes(reference)
        api = RuntimeAPI(storage_dir=directory, native_backend=backend, managed_audio=True,
                         analyzer_factory=ScriptedFake, analysis_sample_rate_hz=48000,
                         window_size_samples=9600, hop_size_samples=9600)
        api.live_audio.startup_timeout_s = 1
        if not args.port:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                args.port = probe.getsockname()[1]
        base = f"http://127.0.0.1:{args.port}"
        os.environ['PA_ALLOWED_ORIGINS'] = base
        app = create_app(api)

        async def scenario(request):
            value = await request.json()
            phase["guitar"] = float(value.get("guitar", phase["guitar"]))
            for key in ("global", "trial", "reprepare"):
                if key in value:
                    phase[key] = value[key]
            for session in api.sessions.values():
                previous = session._frame_builder
                session._frame_builder = TrialFrameBuilder(
                    anomaly_threshold_db=previous.anomaly_threshold_db,
                    calibration_policy=previous.calibration_policy)
            backend.fail = set(value.get("fail", []))
            backend.silent = set(value.get("silent", []))
            return JSONResponse({"example_only": True, "phase": phase, "physical": False})

        async def audio(request):
            return Response(reference, media_type="audio/wav")

        app.router.routes.insert(0, Route("/__ui_test/scenario", scenario, methods=["POST"]))
        app.router.routes.insert(0, Route("/__ui_test/reference.wav", audio))
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port,
            loop="asyncio", http="h11", ws="websockets-sansio", log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(.02)
            assert server.started
            print(json.dumps({"base": base, "reference_path": str(reference_path),
                              "scope": "Fake + injected PCM only; no hardware"}), flush=True)
            if args.serve:
                while thread.is_alive():
                    thread.join(.5)
            else:
                script = "tests/ui/perception-hint-smoke.mjs" if args.hint_smoke else "tests/ui/live-reference-smoke.mjs"
                result = subprocess.run(["node", script], cwd=ROOT,
                    env={**os.environ, "SMOKE_BASE": base}, timeout=45)
                if result.returncode:
                    raise SystemExit(result.returncode)
        finally:
            server.should_exit = True
            thread.join(5)
            api.close()


if __name__ == "__main__":
    main()
