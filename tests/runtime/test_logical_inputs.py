import unittest
from types import SimpleNamespace
from unittest.mock import patch
from core.audio.logical import MicrophoneInventory
from core.audio.native import NativeDevice


def device(identity,name,host,default=False):
    return NativeDevice(identity,0,name,host,1,48000,default)


class LogicalInputsTests(unittest.TestCase):
    def test_conservative_cross_host_groups_keep_unique_and_same_host_alternatives(self):
        raw=[device("a","USB microphone","Windows WASAPI"),device("b","USB microphone","MME",True),
             device("c","USB microphone","Windows WASAPI"),device("d","Unique line microphone","MME")]
        with patch("core.audio.logical.sys.platform","win32"):
            inventory=MicrophoneInventory(SimpleNamespace(discover=lambda:raw))
        choices=[m for m in inventory.microphones if m["selection_kind"]!="system_default"]
        self.assertEqual(4,len(choices))
        self.assertEqual(set("abcd"),{d.device_id for m in choices for d in inventory.resolve(m["microphone_id"])})
        for m in choices:
            candidates=inventory.resolve(m["microphone_id"])
            self.assertEqual(len(candidates),len({d.host_api for d in candidates}))
        self.assertEqual("system-default",inventory.default_microphone_id)
        self.assertEqual("b",inventory.resolve("b")[0].device_id)
    def test_host_defaults_prioritize_actual_available_provider(self):
        raw=[device("a","Array","MME",True),device("b","Array","Windows WASAPI")]
        backend=SimpleNamespace(discover=lambda:raw,default_inputs=lambda:["a","b"])
        with patch("core.audio.logical.sys.platform","win32"):
            inventory=MicrophoneInventory(backend)
        self.assertEqual(["b","a"],[d.device_id for d in inventory.resolve("system-default")])
        self.assertEqual("name_heuristic",inventory.microphones[1]["grouping"])
    def test_unknown_route_does_not_choose_unrelated_input(self):
        inventory=MicrophoneInventory(SimpleNamespace(discover=lambda:[device("a","Room","ALSA")]))
        self.assertIsNone(inventory.default_microphone_id)
        self.assertEqual([],inventory.resolve("system-default"))
        self.assertEqual([],inventory.resolve("missing"))
