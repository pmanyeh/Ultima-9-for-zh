"""Synthetic readable-item records and optional private integration."""
import copy
import os
from pathlib import Path
import struct
import unittest

from test_typename import fixture
from u9cht.books import BookArchive
from u9cht.flx import FormatError


def book(title=b"1: Synthetic\0", body=b"`f2Heading\r\n`f1Synthetic text.`pNext page."):
    return struct.pack("<I", len(title))+title+struct.pack("<I", len(body))+body


class BookTests(unittest.TestCase):
    def test_exact_roundtrip_ascii_empty_body_binary_and_terminal_nul(self):
        data = fixture([book(), book(body=b""), book(body=b"\xd0\xcf\x11\xe0opaque"),
                        book(body=b"Synthetic\0")])
        a = BookArchive(data)
        self.assertIsNone(a.records[2]["body_ascii"])
        self.assertEqual(a.rebuild(a.export()), data)

    def test_single_body_edit_preserves_control_tokens_unknown_bytes_and_others(self):
        a = BookArchive(fixture([book(), book(body=b"Opaque\x80")]))
        d = a.export(); d["entries"][0]["body_ascii"] = d["entries"][0]["body_ascii"].replace("Heading", "U9_BOOK_PROBE")
        out = a.rebuild(d); b = BookArchive(out)
        self.assertEqual(a.padding(), b.padding()); self.assertEqual(out[0x70], 0xA9)
        self.assertEqual(a.payload(a.entries[1]), b.payload(b.entries[1]))
        self.assertEqual(a.records[0]["title_ascii"], b.records[0]["title_ascii"])

    def test_malformed_lengths_title_terminator_and_trailing_data(self):
        for raw in (b"short", book(title=b"not terminated"),
                    book(title=b"bad\0extra\0"), book()+b"trailer",
                    struct.pack("<I", 0xffffffff)+b"data"):
            with self.assertRaises(FormatError): BookArchive(fixture([raw]))

    def test_mutation_rejects_opaque_unicode_tokens_and_metadata(self):
        a = BookArchive(fixture([book(), book(body=b"binary\x80")]))
        changes = [lambda d:d["entries"].pop(),
                   lambda d:d["entries"][1].update(id=0),
                   lambda d:d["entries"][0].update(body_ascii="中文"),
                   lambda d:d["entries"][1].update(body_ascii="changed opaque"),
                   lambda d:d["entries"][0].update(title_ascii="changed internal title"),
                   lambda d:d["entries"][0].update(body_ascii="plain text without markup"),
                   lambda d:d["entries"][0].update(body_ascii="`f2Heading\n`f1Synthetic text.`pNext page."),
                   lambda d:d.update(source_sha256="0"*64)]
        for change in changes:
            d = copy.deepcopy(a.export()); change(d)
            with self.assertRaises(FormatError): a.rebuild(d)

    def test_alias_conflict_and_incomplete_container_replacements(self):
        data = bytearray(fixture([book(), book()]))
        data[0x88:0x90] = data[0x80:0x88]
        a = BookArchive(data); self.assertEqual(a.rebuild(a.export()), bytes(data))
        d = a.export(); d["entries"][1]["body_ascii"] += " Different"
        with self.assertRaisesRegex(FormatError, "aliased"): a.rebuild(d)
        with self.assertRaises(FormatError): a._rebuild_regions({})

    @unittest.skipUnless(os.environ.get("U9_GAME_DIR"), "LOCAL-ONLY; skipped when assets absent")
    def test_local_unchanged_roundtrip(self):
        path = Path(os.environ["U9_GAME_DIR"])/"static/BOOKS-EN.FLX"
        if not path.is_file(): self.skipTest("LOCAL-ONLY asset absent")
        raw = path.read_bytes(); a = BookArchive(raw)
        self.assertEqual(a.rebuild(a.export()), raw)


if __name__ == "__main__": unittest.main()
