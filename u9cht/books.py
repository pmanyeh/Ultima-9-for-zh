"""Independent BOOKS records, after observing a genuine readable-item surface.

Only the empirically ASCII subset is editable. Other bodies, including an
embedded binary document, remain opaque and are copied byte for byte.
"""
import re
import struct

from .flx import Archive, FormatError, digest

TOKENS = re.compile(rb"`[fF][0-9]|`[pP]|\r\n|\x00")


def ascii_body(raw):
    return (raw.decode("ascii") if all(32 <= b < 127 or b in (0, 9, 10, 13)
                                      for b in raw) else None)


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
                                 "body_hex": body.hex(), "body_ascii": ascii_body(body)})

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
            for key in original.keys()-{"body_ascii"}:
                if type(row[key]) is not type(original[key]) or row[key] != original[key]:
                    raise FormatError(f"book {index}: metadata mismatch: {key}")
            text = row["body_ascii"]
            old = self.data[original["offset"]:original["offset"]+original["raw_size"]]
            if text == original["body_ascii"]:
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
