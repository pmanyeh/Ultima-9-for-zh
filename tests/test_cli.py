import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_flx import fixture


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "u9cht", *map(str, args)], capture_output=True, text=True)

    def test_export_import_verify_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "text.flx"; source.write_bytes(fixture())
            exported = root / "text.json"; rebuilt = root / "rebuilt.flx"
            self.assertEqual(self.run_cli("text", "export", source, "--output", exported).returncode, 0)
            self.assertEqual(self.run_cli("text", "import", source, "--input", exported, "--output", rebuilt).returncode, 0)
            self.assertEqual(self.run_cli("verify-roundtrip", source, rebuilt).returncode, 0)
            self.assertEqual(source.read_bytes(), rebuilt.read_bytes())
            self.assertEqual(self.run_cli("text", "export", source, "--output", exported).returncode, 1)
            self.assertEqual(self.run_cli("text", "import", source, "--input", exported, "--output", source).returncode, 1)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "text.flx"; source.write_bytes(fixture())
            document = root / "bad.json"; document.write_text('{"format":1,"format":2}')
            output = root / "rebuilt.flx"
            self.assertEqual(self.run_cli("text", "import", source, "--input", document, "--output", output).returncode, 1)
            self.assertFalse(output.exists())

    def test_repository_public_dump_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "text.flx"; source.write_bytes(fixture())
            output = Path("reports/SHOULD_NOT_EXIST_GAME_DUMP.json")
            self.assertEqual(self.run_cli("text", "export", source, "--output", output).returncode, 1)
            self.assertFalse(output.exists())
