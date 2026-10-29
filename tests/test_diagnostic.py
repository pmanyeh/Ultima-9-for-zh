import unittest

from test_flx import fixture
from u9cht.diagnostic import analyze_mutation
from u9cht.flx import FormatError, TextArchive


class DiagnosticTests(unittest.TestCase):
    def build(self, replacements):
        source = fixture()
        archive = TextArchive(source)
        document = archive.export()
        for row in document["entries"]:
            if row["id"] in replacements:
                row["text"] = replacements[row["id"]]
        return source, archive.rebuild(document)

    def test_same_length_ascii_changes_only_target_payload(self):
        source, rebuilt = self.build({1: "SYNTHETIC ASCII"})
        result = analyze_mutation(source, rebuilt, 1, "SYNTHETIC ASCII")
        self.assertEqual(result["changed_payload_ids"], [1])
        self.assertEqual(result["changed_offset_count"], 0)
        self.assertEqual(result["size_delta"], 0)
        self.assertEqual(result["changed_header_fields"], [])

    def test_single_bmp_unit_keeps_layout(self):
        text = "\u4e2dynthetic ASCII"
        source, rebuilt = self.build({1: text})
        result = analyze_mutation(source, rebuilt, 1, text)
        self.assertEqual(result["size_delta"], 0)
        self.assertEqual(result["difference_count"], 2)

    def test_changed_length_relocates_only_physical_successors(self):
        text = "Longer synthetic diagnostic text"
        source, rebuilt = self.build({1: text})
        result = analyze_mutation(source, rebuilt, 1, text, same_length=False)
        self.assertEqual(result["changed_offset_count"], 2)
        self.assertGreater(result["size_delta"], 0)
        self.assertEqual([field["offset"] for field in result["changed_header_fields"]], [0x58, 0x5C])

    def test_unrelated_payload_mutation_rejected(self):
        source, rebuilt = self.build({1: "SYNTHETIC ASCII", 2: "other"})
        with self.assertRaisesRegex(FormatError, "exactly the selected"):
            analyze_mutation(source, rebuilt, 1, "SYNTHETIC ASCII")

    def test_unexpected_header_changes_rejected(self):
        source, rebuilt = self.build({1: "SYNTHETIC ASCII"})
        mutated = bytearray(rebuilt); mutated[0x70] ^= 1
        with self.assertRaisesRegex(FormatError, "unknown header"):
            analyze_mutation(source, bytes(mutated), 1, "SYNTHETIC ASCII")

    def test_length_mode_and_wrong_replacement_rejected(self):
        source, rebuilt = self.build({1: "SYNTHETIC ASCII"})
        with self.assertRaisesRegex(FormatError, "must change entry size"):
            analyze_mutation(source, rebuilt, 1, "SYNTHETIC ASCII", same_length=False)
        with self.assertRaisesRegex(FormatError, "replacement text mismatch"):
            analyze_mutation(source, rebuilt, 1, "unexpected")
        source, rebuilt = self.build({1: "different length"})
        with self.assertRaisesRegex(FormatError, "same-length"):
            analyze_mutation(source, rebuilt, 1, "different length")
