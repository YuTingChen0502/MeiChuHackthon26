"""Launcher-selected browser origins without widening the loopback allowlist."""
import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from apps.api.launch import main
from apps.api.transport import _origin_allowed


class LauncherOriginTests(unittest.TestCase):
    def launch(self, explicit=None):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            if explicit is not None:
                os.environ["PA_ALLOWED_ORIGINS"]=explicit
            async def inspect(app):
                async with app.router.lifespan_context(app):
                    return set(app.state.allowed_origins), {
                        origin:_origin_allowed(SimpleNamespace(headers={"origin":origin},app=app))
                        for origin in ("http://127.0.0.1:8094", "http://localhost:8094",
                                       "http://127.0.0.1:8000", "https://untrusted.example")}
            def run(app,**options):
                self.assertEqual(8094,options["port"])
                self.assertEqual("127.0.0.1",options["host"])
                self.result=asyncio.run(inspect(app))
            with patch("sys.argv",["launch","--mode","fake","--storage",directory,"--port","8094"]), patch("uvicorn.run",side_effect=run):
                main()
            return self.result

    def test_custom_port_defaults_allow_only_selected_loopback_origins(self):
        allowed,decisions=self.launch()
        self.assertEqual({"http://127.0.0.1:8094","http://localhost:8094"},allowed)
        self.assertEqual([True,True,False,False],list(decisions.values()))

    def test_explicit_origin_configuration_is_preserved(self):
        allowed,decisions=self.launch("http://127.0.0.1:8000")
        self.assertEqual({"http://127.0.0.1:8000"},allowed)
        self.assertEqual([False,False,True,False],list(decisions.values()))


class CandidateLauncherTests(unittest.TestCase):
    def test_explicit_candidate_uses_host_loader_and_frozen_geometry(self):
        from unittest.mock import Mock
        from pathlib import Path
        loader=Mock()
        make=Mock(return_value=loader)
        module=SimpleNamespace(make_p1_candidate_loader=make)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch.dict(
                "sys.modules", {"analyzers.separation.p1_candidate":module}):
            with patch("sys.argv",["launch","--mode","candidate-p1","--storage",directory,
                    "--bundle",directory]), patch("uvicorn.run"), patch("apps.api.transport.create_app") as app:
                main()
            make.assert_called_once_with(cache_dir=Path(directory)/"context-cache",candidate_mode=True,device="cpu")
            self.assertIs(loader,app.call_args.kwargs["bundle_loader"])
            self.assertEqual(["44100","176400","44100"],[os.environ[k] for k in
                ("PA_ANALYSIS_RATE_HZ","PA_WINDOW_SIZE_SAMPLES","PA_HOP_SIZE_SAMPLES")])
            self.assertEqual("bundle",os.environ["PA_ANALYZER_MODE"])
            self.assertNotIn("PA_HOST_REVIEW",os.environ)

    def test_candidate_rejects_wrong_geometry_or_production_review(self):
        for extra in (["--rate","48000"],["--host-review","review.json"],["--adapter","x=y:z"]):
            with patch("sys.argv",["launch","--mode","candidate-p1","--storage","unused",*extra]):
                with self.assertRaises(SystemExit) as raised:
                    main()
                self.assertEqual(2,raised.exception.code)
