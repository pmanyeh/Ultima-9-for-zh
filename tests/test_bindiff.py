"""Synthetic byte/PE/instruction anchors only."""

import struct
import unittest

from test_pe import synthetic_pe
from u9cht.bindiff import (changed_ranges, cluster_ranges, compare_pe,
                          instruction_token, positional_summary, sequence_matches)


class BinaryDiffTests(unittest.TestCase):
    def test_ranges_include_deletion_and_addition_tails(self):
        self.assertEqual(changed_ranges(b"abcd", b"abXdef"), [(2, 3), (4, 6)])
        self.assertEqual(changed_ranges(b"abc", b"a"), [(1, 3)])
        self.assertEqual(changed_ranges(b"", b""), [])

    def test_clusters_do_not_count_unchanged_gap_as_changed_bytes(self):
        result = cluster_ranges([(0, 2), (4, 5), (9, 10)], gap=2)
        self.assertEqual(result, [{"start": 0, "end": 5, "changed_bytes": 3, "ranges": 2},
                                  {"start": 9, "end": 10, "changed_bytes": 1, "ranges": 1}])

    def test_invalid_clustering_inputs(self):
        for ranges in ([(2, 1)], [(2, 4), (3, 5)], [(-1, 1)], [(1, 1)]):
            with self.assertRaises(ValueError):
                cluster_ranges(ranges)
        with self.assertRaises(ValueError):
            cluster_ranges([], -1)

    def test_positional_summary_is_not_semantic_function_count(self):
        result = positional_summary(b"abcd", b"Xabcd")
        self.assertEqual(result["changed_bytes"], 5)
        self.assertIn("not semantic", result["interpretation"])

    def test_pe_import_difference_and_section_relative_comparison(self):
        left = synthetic_pe()
        right = bytearray(left)
        right[0x2C2:0x2D0] = b"DifferentCall\0"
        result = compare_pe(left, right)
        self.assertEqual(result["imports_added"], [("synthetic.dll", "DifferentCall", None)])
        self.assertEqual(result["imports_removed"], [("synthetic.dll", "SyntheticCall", None)])
        self.assertEqual(result["sections"][0]["name"], ".data")
        self.assertGreater(result["sections"][0]["section_relative_diff"]["changed_bytes"], 0)

    def test_resource_payloads_are_compared_by_hash_only(self):
        left = bytearray(synthetic_pe())
        struct.pack_into("<II", left, 0x98 + 112, 0x1100, 0x100)
        struct.pack_into("<HH", left, 0x30C, 0, 1)
        struct.pack_into("<II", left, 0x310, 8, 0x20)
        struct.pack_into("<IIII", left, 0x320, 0x1200, 4, 0, 0)
        left[0x400:0x404] = b"fake"
        right = bytearray(left)
        right[0x400:0x404] = b"edit"
        result = compare_pe(left, right)
        resource = result["resources"][0]
        self.assertNotEqual(resource["left"]["sha256"], resource["right"]["sha256"])
        self.assertNotIn("fake", str(result))
        self.assertNotIn("edit", str(result))

    def test_matching_masks_relocation_but_keeps_registers_and_constants(self):
        images = [(0x400000, 0x800000)]
        self.assertEqual(instruction_token("call", "0x405000", images), "call TARGET")
        self.assertEqual(instruction_token("mov", "eax, dword ptr [0x750000]", images),
                         "mov eax, dword ptr [ADDRESS]")
        self.assertEqual(instruction_token("test", "eax, 0x20000000", images), "test eax, 0x20000000")
        self.assertNotEqual(instruction_token("inc", "esi", images), instruction_token("inc", "edi", images))
        self.assertNotEqual(instruction_token("push", "0", images), instruction_token("push", "1", images))

    def test_matching_reports_ambiguous_and_absent_anchors(self):
        self.assertEqual(sequence_matches(["a", "b", "a", "b"], ["a", "b"]), [0, 2])
        self.assertEqual(sequence_matches(["a"], ["b"]), [])
        with self.assertRaises(ValueError):
            sequence_matches(["a"], [])
