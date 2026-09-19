"""Additive native discovery labels without guessed physical-device merging."""
import tempfile
import unittest
from types import SimpleNamespace
from apps.api.service import RuntimeAPI
from core.audio.native import SoundDeviceBackend


class Module:
    def __init__(self, default=0):
        self.default=SimpleNamespace(device=[default,2])
    def query_hostapis(self):
        return [{"name":"MME"},{"name":"WASAPI"}]
    def query_devices(self):
        return [dict(name=name,hostapi=host,max_input_channels=inputs,default_samplerate=48000)
            for name,host,inputs in (("Desk microphone",0,1),("Desk microphone",1,2),
                                     ("Speakers",1,0),("Stereo Mix",1,2))]


class DeviceMetadataTests(unittest.TestCase):
    def discover(self, backend):
        with tempfile.TemporaryDirectory() as directory:
            api=RuntimeAPI(storage_dir=directory,window_size_samples=192000,native_backend=backend,managed_audio=True)
            try:return api.audio_devices()[1]
            finally:api.close()

    def test_labels_default_and_cross_host_names_preserve_distinct_ids(self):
        backend=SoundDeviceBackend(Module())
        before=[device.device_id for device in backend.discover()]
        response=self.discover(backend)
        self.assertEqual("available",response["discovery_status"])
        rows=response["devices"]
        self.assertEqual(2,len(rows))
        self.assertEqual(before,[row["device_id"] for row in rows])
        self.assertEqual(2,len(set(before)))
        self.assertEqual(["Desk microphone"]*2,[row["name"] for row in rows])
        self.assertEqual(["MME","WASAPI"],[row["host_api"] for row in rows])
        self.assertEqual([True,False],[row["is_default"] for row in rows])

    def test_unknown_default_is_omitted_not_inferred_from_name(self):
        for default in (-1,99,None,"Desk microphone"):
            rows=self.discover(SoundDeviceBackend(Module(default)))["devices"]
            self.assertEqual(2,len(rows))
            self.assertTrue(all("is_default" not in row for row in rows))

    def test_legacy_backend_metadata_remains_optional(self):
        backend=SimpleNamespace(discover=lambda:[SimpleNamespace(device_id="legacy-mic")])
        self.assertEqual([{"device_id":"legacy-mic"}],self.discover(backend)["devices"])
