from fractions import Fraction
import unittest

from u9cht.p5_unicode import CopyRegistry, logical_advance, make_plan, target_em


class UnicodeTests(unittest.TestCase):
    def test_unicode_segmentation_native_controls_and_one_scalar_per_slot(self):
        p = make_plan("Avatar \u4e2d\u6587 TEST\n", {0x4E2D, 0x6587})
        self.assertEqual(p.slots, b"Avatar \x7f\x7f TEST\n")
        self.assertEqual([(r.route, r.start, r.end) for r in p.runs],
                         [("native", 0, 7), ("unicode", 7, 9), ("native", 9, 15)])
        self.assertEqual(p.scalars[7:9], (0x4E2D, 0x6587))
        supplementary = make_plan("A\U00020000B", {0x20000})
        self.assertEqual(supplementary.slots, b"A\x7fB")
        self.assertEqual(len(supplementary.scalars), 3)

    def test_unsupported_glyph_invalid_unicode_and_collision_fail_closed(self):
        for value in ("", "\0", "\x7f", "\ud800", "\u6587"):
            with self.assertRaises((ValueError, UnicodeError)):make_plan(value, {0x4E2D})

    def test_exact_final_resolution_and_metric_advance(self):
        self.assertEqual(target_em(16, 800, 600), (20, Fraction(5, 4)))
        self.assertEqual(target_em(16, 1600, 1200), (40, Fraction(5, 2)))
        self.assertEqual(logical_advance(40, Fraction(5, 2), 1), 15)
        for args in [(0, 800, 600), (16, 1920, 1080), (1, 800, 600)]:
            with self.assertRaises(ValueError):target_em(*args)
        with self.assertRaises(ValueError):logical_advance(32, Fraction(5, 2), 0)

    def test_copy_edges_lifetime_and_address_reuse(self):
        p = make_plan("A\u4e2dB", {0x4E2D});r = CopyRegistry(p);b = p.slots+b"\0"
        r.add(0x1000, b);r.copy(0x1000, 0x2000, b, b)
        self.assertEqual(r.locate(0x2001), (0x2000, 1))
        r.invalidate(0x1000)
        self.assertIsNone(r.locate(0x1000))
        with self.assertRaises(ValueError):r.copy(0x1000, 0x3000, b, b)
        with self.assertRaises(ValueError):r.verify(0x2000, b"reused")
        self.assertIsNone(r.locate(0x2001))
        with self.assertRaises(ValueError):r.add(0x2000, b"reused")

    def test_overlapping_copy_provenance_rejected(self):
        p = make_plan("A\u4e2dB", {0x4E2D});r = CopyRegistry(p);b = p.slots+b"\0"
        r.add(0x1000, b);r.add(0x1001, b)
        with self.assertRaises(ValueError):r.locate(0x1001)


if __name__ == "__main__":unittest.main()
