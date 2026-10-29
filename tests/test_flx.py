"""All public fixtures below are synthetic byte arrays."""

import copy
import struct
import unittest

from u9cht.flx import Archive, FormatError, TextArchive, verify


def fixture(strings=("", "Synthetic ASCII", "caf\u00e9", "\u6e2c\u8a66"), *, reverse=False):
    count = len(strings) + 1
    header = bytearray(0x80 + count * 8)
    header[:0x4C] = b" " * 0x4C
    header[0x70] = 0xA5  # Unknown bytes must survive.
    struct.pack_into("<II", header, 0x50, count, 2)
    payload = bytearray(b"GAP")
    ids = list(range(len(strings)))
    if reverse:
        ids.reverse()
    for index in ids:
        raw = (strings[index] + "\0").encode("utf-16-le")
        struct.pack_into("<II", header, 0x80 + index * 8, len(header) + len(payload), len(raw))
        payload += raw + b"\x9a"
    payload += b"TRAILER"
    struct.pack_into("<II", header, 0x58, len(header) + len(payload), len(header) + len(payload))
    return bytes(header + payload)


class TextTests(unittest.TestCase):
    def test_exact_roundtrip_empty_ascii_extended_cjk_and_unused(self):
        source = fixture()
        archive = TextArchive(source)
        self.assertEqual([r["text"] for r in archive.records], ["", "Synthetic ASCII", "caf\u00e9", "\u6e2c\u8a66"])
        rebuilt = archive.rebuild(archive.export())
        self.assertEqual(source, rebuilt)
        self.assertEqual(archive.entries[-1].length, 0)
        self.assertEqual(verify(source, rebuilt)["status"], "BYTE-PERFECT PASS")

    def test_non_index_order_unknown_header_gaps_and_trailer_survive_resize(self):
        source = fixture(reverse=True)
        archive = TextArchive(source)
        doc = archive.export()
        doc["entries"][1]["text"] = "A much longer synthetic string"
        rebuilt = archive.rebuild(doc)
        after = TextArchive(rebuilt)
        self.assertEqual(rebuilt[0x70], 0xA5)
        self.assertEqual(archive.padding(), after.padding())
        self.assertEqual(after.records[1]["text"], doc["entries"][1]["text"])
        self.assertEqual(after.records[2]["text"], archive.records[2]["text"])
        self.assertEqual([i for _, i in sorted((r["offset"], r["id"]) for r in archive.records)],
                         [i for _, i in sorted((r["offset"], r["id"]) for r in after.records)])
        self.assertEqual(after.upstream.size, len(rebuilt))
        self.assertTrue(verify(source, rebuilt)["semantic_content_changed"])

    def test_empty_archive_roundtrip(self):
        source = fixture(())
        archive = TextArchive(source)
        self.assertEqual(archive.rebuild(archive.export()), source)

    def test_bom_supplementary_and_multiple_nuls_are_not_normalized(self):
        source = fixture(("\ufeffSynthetic\U0001f600\0",))
        archive = TextArchive(source)
        self.assertTrue(archive.records[0]["bom"])
        self.assertTrue(archive.records[0]["text"].endswith("\0"))
        self.assertEqual(archive.rebuild(archive.export()), source)

    def test_duplicate_offsets_preserved_and_conflicting_edits_rejected(self):
        data = bytearray(fixture(("same", "same")))
        data[0x88:0x90] = data[0x80:0x88]
        archive = TextArchive(data)
        self.assertEqual(archive.rebuild(archive.export()), bytes(data))
        doc = archive.export()
        doc["entries"][0]["text"] = "different"
        with self.assertRaisesRegex(FormatError, "aliased"):
            archive.rebuild(doc)

    def test_missing_duplicate_extra_and_tampered_records_rejected(self):
        archive = TextArchive(fixture())
        baseline = archive.export()
        documents = []
        doc = copy.deepcopy(baseline); doc["source_sha256"] = "0" * 64; documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"].pop(); documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"][1] = doc["entries"][0]; documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"][0]["offset"] += 1; documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"][0]["id"] = False; documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"][0]["text"] = "\ud800"; documents.append(doc)
        doc = copy.deepcopy(baseline); doc["entries"][0]["text"] = "x\0y"; documents.append(doc)
        for document in documents:
            with self.subTest(document=documents.index(document)), self.assertRaises(FormatError):
                archive.rebuild(document)

    def test_marker_mutation_and_creation_rejected(self):
        archive = TextArchive(fixture(("synthetic.cpp : BEGIN FILE", "line")))
        for index, replacement in [(0, "changed"), (1, "invented : BEGIN FILE")]:
            doc = archive.export(); doc["entries"][index]["text"] = replacement
            with self.assertRaisesRegex(FormatError, "marker"):
                archive.rebuild(doc)


class MalformedTests(unittest.TestCase):
    def test_bad_headers_and_bounds(self):
        valid = fixture()
        bad = [valid[:30]]
        for offset, value in [(0x54, 1), (0x50, 0xFFFFFFFF), (0x58, 0),
                              (0x80, 1), (0x80, len(valid) + 1), (0x84, 0)]:
            data = bytearray(valid); struct.pack_into("<I", data, offset, value); bad.append(bytes(data))
        for index, data in enumerate(bad):
            with self.subTest(index=index), self.assertRaises(FormatError):
                TextArchive(data)

    def test_partial_overlap_rejected(self):
        data = bytearray(fixture(("abcd", "efgh")))
        offset = struct.unpack_from("<I", data, 0x80)[0]
        struct.pack_into("<I", data, 0x88, offset + 2)
        with self.assertRaisesRegex(FormatError, "overlapping"):
            Archive(data)

    def test_odd_length_missing_terminator_and_invalid_utf16_rejected(self):
        for raw in (b"A\0B", b"A\0", b"\x00\xd8\0\0"):
            data = bytearray(fixture(("abcd",)))
            offset = struct.unpack_from("<I", data, 0x80)[0]
            data[offset:offset + len(raw)] = raw
            struct.pack_into("<I", data, 0x84, len(raw))
            with self.subTest(raw=raw), self.assertRaises(FormatError):
                TextArchive(data)

    def test_diff_ranges_and_malformed_output_are_explicit(self):
        source = fixture()
        data = bytearray(source); data[0x70:0x72] = b"\x12\x34"
        result = verify(source, bytes(data))
        self.assertEqual(result["status"], "SEMANTIC PASS")
        self.assertEqual(result["difference_count"], 2)
        self.assertEqual(result["difference_ranges_half_open"], [[0x70, 0x72]])
        self.assertFalse(result["semantic_content_changed"])
        self.assertEqual(verify(source, b"broken")["status"], "FAIL")
