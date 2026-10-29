"""LOCAL-ONLY: SKIPPED WHEN ASSETS ABSENT. Set U9_GAME_DIR explicitly."""

import os
from pathlib import Path
import unittest

from u9cht.flx import TextArchive, digest


@unittest.skipUnless(os.environ.get("U9_GAME_DIR"), "LOCAL-ONLY: SKIPPED WHEN ASSETS ABSENT")
class LocalIntegrationTests(unittest.TestCase):
    def test_observed_text_baseline(self):
        path = Path(os.environ["U9_GAME_DIR"]) / "static/text.flx"
        if not path.is_file():
            self.skipTest("LOCAL-ONLY: SKIPPED WHEN ASSETS ABSENT")
        original = path.read_bytes()
        self.assertEqual(digest(original), "378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0",
                         "STOP: local baseline differs; investigate before rebuilding")
        archive = TextArchive(original)
        self.assertEqual(archive.rebuild(archive.export()), original)
