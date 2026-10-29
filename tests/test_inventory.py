import json
from pathlib import Path
import struct
import tempfile
import unittest

from scripts.inventory import inventory


def synthetic_archive():
    data = bytearray(0x80 + 16)
    data += b"synthetic"
    struct.pack_into("<II", data, 0x50, 2, 2)
    struct.pack_into("<II", data, 0x58, len(data), len(data))
    struct.pack_into("<II", data, 0x80, 0x90, 9)
    return data


class InventoryTests(unittest.TestCase):
    def test_metadata_only_non_flx_extension_and_unchanged_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "static").mkdir()
            path = root / "static/Tbrk.fn"
            original = synthetic_archive(); path.write_bytes(original)
            result = inventory(root)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(len(result["resources"]), 1)
            record = result["resources"][0]
            self.assertEqual(record["filename"], "static/Tbrk.fn")
            self.assertEqual((record["slots"], record["used"], record["unused"]), (2, 1, 1))
            serialized = json.dumps(result)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("synthetic", serialized)

    def test_malformed_candidate_bounds_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            data = synthetic_archive()
            struct.pack_into("<I", data, 0x80, len(data) + 1)
            (root / "text.flx").write_bytes(data)
            with self.assertRaisesRegex(ValueError, "STOP"):
                inventory(root)
