import ctypes
import unittest

from u9cht.wintrace import Context32, DebugEvent, hardware_config, forward_copy_destination


class TraceMetadataTests(unittest.TestCase):
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
