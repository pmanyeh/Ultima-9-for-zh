"""Read-only Octodiff v1 metadata inspection, not a delta applier.

Format checked against Octodiff 1.3.23 source. Unknown algorithms/commands fail
closed. Literal payloads and per-chunk game hashes are never exported by summary.
"""

import hashlib
import struct


class OctoError(ValueError):
    pass


class _Reader:
    def __init__(self, data):
        self.data, self.pos = bytes(data), 0

    def read(self, length):
        if length < 0 or self.pos + length > len(self.data):
            raise OctoError("truncated Octodiff input")
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result

    def number(self, fmt):
        return struct.unpack(fmt, self.read(struct.calcsize(fmt)))[0]

    def string(self):
        length = 0
        for shift in range(0, 35, 7):
            byte = self.number("<B")
            if shift == 28 and byte > 7:
                raise OctoError("invalid .NET string length")
            length |= (byte & 127) << shift
            if not byte & 128:
                if length > 64:
                    raise OctoError("algorithm name too long")
                try:
                    return self.read(length).decode("utf-8", errors="strict")
                except UnicodeError as error:
                    raise OctoError("invalid algorithm name") from error
        raise OctoError("invalid .NET string length")

    def expect(self, value):
        if self.read(len(value)) != value:
            raise OctoError("invalid Octodiff header/version/metadata marker")


def delta_metadata(data, *, basis_size=None, maximum_output=64 * 1024 * 1024):
    """Return commands/offsets/counts only; expected hash describes the TARGET."""
    reader = _Reader(data)
    reader.expect(b"OCTODELTA\x01")
    algorithm = reader.string()
    length = reader.number("<i")
    if algorithm != "SHA1" or length != 20:
        raise OctoError("only SHA1 v1 delta metadata supported")
    expected = reader.read(length).hex()
    reader.expect(b">>>")
    commands, target, literal, copied = [], 0, 0, 0
    while reader.pos < len(reader.data):
        command_offset = reader.pos
        kind = reader.number("<B")
        row = {"delta_offset": command_offset, "target_offset": target}
        if kind == 0x60:
            start, count = reader.number("<q"), reader.number("<q")
            if start < 0 or count <= 0 or (basis_size is not None and start + count > basis_size):
                raise OctoError("copy command outside basis")
            row.update(kind="copy", basis_offset=start)
            copied += count
        elif kind == 0x80:
            count = reader.number("<q")
            if count <= 0:
                raise OctoError("invalid literal length")
            row.update(kind="literal", data_offset=reader.pos)
            reader.read(count)
            literal += count
        else:
            raise OctoError("unknown delta command")
        target += count
        if target > maximum_output:
            raise OctoError("delta output exceeds inspection limit")
        row["length"] = count
        commands.append(row)
    return {"format_version": 1, "hash_algorithm": algorithm,
            "expected_target_sha1": expected, "output_size": target,
            "literal_bytes": literal, "copied_bytes": copied, "commands": commands}


def signature_chunks(data):
    reader = _Reader(data)
    reader.expect(b"OCTOSIG\x01")
    if reader.string() != "SHA1" or reader.string() != "Adler32":
        raise OctoError("only original SHA1/Adler32 signatures supported")
    reader.expect(b">>>")
    if (len(reader.data) - reader.pos) % 26:
        raise OctoError("truncated signature chunk")
    chunks, offset = [], 0
    while reader.pos < len(reader.data):
        length = reader.number("<h")
        if length <= 0:
            raise OctoError("invalid signed chunk length")
        checksum = reader.number("<I")
        chunks.append({"offset": offset, "length": length, "checksum": checksum,
                       "sha1": reader.read(20).hex()})
        offset += length
    return chunks


def _original_adler32(data):
    # Octodiff's original Adler32 uses ushort wrap, NOT zlib's modulus 65521.
    a, b = 1, 0
    for value in data:
        a = (a + value) & 0xFFFF
        b = (b + a) & 0xFFFF
    return b << 16 | a


def signature_comparison(signature, basis):
    chunks = signature_chunks(signature)
    matches, mismatches = 0, []
    for index, row in enumerate(chunks):
        block = basis[row["offset"]:row["offset"] + row["length"]]
        if (len(block) == row["length"] and hashlib.sha1(block).hexdigest() == row["sha1"]
                and _original_adler32(block) == row["checksum"]):
            matches += 1
        else:
            mismatches.append(index)
    size = sum(row["length"] for row in chunks)
    return {"chunks": len(chunks), "matching_chunks": matches,
            "mismatching_chunks": len(mismatches), "first_mismatching_indices": mismatches[:16],
            "represented_length": size, "basis_length": len(basis),
            "whole_basis_matches_signature": not mismatches and size == len(basis)}
