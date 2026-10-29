"""Strict validation around TITAN; original-layout text rebuilding.

Only text.flx payloads are supported here. Unknown header bytes, gaps, trailer,
slot IDs and physical ordering are retained from a hash-locked source template.
"""

import hashlib
import struct

from ._vendor.titan_u9_flx_archive import U9FlxArchive, U9FlxArchiveError


class FormatError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Archive:
    def __init__(self, data):
        self.data = bytes(data)
        try:
            self.upstream = U9FlxArchive(self.data)
        except U9FlxArchiveError as error:
            raise FormatError(str(error)) from error
        self.entries = self.upstream.entries
        self.table_end = 0x80 + len(self.entries) * 8
        if self.upstream.size != len(data) or self.upstream.size2 != len(data):
            raise FormatError("declared file sizes do not match input; preserve and investigate")
        for entry in self.entries:
            if bool(entry.offset) != bool(entry.length):
                raise FormatError(f"entry {entry.index}: ambiguous half-empty slot")
            if entry.is_used and (
                entry.offset < self.table_end or entry.offset + entry.length > len(data)
            ):
                raise FormatError(f"entry {entry.index}: payload out of bounds")
        self.regions = sorted({(e.offset, e.length) for e in self.entries if e.is_used})
        cursor = self.table_end
        for offset, length in self.regions:
            if offset < cursor:
                raise FormatError("partially overlapping payloads; preserve and investigate")
            cursor = offset + length

    def payload(self, entry):
        return self.upstream.read_entry(entry.index)

    def padding(self):
        chunks = []
        cursor = self.table_end
        for offset, length in self.regions:
            chunks.append(self.data[cursor:offset])
            cursor = offset + length
        chunks.append(self.data[cursor:])
        return chunks


class TextArchive(Archive):
    def __init__(self, data):
        super().__init__(data)
        self.records = []
        for entry in self.entries:
            if not entry.is_used:
                continue
            raw = self.payload(entry)
            if len(raw) % 2:
                raise FormatError(f"entry {entry.index}: odd UTF-16LE byte count")
            try:
                decoded = raw.decode("utf-16-le", errors="strict")
            except UnicodeDecodeError as error:
                raise FormatError(f"entry {entry.index}: invalid UTF-16LE") from error
            if not decoded.endswith("\0"):
                raise FormatError(f"entry {entry.index}: missing NUL terminator")
            bom = decoded.startswith("\ufeff")
            # Remove exactly one terminator. Other code units remain represented.
            text = decoded[int(bom):-1]
            self.records.append({
                "id": entry.index, "offset": entry.offset, "raw_size": entry.length,
                "encoding": "utf-16-le", "bom": bom, "terminator": "0000", "text": text,
            })

    def export(self):
        return {
            "format": "u9-text-v1", "source_sha256": digest(self.data),
            "slot_count": len(self.entries), "entries": [dict(r) for r in self.records],
        }

    def rebuild(self, document):
        baseline = self.export()
        if not isinstance(document, dict) or set(document) != set(baseline):
            raise FormatError("invalid document fields")
        for key in ("format", "source_sha256", "slot_count"):
            if type(document[key]) is not type(baseline[key]) or document[key] != baseline[key]:
                raise FormatError(f"source metadata mismatch: {key}")
        rows = document["entries"]
        if not isinstance(rows, list) or len(rows) != len(self.records):
            raise FormatError("missing or extra entry records")
        expected = {r["id"]: r for r in self.records}
        replacements = {}
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(self.records[0]):
                raise FormatError("invalid entry fields")
            index = row["id"]
            if type(index) is not int or index not in expected or index in seen:
                raise FormatError("duplicate or invalid entry ID")
            seen.add(index)
            original = expected[index]
            for key in original.keys() - {"text"}:
                if type(row[key]) is not type(original[key]) or row[key] != original[key]:
                    raise FormatError(f"entry {index}: metadata mismatch: {key}")
            text = row["text"]
            if not isinstance(text, str):
                raise FormatError(f"entry {index}: text must be a string")
            if text != original["text"]:
                if original["text"].endswith(" : BEGIN FILE") or text.endswith(" : BEGIN FILE"):
                    raise FormatError(f"entry {index}: source marker must not change")
                if "\0" in text:
                    raise FormatError(f"entry {index}: unexpected embedded NUL")
            try:
                raw = (("\ufeff" if row["bom"] else "") + text + "\0").encode("utf-16-le")
            except UnicodeEncodeError as error:
                raise FormatError(f"entry {index}: invalid Unicode") from error
            region = (original["offset"], original["raw_size"])
            if region in replacements and replacements[region] != raw:
                raise FormatError("aliased entries request conflicting replacements")
            replacements[region] = raw
        # Copy every non-payload byte and preserve the physical payload order.
        parts = []
        cursor = 0
        output_size = 0
        positions = {}
        for region in self.regions:
            offset, length = region
            gap = self.data[cursor:offset]
            parts.append(gap)
            output_size += len(gap)
            raw = replacements[region]
            positions[region] = (output_size, len(raw))
            parts.append(raw)
            output_size += len(raw)
            cursor = offset + length
        parts.append(self.data[cursor:])
        rebuilt = bytearray(b"".join(parts))
        if len(rebuilt) > 0xFFFFFFFF:
            raise FormatError("rebuilt file exceeds u32 size")
        for entry in self.entries:
            if entry.is_used:
                struct.pack_into("<II", rebuilt, 0x80 + entry.index * 8,
                                 *positions[(entry.offset, entry.length)])
        struct.pack_into("<II", rebuilt, 0x58, len(rebuilt), len(rebuilt))
        # Validate output before returning it to any caller.
        TextArchive(bytes(rebuilt))
        return bytes(rebuilt)


