"""P10-1: misctext.flx joins the text domain; Gargish book passages stay out of the store."""
import unittest

from test_books import book
from test_p7_pipeline import Env, rec
from u9cht.books import expand_gargish, gargish_runs
from u9cht.l10n.adapters import ADAPTERS, MiscTextAdapter
from u9cht.l10n.pipeline import build
from u9cht.l10n.runtime_pack import MISC_ENTRY_BASE, RUNTIME_CONTRACT, decode_pack, plan_entry, shared_text_targets


class MiscTextTests(unittest.TestCase):
    def test_adapter_registered_with_text_layout(self):
        self.assertIsInstance(ADAPTERS["misctext.flx"], MiscTextAdapter)
        self.assertEqual(MISC_ENTRY_BASE, 0xC000)

    def test_plan_entries_and_shared_targets_span_text_and_misctext(self):
        text = rec("text.flx", 7, "選項", "Options")
        misc = rec("misctext.flx", 1, "選項", "Options", category="ui")
        other = rec("misctext.flx", 0, "鎖住了。", "Locked.", category="ui")
        self.assertEqual(plan_entry(misc), MISC_ENTRY_BASE + 1)
        self.assertEqual(shared_text_targets([misc, text, other]), {"misctext.flx:1": "text.flx:7"})
        with self.assertRaises(ValueError):
            plan_entry(rec("misctext.flx", 0x1000, "x", "x"))

    def test_build_writes_misctext_and_text_domain_plans(self):
        env = Env([rec("misctext.flx", 0, "鎖住了。", "Locked.", category="ui"),
                   rec("misctext.flx", 1, "Options", "Options", category="ui")])
        try:
            a = env.analyze()
            self.assertEqual(a.errors, [])
            self.assertEqual([r["key"] for r in a.runtime], ["misctext.flx:0"])
            manifest = build(a, env.root / "out", env.game)
            self.assertEqual(manifest["mutation_audit_status"], "PASS")
            plans = decode_pack((env.root / "out/runtime/allowlist.u9ct").read_bytes())[3]
            # P10-2: a build with misctext also carries the one-character clock plans.
            clock = RUNTIME_CONTRACT["clock_scalars"]
            self.assertEqual(plans[0], (MISC_ENTRY_BASE, "鎖住了。"))
            self.assertEqual(plans[1:], [(RUNTIME_CONTRACT["clock_entry_base"] + i, c) for i, c in enumerate(clock)])
        finally:
            env.close()


class GargishReferenceTests(unittest.TestCase):
    SOURCE = "`f5\r\nKodeks synth\r\n\r\nsynth runes\r\n`p\r\n`f1\r\nSynthetic translation.\r\n"

    def test_expand_and_reject_out_of_range(self):
        self.assertEqual(gargish_runs(self.SOURCE), ["\r\nKodeks synth\r\n\r\nsynth runes\r\n"])
        self.assertEqual(expand_gargish("`f5{{gargish:1}}`p", self.SOURCE),
                         "`f5\r\nKodeks synth\r\n\r\nsynth runes\r\n`p")
        with self.assertRaisesRegex(ValueError, "1 Gargish run"):
            expand_gargish("{{gargish:2}}", self.SOURCE)

    def test_pipeline_expands_reference_from_local_source(self):
        body = self.SOURCE.encode("ascii")
        target = "`f5{{gargish:1}}`p\r\n`f1\r\n合成譯文。\r\n"
        env = Env([rec("BOOKS-EN.FLX", 0, target, self.SOURCE, category="book")], books=[book(body=body)])
        try:
            a = env.analyze()
            self.assertEqual(a.errors, [])
            self.assertEqual(a.runtime[0]["target"], expand_gargish(target, self.SOURCE))
            self.assertNotIn("{{", a.runtime[0]["target"])
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
