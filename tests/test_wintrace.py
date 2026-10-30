import ctypes
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from u9cht.wintrace import (Context32, DebugEvent, hardware_config,
                           forward_copy_destination, verified_window_receipt)


class TraceMetadataTests(unittest.TestCase):
    def test_window_receipt_rejects_unverified_fullscreen_and_changed_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            (game / "Options.ini").write_text("synthetic options\n")
            (game / "dxcfg.ini").write_text("presentation=windowed\n")
            receipt = {"verified_windowed": True, "visual_verified_3d": True,
                       "caption": True, "minimized": False, "client": [533, 400],
                       "screen": [1920, 1200], "configuration_hashes": {
                           name: hashlib.sha256((game / name).read_bytes()).hexdigest()
                           for name in ("Options.ini", "dxcfg.ini")}}
            target = game / "receipt.json"
            target.write_text(json.dumps(receipt))
            self.assertTrue(verified_window_receipt(game, target)["verified_windowed"])
            for key, value in (("visual_verified_3d", False), ("caption", False),
                               ("client", [1920, 1200])):
                target.write_text(json.dumps(dict(receipt, **{key: value})))
                with self.assertRaises(ValueError):
                    verified_window_receipt(game, target)
            target.write_text(json.dumps(receipt))
            (game / "dxcfg.ini").write_text("presentation=application\n")
            with self.assertRaises(ValueError):
                verified_window_receipt(game, target)

    def test_wow64_context_layout(self):
        self.assertEqual(ctypes.sizeof(Context32), 716)
        self.assertEqual(Context32.Eip.offset, 184)
        self.assertEqual(Context32.Esp.offset, 196)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(DebugEvent), 176)
            self.assertEqual(DebugEvent.u.offset, 16)

    def test_hardware_point_control_encoding(self):
        addresses, control = hardware_config([(0x401000, "execute", 1), (0x800000, "readwrite", 2)])
        self.assertEqual(addresses, [0x401000, 0x800000, 0, 0])
        self.assertEqual(control & 0xFF, 5)
        self.assertEqual((control >> 20) & 15, 7)

    def test_invalid_hardware_points_rejected(self):
        for points in ([(1, "execute", 2)], [(3, "readwrite", 2)],
                       [(0, "execute", 1)], [(1, "execute", 1)] * 5):
            with self.assertRaises(ValueError):
                hardware_config(points)

    def test_rep_copy_destination_handles_grouped_iterations(self):
        self.assertEqual(forward_copy_destination("rep movsd", 0x1010, 0x2010, 0x1000, 130),
                         (0x2000, 4, 16))
        self.assertEqual(forward_copy_destination("rep movsd", 0x1004, 0x2004, 0x1000, 130),
                         (0x2000, 4, 4))
        self.assertEqual(forward_copy_destination("rep movsb", 0x1003, 0x2003, 0x1000, 130),
                         (0x2000, 1, 3))

    def test_rep_copy_destination_rejects_ambiguous_direction_and_bounds(self):
        self.assertIsNone(forward_copy_destination("rep movsd", 0x1000, 0x2000, 0x1000, 130))
        self.assertIsNone(forward_copy_destination("rep movsd", 0x1003, 0x2003, 0x1000, 130))
        self.assertIsNone(forward_copy_destination("rep movsd", 0x2000, 0x3000, 0x1000, 130))
        self.assertIsNone(forward_copy_destination("rep movsd", 0x1004, 0x2004, 0x1000, 130, 0x400))
