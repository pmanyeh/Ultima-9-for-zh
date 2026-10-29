"""Synthetic baseline checks; no original game assets."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.preflight import capture


class PreflightTests(unittest.TestCase):
    def test_unconfigured_is_explicitly_blocked(self):
        result = capture()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["assets"], [])
        self.assertEqual(result["blockers"], ["GAME_DIR_NOT_CONFIGURED"])

    def test_nonexistent_install_is_explicitly_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            result = capture(Path(directory) / "absent")
        self.assertEqual(result["blockers"], ["GAME_DIR_NOT_FOUND"])

    def test_empty_install_reports_missing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = capture(directory)
        self.assertIn("TEXT_FLX_NOT_FOUND", result["blockers"])
        self.assertIn("GAME_EXE_NOT_FOUND", result["blockers"])

    def test_recorded_baseline_match_and_changed_input_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "text.flx").write_bytes(b"synthetic text")
            (root / "u9.exe").write_bytes(b"synthetic exe")
            baseline = capture(root)
            matched = capture(root, baseline)
            self.assertTrue(matched["baseline_verified"])
            self.assertEqual(matched["blockers"], [])
            (root / "text.flx").write_bytes(b"changed synthetic text")
            changed = capture(root, baseline)
            self.assertFalse(changed["baseline_verified"])
            self.assertIn("STOP_BASELINE_MISMATCH", changed["blockers"])

    def test_invalid_baseline_does_not_authorize_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = capture(directory, {"assets": []})
            self.assertIn("INVALID_BASELINE", result["blockers"])

    def test_hashes_are_correct_and_sources_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "static").mkdir()
            source = root / "static/TEXT.FLX"
            source.write_bytes(b"synthetic-not-a-real-archive")
            (root / "U9.EXE").write_bytes(b"synthetic-not-an-executable")
            (root / "unrelated.txt").write_text("not inventoried", encoding="utf-8")
            original = source.read_bytes()
            result = capture(root)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(len(result["assets"]), 2)
            item = next(a for a in result["assets"] if a["filename"] == "static/TEXT.FLX")
            self.assertEqual(item["sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(item["size"], len(original))
            self.assertNotIn(directory, json.dumps(result))
            self.assertFalse(result["baseline_verified"])
            self.assertEqual(result["blockers"], ["EDITION_PATCH_AND_EXPECTED_HASHES_UNCONFIRMED"])


if __name__ == "__main__":
    unittest.main()
