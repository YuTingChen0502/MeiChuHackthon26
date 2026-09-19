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
