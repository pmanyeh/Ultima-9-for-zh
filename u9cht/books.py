"""Independent BOOKS records, after observing a genuine readable-item surface.

Only the empirically ASCII subset is editable. Other bodies, including an
embedded binary document, remain opaque and are copied byte for byte.
"""
import re
import struct

from .flx import Archive, FormatError, digest

TOKENS = re.compile(rb"`[fF][0-9]|`[pP]|\r\n|\x00")
TEXT_TOKENS = re.compile(r"`[fF][0-9]|`[pP]|\r\n|\x00")
# P9-4 (CONFIRMED by disassembly of the book reader 0x42E560): a body that begins with the UTF-16LE BOM is
# converted from UTF-16 by the game itself. The reader overwrites the final UTF-16 unit with NUL, so a
# Unicode body always ends with one explicit NUL unit that is not part of the text.
UTF16_BOM = b"\xff\xfe"
# Gargish passages (font `f5) are printed as written. A canonical target refers to the N-th
# such source run with {{gargish:N}} so original text never enters the tracked store; the
# build expands it from the local source.
GARGISH_RUN = re.compile(r"`f5(.*?)(?=`[fFpP]|\Z)", re.S)
GARGISH_REF = re.compile(r"\{\{gargish:([1-9][0-9]?)\}\}")


def gargish_runs(source):
    return GARGISH_RUN.findall(source or "")


def expand_gargish(target, source):
    """Replace each {{gargish:N}} with the N-th `f5 run of the local source (1-based)."""
    runs = gargish_runs(source)

    def run(match):
        n = int(match.group(1))
        if n > len(runs):
            raise ValueError(f"{{{{gargish:{n}}}}} but the source has {len(runs)} Gargish run(s)")
        return runs[n - 1]
    return GARGISH_REF.sub(run, target)


def ascii_body(raw):
    return (raw.decode("ascii") if all(32 <= b < 127 or b in (0, 9, 10, 13)
                                      for b in raw) else None)


def unicode_body(raw):
    """Text of a BOM-marked UTF-16LE body that ends with its NUL unit, else None."""
    if not raw.startswith(UTF16_BOM) or len(raw) % 2 or len(raw) < 4 or raw[-2:] != b"\0\0":
        return None
    try:
        text = raw[2:-2].decode("utf-16-le", errors="strict")
    except UnicodeDecodeError:
        return None
    return text if "\0" not in text else None


def encode_body(text):
    """ASCII bodies keep the original single-byte form; anything else uses the game's UTF-16 book format."""
    if all(32 <= ord(c) < 127 or c in "\t\n\r\0" for c in text):
        return text.encode("ascii")
    if "\0" in text:
        raise FormatError("NUL inside a Unicode book body")
    return UTF16_BOM + text.encode("utf-16-le", errors="strict") + b"\0\0"


class BookArchive(Archive):
    def __init__(self, data):
        super().__init__(data)
        self.records = []
        for entry in self.entries:
            if not entry.is_used:
                continue
            raw = self.payload(entry)
            if len(raw) < 8:
                raise FormatError(f"book {entry.index}: missing field lengths")
            n = struct.unpack_from("<I", raw)[0]
            if not 0 < n <= len(raw)-8:
                raise FormatError(f"book {entry.index}: title length out of bounds")
            title = raw[4:4+n]
            if not title.endswith(b"\0") or b"\0" in title[:-1]:
                raise FormatError(f"book {entry.index}: invalid title terminator")
            try:
                label = title[:-1].decode("ascii", errors="strict")
            except UnicodeDecodeError as error:
                raise FormatError(f"book {entry.index}: title encoding unverified") from error
            m = struct.unpack_from("<I", raw, 4+n)[0]
            body = raw[8+n:]
            if m != len(body):
                raise FormatError(f"book {entry.index}: body size/trailer mismatch")
            self.records.append({"id": entry.index, "offset": entry.offset,
                                 "raw_size": entry.length, "title_length": n,
                                 "title_ascii": label, "body_length": m,
                                 "body_hex": body.hex(), "body_ascii": ascii_body(body),
                                 "body_text": ascii_body(body) if ascii_body(body) is not None
                                 else unicode_body(body)})

    def export(self):
        return {"format": "u9-books-ascii-selection-v1", "source_sha256": digest(self.data),
                "slot_count": len(self.entries), "entries": [dict(r) for r in self.records]}

    def rebuild(self, document):
        baseline = self.export()
        if not isinstance(document, dict) or set(document) != set(baseline):
            raise FormatError("invalid book document fields")
        for key in ("format", "source_sha256", "slot_count"):
            if type(document[key]) is not type(baseline[key]) or document[key] != baseline[key]:
                raise FormatError(f"book source metadata mismatch: {key}")
        rows = document["entries"]
        if not isinstance(rows, list) or len(rows) != len(self.records):
            raise FormatError("missing or extra book records")
        expected = {r["id"]: r for r in self.records}
        replacements, seen = {}, set()
        for row in rows:
            if not isinstance(row, dict) or not self.records or set(row) != set(self.records[0]):
                raise FormatError("invalid book record fields")
            index = row["id"]
            if type(index) is not int or index not in expected or index in seen:
                raise FormatError("duplicate or invalid book ID")
            seen.add(index)
            original = expected[index]
            for key in original.keys()-{"body_ascii", "body_text"}:
                if type(row[key]) is not type(original[key]) or row[key] != original[key]:
                    raise FormatError(f"book {index}: metadata mismatch: {key}")
            text = row["body_ascii"]
            old = self.data[original["offset"]:original["offset"]+original["raw_size"]]
            unicode_edit = row["body_text"] != original["body_text"]
            if unicode_edit and text != original["body_ascii"]:
                raise FormatError(f"book {index}: body_ascii and body_text both changed")
            if unicode_edit:
                new = row["body_text"]
                if original["body_text"] is None or not isinstance(new, str):
                    raise FormatError("opaque book body is not editable")
                if TEXT_TOKENS.findall(original["body_text"]) != TEXT_TOKENS.findall(new):
                    raise FormatError("book font/page/CRLF/NUL control-token mismatch")
                body = encode_body(new)
                title_end = 4+original["title_length"]
                raw = old[:title_end]+struct.pack("<I", len(body))+body
            elif text == original["body_ascii"]:
                raw = old
            else:
                if original["body_ascii"] is None or not isinstance(text, str):
                    raise FormatError("opaque book body is not editable")
                try:
                    body = text.encode("ascii", errors="strict")
                except UnicodeEncodeError as error:
                    raise FormatError("book body encoding beyond ASCII is unverified") from error
                before = bytes.fromhex(original["body_hex"])
                if ascii_body(body) is None or TOKENS.findall(before) != TOKENS.findall(body):
                    raise FormatError("book font/page/CRLF/NUL control-token mismatch")
                title_end = 4+original["title_length"]
                raw = old[:title_end]+struct.pack("<I", len(body))+body
            region = (original["offset"], original["raw_size"])
            if region in replacements and replacements[region] != raw:
                raise FormatError("aliased book records request conflicting bodies")
            replacements[region] = raw
        output = self._rebuild_regions(replacements)
        BookArchive(output)
        return output
