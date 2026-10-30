import struct
import unittest

from u9cht.gdi_raster import gray8_alpha
from u9cht.p5_surface import blend_row, intersect_rect, lock_stub, parse_surface


def descriptor(width=20, height=10, pitch=80):
    v = [0] * 31
    v[:5] = [124, 0x100F, height, width, pitch]
    v[9] = 0x100000
    v[18:26] = [32, 0x40, 0, 32, 0xFF0000, 0xFF00, 0xFF, 0]
    v[26] = 4
    return struct.pack("<31I", *v)


class SurfaceTests(unittest.TestCase):
    def test_surface_format_stride_and_caps(self):
        s = parse_surface(descriptor(pitch=96))
        self.assertEqual((s.width, s.height, s.pitch, s.caps), (20, 10, 96, 4))
        for offset, value in [(0, 108), (4, 0), (16, 79), (16, 0xFFFFFFFC),
                              (72, 0), (84, 16), (100, 0xFF000000)]:
            data = bytearray(descriptor());struct.pack_into("<I", data, offset, value)
            with self.assertRaises(ValueError):parse_surface(data)
        with self.assertRaises(ValueError):parse_surface(b"")

    def test_gray8_padding_range_and_antialias(self):
        self.assertEqual(gray8_alpha(bytes([0, 32, 64, 255]), 3, 1), bytes([0, 128, 255]))
        for data, w, h in [(b"", 1, 1), (bytes([65, 0, 0, 0]), 1, 1), (b"", 513, 0)]:
            with self.assertRaises(ValueError):gray8_alpha(data, w, h)

    def test_blend_endpoints_intermediate_and_preserve_x(self):
        original = bytes([10, 20, 30, 77] * 3)
        out = blend_row(original, bytes([0, 128, 255]), (200, 100, 50))
        self.assertEqual(out[:4], original[:4])
        self.assertEqual(out[8:], bytes([50, 100, 200, 77]))
        self.assertEqual(out[4:8], bytes([30, 60, 115, 77]))
        with self.assertRaises(ValueError):blend_row(b"", b"1")

    def test_half_open_clipping_negative_and_outside_bounds(self):
        self.assertEqual(intersect_rect((-2, 3, 8, 20), (0, 0, 10, 10)), (0, 3, 8, 10))
        self.assertIsNone(intersect_rect((0, 0, 10, 10), (10, 0, 20, 10)))
        with self.assertRaises(ValueError):intersect_rect((2, 0, 1, 1), (0, 0, 3, 3))

    def test_stub_failure_skips_unlock_and_traps_are_bounded(self):
        data, code, first, second = lock_stub(0x200000, 0x300000, (2, 3, 20, 30))
        self.assertEqual(struct.unpack_from("<4i", data, 4), (2, 3, 20, 30))
        self.assertEqual(struct.unpack_from("<I", data, 20)[0], 124)
        self.assertEqual(code[first:first+4], b"\x90\x85\xc0\x78")
        self.assertEqual(first + 5 + code[first+4], second)
        self.assertEqual(code[second:second+4], b"\x90\x0f\xae\x0d")
        self.assertEqual(code[:5], b"\x9c\x60\x0f\xae\x05")
        self.assertEqual(code[-7:-5], b"\x61\x9d")
        self.assertEqual(0x201000 + len(code) + struct.unpack("<i", code[-4:])[0], 0x597B1A)
        self.assertIn(b"\xff\x50\x64", code)
        self.assertIn(b"\xff\x90\x80\x00\x00\x00", code)
        with self.assertRaises(ValueError):lock_stub(1, 2, (0, 0, 1, 1))


if __name__ == "__main__":
    unittest.main()