def verify(original, rebuilt):
    ranges = []
    start = None
    differences = 0
    for offset in range(max(len(original), len(rebuilt))):
        changed = original[offset:offset + 1] != rebuilt[offset:offset + 1]
        differences += changed
        if changed and start is None:
            start = offset
        elif not changed and start is not None:
            ranges.append([start, offset])
            start = None
    if start is not None:
        ranges.append([start, max(len(original), len(rebuilt))])
    result = {
        "original_sha256": digest(original), "rebuilt_sha256": digest(rebuilt),
        "original_size": len(original), "rebuilt_size": len(rebuilt),
        "difference_count": differences, "difference_ranges_half_open": ranges,
        "runtime": "NOT EXECUTED", "status": "FAIL",
    }
    try:
        left, right = TextArchive(original), TextArchive(rebuilt)
    except FormatError as error:
        result["error"] = str(error)
        return result
    result["changed_header_fields"] = [
        {"offset": offset, "original": original[offset:offset + 4].hex(),
         "rebuilt": rebuilt[offset:offset + 4].hex()}
        for offset in range(0, 0x80, 4)
        if original[offset:offset + 4] != rebuilt[offset:offset + 4]
    ]
    result["changed_offsets_or_lengths"] = [
        {"id": a.index, "original": [a.offset, a.length], "rebuilt": [b.offset, b.length]}
        for a, b in zip(left.entries, right.entries)
        if (a.offset, a.length) != (b.offset, b.length)
    ]
    result["slot_count_changed"] = len(left.entries) != len(right.entries)
    result["padding_changed"] = left.padding() != right.padding()
    result["semantic_content_changed"] = (
        result["slot_count_changed"] or
        [(e.index, left.payload(e)) for e in left.entries] !=
        [(e.index, right.payload(e)) for e in right.entries]
    )
    if original == rebuilt:
        result["status"] = "BYTE-PERFECT PASS"
    elif not result["semantic_content_changed"]:
        result["status"] = "SEMANTIC PASS"
    return result
