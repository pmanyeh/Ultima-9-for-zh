"""Synthetic independent typename fixtures; never redistribute game data."""
import copy
import os
from pathlib import Path
import struct
import unittest

from u9cht.flx import FormatError
from u9cht.typename import TypeNameArchive


def fixture(payloads=None, reverse=True):
    if payloads is None:
        payloads = [struct.pack("<iH", -1, 7041),
                    struct.pack("<iH", 12, 42)+b"Synthetic tool\0\xa5\x00",
                    struct.pack("<iH", 0, 7)+b"\0"]
    header = bytearray(0x80+(len(payloads)+1)*8)
    header[0x70] = 0xA9
    struct.pack_into("<II", header, 0x50, len(payloads)+1, 2)
    tail = bytearray(b"gap")
    for i in (reversed(range(len(payloads))) if reverse else range(len(payloads))):
        struct.pack_into("<II", header, 0x80+8*i, len(header)+len(tail), len(payloads[i]))
        tail += payloads[i]+b"\x95"
    tail += b"trailer"
    struct.pack_into("<II", header, 0x58, len(header)+len(tail), len(header)+len(tail))
    return bytes(header+tail)


class TypeNameTests(unittest.TestCase):
    def test_exact_roundtrip_absent_empty_signed_refs_unknown_bytes(self):
        data = fixture(); a = TypeNameArchive(data)
        self.assertEqual([r["name"] for r in a.records], [None, "Synthetic tool", ""])
        self.assertEqual(a.records[0]["reference_i32"], -1)
        self.assertEqual(a.rebuild(a.export()), data)

    def test_resize_preserves_headers_padding_order_unselected_payloads(self):
        data = fixture(); a = TypeNameArchive(data); doc = a.export()
        doc["entries"][1]["name"] = "U9T_00001"
        raw = a.rebuild(doc); b = TypeNameArchive(raw)
        self.assertEqual(b.records[1]["trailing_hex"], "a500")
        self.assertEqual(a.padding(), b.padding())
        self.assertEqual(raw[0x70], 0xA9)
        for i in (0,2): self.assertEqual(a.payload(a.entries[i]), b.payload(b.entries[i]))
        self.assertEqual(b.payload(b.entries[1])[:6], a.payload(a.entries[1])[:6])

    def test_malformed_header_encoding_terminator_bounds(self):
        for raw in (b"short", b"123456bad", b"123456\x80\0"):
            with self.assertRaises(FormatError): TypeNameArchive(fixture([raw]))
        bad = bytearray(fixture()); struct.pack_into("<I", bad, 0x80, len(bad)+1)
        with self.assertRaises(FormatError): TypeNameArchive(bad)

    def test_document_integrity_and_unverified_unicode_rejected(self):
        a = TypeNameArchive(fixture()); base = a.export()
        mutations = [lambda d:d["entries"].pop(),
                     lambda d:d["entries"].append(d["entries"][0]),
                     lambda d:d["entries"][1].update(id=0),
                     lambda d:d["entries"][0].update(id=False),
                     lambda d:d["entries"][1].update(icon_u16=2),
                     lambda d:d["entries"][1].update(reference_i32=0),
                     lambda d:d["entries"][1].update(trailing_hex=""),
                     lambda d:d["entries"][1].update(name="中"),
                     lambda d:d["entries"][1].update(name="bad\0name"),
                     lambda d:d["entries"][1].update(name=None),
                     lambda d:d.update(source_sha256="0"*64)]
        for change in mutations:
            d = copy.deepcopy(base); change(d)
            with self.assertRaises(FormatError): a.rebuild(d)

    def test_aliases_preserved_and_conflicting_changes_rejected(self):
        data = bytearray(fixture([b"123456same\0", b"123456same\0"]))
        data[0x88:0x90] = data[0x80:0x88]
        a = TypeNameArchive(data); self.assertEqual(a.rebuild(a.export()), bytes(data))
        d = a.export(); d["entries"][1]["name"] = "different"
        with self.assertRaisesRegex(FormatError, "aliased"): a.rebuild(d)

    @unittest.skipUnless(os.environ.get("U9_GAME_DIR"), "LOCAL-ONLY; skipped when assets absent")
    def test_local_unchanged_roundtrip(self):
        path = Path(os.environ["U9_GAME_DIR"])/"static/TYPENAME.FLX"
        if not path.is_file(): self.skipTest("LOCAL-ONLY asset absent")
        raw = path.read_bytes(); a = TypeNameArchive(raw)
        self.assertEqual(a.rebuild(a.export()), raw)


if __name__ == "__main__": unittest.main()
