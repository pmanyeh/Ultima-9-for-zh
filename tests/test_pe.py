"""Public PE fixtures are wholly synthetic; contain no game instructions/assets."""

import struct
import unittest

from u9cht.pe import PEError, PEImage


def synthetic_pe():
    data = bytearray(0x600)
    data[:2] = b"MZ"; struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, 0x14C, 1)
    struct.pack_into("<H", data, 0x94, 0xE0)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<I", data, optional + 28, 0x400000)
    struct.pack_into("<II", data, optional + 56, 0x2000, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 104, 0x1000, 40)
    section = optional + 0xE0
    data[section:section + 8] = b".data\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x500, 0x1000, 0x400, 0x200)
    struct.pack_into("<IIIII", data, 0x200, 0x1080, 0, 0, 0x1060, 0x10A0)
    data[0x260:0x26D] = b"SYNTHETIC.dll"
    struct.pack_into("<III", data, 0x280, 0x10C0, 0x80000007, 0)
    data[0x2C2:0x2D0] = b"SyntheticCall\0"
    return bytes(data)


class PETests(unittest.TestCase):
    def test_header_sections_and_name_ordinal_imports(self):
        pe = PEImage(synthetic_pe())
        self.assertEqual(pe.image_base, 0x400000)
        self.assertEqual(pe.rva_offset(0x10A0), 0x2A0)
        self.assertEqual(pe.offset_rva(0x2A0), 0x10A0)
        imports = pe.imports()
        self.assertEqual(imports[0]["dll"], "SYNTHETIC.dll")
        self.assertEqual(imports[0]["name"], "SyntheticCall")
        self.assertEqual(imports[1]["ordinal"], 7)
        self.assertEqual(imports[0]["iat_rva"], 0x10A0)
        self.assertEqual(pe.resources(), [])

    def test_truncation_invalid_signatures_and_virtual_only_rva(self):
        valid = synthetic_pe()
        for raw in (b"", valid[:50], b"NO" + valid[2:]):
            with self.assertRaises(PEError):
                PEImage(raw)
        pe = PEImage(valid)
        with self.assertRaises(PEError):
            pe.rva_offset(0x1450)
        with self.assertRaises(PEError):
            pe.rva_offset(0x13FF, 2)

    def test_import_bounds_are_checked(self):
        data = bytearray(synthetic_pe())
        struct.pack_into("<I", data, 0x200, 0xFFFFFFFF)
        with self.assertRaises(PEError):
            PEImage(data).imports()

    def test_resource_metadata_without_payload_export(self):
        data = bytearray(synthetic_pe())
        struct.pack_into("<II", data, 0x98 + 112, 0x1100, 0x100)
        struct.pack_into("<HH", data, 0x300 + 12, 0, 1)
        struct.pack_into("<II", data, 0x310, 8, 0x20)
        struct.pack_into("<IIII", data, 0x320, 0x1200, 4, 0, 0)
        data[0x400:0x404] = b"fake"
        resources = PEImage(data).resources()
        self.assertEqual(resources, [{"path": [8], "rva": 0x1200, "size": 4, "codepage": 0}])
        self.assertNotIn("fake", str(resources))
