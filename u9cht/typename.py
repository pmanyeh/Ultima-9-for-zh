"""Separately verified TYPENAME records; preserve the source FLX container.

Local labels are ASCII, not text.flx UTF-16. Chinese is deliberately rejected
here: a later verified runtime bridge must transport Unicode independently.
"""
import struct

from .flx import Archive, FormatError, digest


class TypeNameArchive(Archive):
    def __init__(self, data):
        super().__init__(data)
        self.records = []
        for entry in self.entries:
            if not entry.is_used:
                continue
            raw = self.payload(entry)
            if len(raw) < 6:
                raise FormatError(f"type {entry.index}: truncated six-byte header")
            reference, icon = struct.unpack_from("<iH", raw)
            storage = raw[6:]
            name, trailing = None, b""
            if storage:
                if b"\0" not in storage:
                    raise FormatError(f"type {entry.index}: missing name terminator")
                label, trailing = storage.split(b"\0", 1)
                try:
                    name = label.decode("ascii", errors="strict")
                except UnicodeDecodeError as error:
                    raise FormatError(f"type {entry.index}: non-ASCII label; investigate encoding") from error
            self.records.append({"id": entry.index, "offset": entry.offset,
                                 "raw_size": entry.length, "reference_i32": reference,
                                 "icon_u16": icon, "name": name,
                                 "trailing_hex": trailing.hex()})

    def export(self):
        return {"format": "u9-typename-ascii-v1", "source_sha256": digest(self.data),
                "slot_count": len(self.entries), "entries": [dict(r) for r in self.records]}

    def rebuild(self, document):
        baseline = self.export()
        if not isinstance(document, dict) or set(document) != set(baseline):
            raise FormatError("invalid typename document fields")
        for key in ("format", "source_sha256", "slot_count"):
            if type(document[key]) is not type(baseline[key]) or document[key] != baseline[key]:
                raise FormatError(f"typename source metadata mismatch: {key}")
        rows = document["entries"]
        if not isinstance(rows, list) or len(rows) != len(self.records):
            raise FormatError("missing or extra typename records")
        expected = {r["id"]: r for r in self.records}
        replacements, seen = {}, set()
        for row in rows:
            if not isinstance(row, dict) or not self.records or set(row) != set(self.records[0]):
                raise FormatError("invalid typename record fields")
            index = row["id"]
            if type(index) is not int or index not in expected or index in seen:
                raise FormatError("duplicate or invalid typename ID")
            seen.add(index)
            original = expected[index]
            for key in original.keys() - {"name"}:
                if type(row[key]) is not type(original[key]) or row[key] != original[key]:
                    raise FormatError(f"type {index}: metadata mismatch: {key}")
            name = row["name"]
            if name is not None and (not isinstance(name, str) or "\0" in name):
                raise FormatError(f"type {index}: invalid display name")
            old = self.data[original["offset"]:original["offset"]+original["raw_size"]]
            if name == original["name"]:
                raw = old
            else:
                try:
                    raw = old[:6] + (name.encode("ascii") + b"\0" if name is not None else b"")
                except UnicodeEncodeError as error:
                    raise FormatError(f"type {index}: only verified ASCII transport is supported") from error
                # Unknown bytes remain present even when removing the label.
                if name is None and original["trailing_hex"]:
                    raise FormatError("cannot remove name without discarding unknown trailing bytes")
                raw += bytes.fromhex(original["trailing_hex"])
            region = (original["offset"], original["raw_size"])
            if region in replacements and replacements[region] != raw:
                raise FormatError("aliased typename records request conflicting names")
            replacements[region] = raw
        # Reuse TITAN's validated directory through Archive. Its generic writer
        # regenerates unknown header/padding bytes, so retain our source layout.
        output = self._rebuild_regions(replacements)
        after = TypeNameArchive(output)
        if self.padding() != after.padding():
            raise FormatError("typename padding changed")
        return bytes(output)
