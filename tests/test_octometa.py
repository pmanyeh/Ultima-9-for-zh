"""Synthetic Octodiff metadata only; no executable or upstream payload fixtures."""

import hashlib
import struct
import unittest

from u9cht.octometa import (OctoError, _original_adler32, delta_metadata,
                           signature_comparison, signature_chunks)


def delta_header(target=b"synthetic"):
    return b"OCTODELTA\x01\x04SHA1" + struct.pack("<i", 20) + hashlib.sha1(target).digest() + b">>>"


def signature(data, chunk=4):
    output = bytearray(b"OCTOSIG\x01\x04SHA1\x07Adler32>>>")
    for offset in range(0, len(data), chunk):
        block = data[offset:offset + chunk]
        output += struct.pack("<hI", len(block), _original_adler32(block))
        output += hashlib.sha1(block).digest()
    return bytes(output)


class OctoMetadataTests(unittest.TestCase):
    def test_delta_target_hash_and_command_offsets_without_payload(self):
        raw = delta_header(b"abcdNEW") + b"\x60" + struct.pack("<qq", 0, 4)
        raw += b"\x80" + struct.pack("<q", 3) + b"NEW"
        meta = delta_metadata(raw, basis_size=4)
        self.assertEqual(meta["expected_target_sha1"], hashlib.sha1(b"abcdNEW").hexdigest())
        self.assertEqual((meta["copied_bytes"], meta["literal_bytes"], meta["output_size"]), (4, 3, 7))
        self.assertEqual(meta["commands"][1]["target_offset"], 4)
        self.assertNotIn("NEW", str(meta))

    def test_delta_truncation_invalid_markers_and_algorithms(self):
        raw = delta_header() + b"\x80" + struct.pack("<q", 2) + b"xy"
        for bad in (raw[:7], raw[:20], raw[:-1], raw.replace(b">>>", b"bad", 1),
                    raw.replace(b"SHA1", b"MD5!", 1), raw.replace(b"\x01\x04", b"\x02\x04", 1)):
            with self.subTest(raw=bad[:10]), self.assertRaises(OctoError):
                delta_metadata(bad)

    def test_delta_rejects_unknown_commands_negative_and_oversized_ranges(self):
        commands = [b"\x00", b"\x60" + struct.pack("<qq", -1, 2),
                    b"\x60" + struct.pack("<qq", 0, -1),
                    b"\x60" + struct.pack("<qq", 3, 2),
                    b"\x80" + struct.pack("<q", -1)]
        for command in commands:
            with self.subTest(command=command[:1]), self.assertRaises(OctoError):
                delta_metadata(delta_header() + command, basis_size=4)
        with self.assertRaises(OctoError):
            delta_metadata(delta_header() + b"\x60" + struct.pack("<qq", 0, 5), maximum_output=4)

    def test_signature_matches_each_chunk_and_detects_tail_length(self):
        data = b"synthetic basis"
        raw = signature(data)
        self.assertEqual(len(signature_chunks(raw)), 4)
        self.assertTrue(signature_comparison(raw, data)["whole_basis_matches_signature"])
        result = signature_comparison(raw, data + b"tail")
        self.assertEqual(result["matching_chunks"], 4)
        self.assertFalse(result["whole_basis_matches_signature"])

    def test_signature_mismatch_is_separate_from_delta_compatibility(self):
        result = signature_comparison(signature(b"abcdefgh"), b"abcdEfgh")
        self.assertEqual(result["matching_chunks"], 1)
        self.assertEqual(result["first_mismatching_indices"], [1])
        self.assertNotIn("delta_accepted", result)

    def test_signature_truncation_invalid_length_and_algorithm(self):
        raw = signature(b"abcd")
        for bad in (raw[:-1], raw[:7], raw.replace(b"Adler32", b"Unknown", 1),
                    raw[:24] + struct.pack("<h", -1) + raw[26:]):
            with self.assertRaises(OctoError):
                signature_chunks(bad)

    def test_dotnet_string_bounds_and_encoding(self):
        for raw in (b"OCTODELTA\x01\xff\xff\xff\xff\xff", b"OCTODELTA\x01\x41",
                    b"OCTODELTA\x01\x01\xff"):
            with self.assertRaises(OctoError):
                delta_metadata(raw)

    def test_original_adler_uses_ushort_wrap(self):
        import zlib
        block = b"\xff" * 1000
        self.assertNotEqual(_original_adler32(block), zlib.adler32(block))
        a = (1 + 255 * 1000) & 65535
        b = (1000 + 255 * 1000 * 1001 // 2) & 65535
        self.assertEqual(_original_adler32(block), b << 16 | a)
