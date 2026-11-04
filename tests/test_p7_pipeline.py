"""P7 localization pipeline tests. Public fixtures are synthetic byte arrays.

Tests marked LOCAL-ONLY use the user's lawful private game copy and pinned font
and are SKIPPED WHEN ASSETS ARE ABSENT. No test depends on elapsed time.
"""
import copy
import hashlib
import json
import os
import random
import re
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from test_books import book
from test_flx import fixture as text_fixture
from test_typename import fixture as name_fixture
from u9cht.flx import digest
from u9cht.l10n import glossary as gl
from u9cht.l10n.adapters import ADAPTERS, SourceUnit, mutation_audit
from u9cht.l10n.migrate import FROZEN_SHA256, frozen_issues, migrate
from u9cht.l10n.pipeline import Paths, analyze, build, parse_selection
from u9cht.l10n.runtime_pack import (RUNTIME_CONTRACT, contract_sha256, encode_pack,
                                     glyph_manifest)
from u9cht.l10n.store import (FIELDS, REQUIRED, STATUSES, CATEGORIES, dumps_jsonl, load_store,
                              parse_jsonl, parse_key, record_revision, validate_record,
                              write_store)
from u9cht.l10n.workset import export_workset, import_workset

ROOT = Path(__file__).resolve().parents[1]
CAPS = ROOT / "translation" / "resource-capabilities.json"
GLOSSARY_HEADER = "source,target,category,status,enforcement,reference,notes\n"
TEXTS = ["Synthetic greeting", "Second synthetic line", "Third line", "Fourth line",
         "Fifth line", "Sixth line"]


def text_sha(s):
    return digest(s.encode("utf-16-le"))


def rec(resource, entry_id, target, source, status="draft", category="dialogue", **extra):
    if resource == "text.flx":
        sha, units = text_sha(source), len(source.encode("utf-16-le")) // 2
    else:
        raw = source.encode("ascii")
        sha, units = digest(raw), len(raw)
    r = {"key": f"{resource}:{entry_id}", "resource": resource, "entry_id": entry_id,
         "status": status, "category": category, "target": target, "source_sha256": sha,
         "source_units": units, "review": {"terminology": False, "language": False, "runtime": False}}
    r.update(extra)
    return r


def metrics(missing=(), odd=()):
    class M(dict):
        def __missing__(self, scalar):
            index = 0 if scalar in missing else scalar
            return {"index": index, "advance": self.em + (1 if scalar in odd and self.em == 40 else 0),
                    "coverage_sha256": f"{scalar:x}-{self.em}"}

    out = {}
    for em in (20, 40):
        m = M(); m.em = em; out[em] = m
    return lambda scalars: {em: {s: out[em][s] for s in scalars} for em in out}


class Env:
    """Synthetic game + canonical store in a temporary directory."""

    def __init__(self, records, texts=TEXTS, names=None, books=None, glossary="", game_mutator=None):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.game = root / "game"
        (self.game / "static").mkdir(parents=True)
        self.files = {
            "text.flx": text_fixture(tuple(texts)),
            "TYPENAME.FLX": name_fixture(names) if names else name_fixture(),
            "BOOKS-EN.FLX": name_fixture(books or [book()]),
        }
        sources = {"schema": "u9cht-source-baseline-v1", "resources": {}}
        for resource, data in self.files.items():
            sources["resources"][resource] = {"path": f"static/{resource}", "size": len(data),
                                              "sha256": digest(data)}
            (self.game / "static" / resource).write_bytes(game_mutator(resource, data) if game_mutator else data)
        (root / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
        (root / "glossary.csv").write_text(GLOSSARY_HEADER + glossary, encoding="utf-8")
        write_store(root / "store", records)
        self.paths = Paths(store=root / "store", glossary=root / "glossary.csv",
                           capabilities=CAPS, sources=root / "sources.json")
        self.root = root

    def analyze(self, **kw):
        kw.setdefault("game_dir", self.game)
        kw.setdefault("metrics_provider", metrics())
        return analyze(self.paths, **kw)

    def close(self):
        self.tmp.cleanup()


def codes(a, level=None):
    return sorted({i.code for i in a.issues if level is None or i.level == level})


class SchemaAndStoreTests(unittest.TestCase):
    def test_schema_file_matches_enforced_fields(self):
        schema = json.loads((ROOT / "translation/schema/translation.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]), set(FIELDS))
        self.assertEqual(set(schema["required"]), set(REQUIRED))
        self.assertEqual(tuple(schema["properties"]["status"]["enum"]), STATUSES)
        self.assertEqual(tuple(schema["properties"]["category"]["enum"]), CATEGORIES)
        self.assertFalse(schema["additionalProperties"])

    def test_canonical_key_parsing(self):
        self.assertEqual(parse_key("text.flx:4041"), ("text.flx", 4041))
        self.assertEqual(parse_key("TYPENAME.FLX:5290"), ("TYPENAME.FLX", 5290))
        self.assertEqual(parse_key("BOOKS-EN.FLX:0"), ("BOOKS-EN.FLX", 0))
        for bad in ("text.flx:01", "TEXT.FLX:1", "text.flx:-1", "misctext.flx:1", "text.flx",
                    "Honesty", "text.flx:1 ", 4041, None):
            with self.assertRaises(ValueError):
                parse_key(bad)

    def test_jsonl_serialization_is_deterministic_and_strict(self):
        rows = [rec("text.flx", i, f"譯文{i}", TEXTS[i]) for i in range(4)]
        rows.append(rec("TYPENAME.FLX", 1, "工具", "Synthetic tool", category="item-name"))
        shuffled = rows[:]
        random.Random(7).shuffle(shuffled)
        data = dumps_jsonl(shuffled)
        self.assertEqual(data, dumps_jsonl(rows))
        self.assertTrue(data.decode("utf-8").startswith('{"key":"text.flx:0"'))
        self.assertNotIn(b"\r", data)
        parsed, issues = parse_jsonl(data)
        self.assertEqual(issues, [])
        self.assertEqual(dumps_jsonl(parsed), data)
        for bad, code in ((b"\xef\xbb\xbf" + data, "bom"), (data.replace(b"\n", b"\r\n"), "crlf"),
                          (data + b"\n", "blank-line"), (data[:-1], "final-newline"),
                          (b'{"key":"a","key":"b"}\n', "malformed-json"), (b"\xff\n", "malformed-utf8")):
            self.assertIn(code, [i.code for i in parse_jsonl(bad)[1]])

    def test_store_rejects_duplicates_order_and_wrong_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            a, b = rec("text.flx", 1, "甲", TEXTS[1]), rec("text.flx", 2, "乙", TEXTS[2])
            write_store(store, [a, b])
            self.assertEqual(load_store(store)[1], [])
            lines = (store / "text.jsonl").read_bytes().splitlines(keepends=True)
            (store / "text.jsonl").write_bytes(lines[1] + lines[0])
            self.assertIn("non-canonical-serialization", [i.code for i in load_store(store)[1]])
            (store / "text.jsonl").write_bytes(lines[0] + lines[0])
            self.assertIn("duplicate-key", [i.code for i in load_store(store)[1]])
            (store / "text.jsonl").write_bytes(dumps_jsonl([a]))
            (store / "typename.jsonl").write_bytes(dumps_jsonl([b]))
            self.assertIn("invalid-resource", [i.code for i in load_store(store)[1]])

    def test_record_validation_structure_status_and_language(self):
        good = rec("text.flx", 1, "你好，旅人。\n請坐。", TEXTS[1])
        self.assertEqual(validate_record(good), [])

        def issue_codes(**change):
            r = copy.deepcopy(good); r.update(change)
            return [i.code for i in validate_record(r)]

        self.assertIn("invalid-status", issue_codes(status="final"))
        self.assertIn("invalid-category", issue_codes(category="cutscene"))
        self.assertIn("empty-target", issue_codes(target="  "))
        self.assertIn("untranslated-with-target", issue_codes(status="untranslated"))
        self.assertEqual(issue_codes(status="untranslated", target=""), [])
        self.assertIn("replacement-character", issue_codes(target="壞�"))
        self.assertIn("private-use", issue_codes(target="私"))
        self.assertIn("control-character", issue_codes(target="控\x07"))
        self.assertIn("control-character", issue_codes(target="零寬​"))
        self.assertIn("control-character", issue_codes(target="換\r行"))
        self.assertIn("invalid-unicode", issue_codes(target=json.loads('"\\ud800"')))
        self.assertIn("simplified-form", issue_codes(target="这是测试"))
        self.assertIn("unknown-field", issue_codes(source="complete English"))
        self.assertIn("key-mismatch", issue_codes(entry_id=2))
        self.assertIn("invalid-source-hash", issue_codes(source_sha256="ABC"))
        self.assertIn("invalid-review", issue_codes(review={"language": True}))
        self.assertIn("invalid-type", issue_codes(terms=["b", "a"]))
        crlf = rec("BOOKS-EN.FLX", 0, "標題\r\n內文", "x", category="book")
        self.assertEqual(validate_record(crlf), [])
        self.assertIn("control-character", [i.code for i in validate_record(
            rec("text.flx", 1, "標題\r\n內文", TEXTS[1]))])

    def test_simplified_detection_is_diagnostic_only(self):
        r = rec("text.flx", 1, "这", TEXTS[1])
        issues = validate_record(r)
        self.assertEqual([(i.level, i.code) for i in issues], [("warning", "simplified-form")])
        self.assertEqual(r["target"], "这")


class SourceDriftTests(unittest.TestCase):
    def test_entry_source_drift_fails_closed_with_report(self):
        good = rec("text.flx", 1, "第二行", TEXTS[1])
        stale = rec("text.flx", 2, "第三行", "An older English revision")
        env = Env([good, stale])
        try:
            a = env.analyze()
            drift = [i for i in a.issues if i.code == "source-drift"]
            self.assertEqual(len(drift), 1)
            self.assertEqual(drift[0].data, {"resource": "text.flx", "entry_id": 2,
                                             "expected_source_sha256": stale["source_sha256"],
                                             "observed_source_sha256": text_sha(TEXTS[2])})
            with self.assertRaisesRegex(ValueError, "build refused"):
                build(a, env.root / "out", env.game)
            self.assertFalse((env.root / "out").exists())
        finally:
            env.close()

    def test_resource_hash_drift_and_missing_entry(self):
        env = Env([rec("text.flx", 99, "不存在", "x")],
                  game_mutator=lambda r, d: d[:-1] + b"X" if r == "BOOKS-EN.FLX" else d)
        try:
            a = env.analyze()
            self.assertIn("resource-drift", codes(a, "error"))
            self.assertIn("missing-source-entry", codes(a, "error"))
            relaxed = env.analyze(allow_resource_drift=True)
            self.assertIn("resource-drift", codes(relaxed, "warning"))
        finally:
            env.close()

    def test_locked_marker_units_aliases_and_placeholders(self):
        texts = ["Hello %s, you have %d coins", "data : BEGIN FILE", "x"]
        env = Env([rec("text.flx", 0, "你好 %s，你有金幣", texts[0]),
                   rec("text.flx", 1, "標記", texts[1]),
                   dict(rec("text.flx", 2, "單位", "x"), source_units=9)], texts=texts)
        try:
            a = env.analyze()
            self.assertTrue({"placeholder-mismatch", "locked-source-entry",
                             "source-units-mismatch"} <= set(codes(a, "error")))
        finally:
            env.close()

    def test_books_control_token_sequence(self):
        body = "`f2Heading\r\n`f1Synthetic text.`pNext page."
        ok = rec("BOOKS-EN.FLX", 0, "`f2標題\r\n`f1中文內文。`p下一頁。", body, category="book",
                 runtime_supported=False)
        bad = rec("BOOKS-EN.FLX", 1, "沒有頁面標記", body, category="book", runtime_supported=False)
        env = Env([ok, bad], books=[book(), book()])
        try:
            a = env.analyze()
            tokens = [i.key for i in a.issues if i.code == "control-token-mismatch"]
            self.assertEqual(tokens, ["BOOKS-EN.FLX:1"])
        finally:
            env.close()


class WorksetTests(unittest.TestCase):
    def setUp(self):
        self.game = {"text.flx": text_fixture(tuple(TEXTS))}
        self.store = [rec("text.flx", 1, "第二行", TEXTS[1]),
                      rec("text.flx", 2, "第三行", TEXTS[2], status="approved")]

    def rows(self, **kw):
        files, manifest = export_workset(self.store, self.game, **kw)
        self.assertTrue(manifest["local_only"])
        return [json.loads(line) for line in files["text.flx"].decode("utf-8").splitlines()]

    def test_export_merges_local_source_with_canonical(self):
        rows = self.rows()
        by = {r["key"]: r for r in rows}
        self.assertEqual(by["text.flx:1"]["source"], TEXTS[1])
        self.assertEqual(by["text.flx:1"]["target"], "第二行")
        self.assertEqual(by["text.flx:3"]["status"], "untranslated")
        self.assertIsNone(by["text.flx:3"]["base_revision"])
        self.assertEqual(by["text.flx:1"]["base_revision"], record_revision(self.store[0]))
        self.assertEqual([r["key"] for r in self.rows(include_untranslated=False)],
                         ["text.flx:1", "text.flx:2"])
        self.assertEqual([r["key"] for r in self.rows(selection=parse_selection(["text.flx:3-4"]))],
                         ["text.flx:3", "text.flx:4"])

    def test_unchanged_import_is_noop_and_update_applies(self):
        rows = self.rows()
        new, report = import_workset(self.store, rows, self.game)
        self.assertEqual((report["status"], report["changes"]), ("OK", []))
        self.assertEqual(new, sorted(self.store, key=lambda r: r["entry_id"]))
        edit = [r for r in rows if r["key"] == "text.flx:1"]
        edit[0]["target"], edit[0]["status"] = "第二行（修訂）", "review"
        new, report = import_workset(self.store, edit, self.game)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(next(r for r in new if r["key"] == "text.flx:1")["status"], "review")

    def test_conflicts_are_reported_and_nothing_applied(self):
        rows = {r["key"]: r for r in self.rows()}
        cases = []
        r = copy.deepcopy(rows["text.flx:1"]); r["status"] = "untranslated"; r["target"] = ""
        cases.append(([r], "status regression"))
        r = copy.deepcopy(rows["text.flx:2"]); r["target"] = "改寫"; r["status"] = "draft"
        cases.append(([r], "status regression"))
        r = copy.deepcopy(rows["text.flx:1"]); r["target"] = "新"
        cases.append(([r, copy.deepcopy(r)], "duplicate key"))
        r = copy.deepcopy(rows["text.flx:3"]); r["target"] = "新增"; r["status"] = "draft"
        cases.append(([r], "unknown key"))
        r = copy.deepcopy(rows["text.flx:1"]); r["target"] = "新"; r["source_sha256"] = "0" * 64
        cases.append(([r], "SOURCE DRIFT"))
        r = copy.deepcopy(rows["text.flx:1"]); r["target"] = "新"; r["base_revision"] = "f" * 64
        cases.append(([r], "changed since workset export"))
        r = copy.deepcopy(rows["text.flx:1"]); r["target"] = "新"; r["status"] = "final"
        cases.append(([r], "invalid record"))
        for work, reason in cases:
            new, report = import_workset(self.store, work, self.game)
            self.assertEqual(report["status"], "CONFLICT", reason)
            self.assertIn(reason, " ".join(c["reason"] for c in report["conflicts"]))

    def test_explicit_options_create_regress_force(self):
        rows = {r["key"]: r for r in self.rows()}
        r = copy.deepcopy(rows["text.flx:3"]); r["target"] = "新增"; r["status"] = "draft"
        new, report = import_workset(self.store, [r], self.game, create=True)
        self.assertEqual(report["changes"][0]["action"], "create")
        self.assertIn("text.flx:3", [x["key"] for x in new])
        r = copy.deepcopy(rows["text.flx:2"]); r["target"] = "改寫"; r["status"] = "draft"
        _, report = import_workset(self.store, [r], self.game, allow_status_regression=True)
        self.assertIn("without --force", report["conflicts"][0]["reason"])
        _, report = import_workset(self.store, [r], self.game, allow_status_regression=True, force=True)
        self.assertEqual(report["status"], "OK")


class GlossaryTests(unittest.TestCase):
    ROWS = ("Honesty,誠實,virtue,approved,mandatory,ref,\n"
            "Valor,英勇,virtue,approved,recommended,ref,\n"
            "Britannia,Britannia,place,review,informational,ref,\n"
            "Skara,斯卡拉,place,blocked,informational,ref,rejected form\n")

    def rows(self, text):
        rows, issues = gl.parse_glossary((GLOSSARY_HEADER + text).encode("utf-8"))
        return rows, issues + gl.glossary_issues(rows)

    def test_parse_and_internal_conflicts(self):
        rows, issues = self.rows(self.ROWS)
        self.assertEqual((len(rows), issues), (4, []))
        _, issues = self.rows(self.ROWS + "Honesty,忠實,virtue,approved,mandatory,ref,\n")
        self.assertIn("term-multiple-approved-targets", [i.code for i in issues])
        _, issues = self.rows(self.ROWS + "Truth,誠實,virtue,approved,mandatory,ref,\n")
        self.assertIn("term-target-conflict", [i.code for i in issues])
        _, issues = self.rows("x,y,beast,final,always,,\n")
        self.assertTrue({"glossary-category", "glossary-status", "glossary-enforcement",
                         "glossary-reference"} <= {i.code for i in issues})
        self.assertEqual(gl.parse_glossary(b"a,b\n")[1][0].code, "glossary-header")

    def test_record_terminology_checks(self):
        rows, _ = self.rows(self.ROWS)
        records = [rec("text.flx", 1, "誠實是美德。", TEXTS[1], terms=["Honesty"]),
                   rec("text.flx", 2, "說實話是美德。", TEXTS[2], terms=["Honesty"]),
                   rec("text.flx", 3, "勇氣", TEXTS[3], terms=["Valor"]),
                   rec("text.flx", 4, "前往 Britannia", TEXTS[4], terms=["Britannia", "Nowhere"]),
                   rec("text.flx", 5, "斯卡拉港", TEXTS[5])]
        issues = gl.terminology_issues(records, rows)
        got = {(i.key, i.code, i.level) for i in issues}
        self.assertIn(("text.flx:2", "term-not-used", "error"), got)
        self.assertIn(("text.flx:3", "term-not-used", "warning"), got)
        self.assertIn(("text.flx:4", "term-not-in-glossary", "warning"), got)
        self.assertIn(("text.flx:5", "blocked-term", "error"), got)
        self.assertNotIn("text.flx:1", {i.key for i in issues})
        untagged = gl.terminology_issues([rec("text.flx", 1, "說實話", TEXTS[1])], rows,
                                         {"text.flx:1": "Honesty is a virtue"})
        self.assertEqual([(i.code, i.level) for i in untagged], [("term-possibly-untagged", "warning")])
        prose = gl.terminology_issues([rec("text.flx", 1, "說實話", TEXTS[1])], rows,
                                      {"text.flx:1": "Dishonesty is not Honestyish"})
        self.assertEqual(prose, [])

    def test_committed_glossary_is_valid_and_claims_nothing_official(self):
        rows, issues = gl.parse_glossary((ROOT / "translation/glossary/U9_TERMS.csv").read_bytes())
        self.assertEqual(issues + gl.glossary_issues(rows), [])
        self.assertFalse([r for r in rows if r["status"] == "approved"])
        for r in rows:
            self.assertNotIn("official", r["reference"].lower())


class FontGlyphLayoutTests(unittest.TestCase):
    def test_font_coverage_reports_missing_scalar_and_keys(self):
        env = Env([rec("text.flx", 1, "甲乙", TEXTS[1]), rec("text.flx", 2, "乙丙", TEXTS[2])])
        try:
            a = env.analyze(metrics_provider=metrics(missing={ord("乙")}))
            missing = [i for i in a.issues if i.code == "font-missing-glyph"]
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0].data, {"scalar": "U+4E59", "character": "乙",
                                               "keys": ["text.flx:1", "text.flx:2"]})
            self.assertEqual(a.glyphs["missing_glyphs"], ["U+4E59"])
            odd = env.analyze(metrics_provider=metrics(odd={ord("丙")}))
            self.assertIn("font-missing-glyph", codes(odd, "error"))
            unchecked = env.analyze(metrics_provider=None)
            self.assertIn("font-not-checked", codes(unchecked, "warning"))
        finally:
            env.close()

    def test_glyph_manifest_is_derived_and_deterministic(self):
        rows = [rec("text.flx", 2, "你好，Avatar。", TEXTS[2]), rec("text.flx", 1, "好！", TEXTS[1])]
        m = glyph_manifest(rows, metrics()([ord(c) for c in "你好，。！"]))
        self.assertEqual([g["scalar"] for g in m["glyphs"]], ["U+3002", "U+4F60", "U+597D", "U+FF01", "U+FF0C"])
        self.assertEqual((m["unique_scalar_count"], m["unique_han_count"], m["punctuation_count"]), (5, 2, 3))
        self.assertEqual(m["latin_native_count"], len(set("Avatar")))
        self.assertEqual((m["cache_requirement"], m["missing_glyph_count"]), (10, 0))
        self.assertEqual(m["glyphs"][2]["keys"], ["text.flx:1", "text.flx:2"])
        self.assertEqual(m, glyph_manifest(list(reversed(rows)), metrics()([ord(c) for c in "你好，。！"])))
        self.assertEqual(m["glyphs"][1]["logical_advance"], 16)

    def test_layout_overflow_warning_unknown_and_profiles(self):
        long_line = "長" * 34                                   # 34 * 16 = 544 > 528
        records = [rec("text.flx", 1, "正常字幕。", TEXTS[1], category="subtitle"),
                   rec("text.flx", 2, long_line, TEXTS[2]),
                   rec("text.flx", 3, "第一行\n，第二行", TEXTS[3]),
                   rec("text.flx", 4, "日誌內容", TEXTS[4], category="journal"),
                   rec("TYPENAME.FLX", 1, "工具\n二行", "Synthetic tool", category="item-name")]
        env = Env(records)
        try:
            a = env.analyze()
            status = {row["key"]: row["status"] for row in a.layout}
            self.assertEqual(status, {"text.flx:1": "PASS", "text.flx:2": "OVERFLOW", "text.flx:3": "WARNING",
                                      "text.flx:4": "UNKNOWN-LAYOUT", "TYPENAME.FLX:1": "OVERFLOW"})
            self.assertEqual(next(r for r in a.layout if r["key"] == "text.flx:2")["line_widths"], [544])
            self.assertIn("layout-overflow", codes(a, "error"))
            self.assertIn("layout-warning", codes(a, "warning"))
            self.assertEqual(records[2]["target"], "第一行\n，第二行")   # never auto-rewritten
            approved = [dict(r, status="approved") for r in records[2:4]]
            env2 = Env(approved)
            try:
                b = env2.analyze(profile="approved")
                self.assertTrue({"layout-warning", "layout-unknown"} <= set(codes(b, "error")))
            finally:
                env2.close()
        finally:
            env.close()

    def test_minimal_kinsoku_rules(self):
        env = Env([rec("text.flx", 1, "開始「\n內容」。", TEXTS[1]),
                   rec("text.flx", 2, "說明\n）結束", TEXTS[2]),
                   rec("text.flx", 3, "（括號內）\n正常。", TEXTS[3]),
                   rec("text.flx", 4, "一\n二\n三", TEXTS[4])])
        try:
            rows = {r["key"]: r for r in env.analyze().layout}
            self.assertIn("ends with opening punctuation", " ".join(rows["text.flx:1"]["issues"]))
            self.assertIn("starts with prohibited punctuation", " ".join(rows["text.flx:2"]["issues"]))
            self.assertEqual(rows["text.flx:3"]["status"], "PASS")
            self.assertIn("exceed observed maximum", " ".join(rows["text.flx:4"]["issues"]))
        finally:
            env.close()


class CapabilityAndBuildTests(unittest.TestCase):
    def records(self):
        return [rec("text.flx", 0, "草稿", TEXTS[0], status="draft"),
                rec("text.flx", 1, "審閱", TEXTS[1], status="review"),
                rec("text.flx", 2, "核准", TEXTS[2], status="approved"),
                rec("text.flx", 3, "封鎖", TEXTS[3], status="blocked"),
                rec("text.flx", 4, "", TEXTS[4], status="untranslated"),
                rec("text.flx", 5, "展示", TEXTS[5], status="showcase-draft"),
                rec("TYPENAME.FLX", 1, "合成工具", "Synthetic tool", category="item-name"),
                rec("BOOKS-EN.FLX", 0, "`f2標題\r\n`f1中文。`p下一頁。",
                    "`f2Heading\r\n`f1Synthetic text.`pNext page.", category="book",
                    runtime_supported=False)]

    def test_capability_manifest_has_evidence_and_no_promoted_unknowns(self):
        caps = json.loads(CAPS.read_text(encoding="utf-8"))
        for resource, entry in caps["resources"].items():
            for name in ("decode", "roundtrip", "translate_build", "unicode_runtime"):
                self.assertIn(entry[name]["status"], caps["evidence_levels"], (resource, name))
                self.assertTrue(entry[name]["evidence"], (resource, name))
                if entry[name]["status"] == "UNKNOWN":
                    self.assertFalse(entry[name]["value"], (resource, name))
        self.assertFalse(caps["resources"]["BOOKS-EN.FLX"]["unicode_runtime"]["value"])
        self.assertEqual(caps["runtime"]["font"]["sha256"],
                         "dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4")

    def test_profiles_and_unsupported_runtime_family(self):
        env = Env(self.records())
        try:
            dev = env.analyze()
            self.assertEqual(dev.errors, [])
            self.assertEqual([r["key"] for r in dev.included["text.flx"]],
                             ["text.flx:0", "text.flx:1", "text.flx:2", "text.flx:5"])
            self.assertEqual([r["key"] for r in dev.runtime],
                             ["text.flx:0", "text.flx:1", "text.flx:2", "text.flx:5", "TYPENAME.FLX:1"])
            excluded = {e["key"]: e["reason"] for e in dev.excluded}
            self.assertEqual(excluded["BOOKS-EN.FLX:0"], "runtime_supported=false")
            self.assertIn("not allowed", excluded["text.flx:3"])
            self.assertNotIn("text.flx:4", excluded)
            rel = env.analyze(profile="approved")
            self.assertEqual([r["key"] for r in rel.runtime], ["text.flx:2"])
            self.assertNotIn("BOOKS-EN.FLX", rel.included)
        finally:
            env.close()
        books = self.records()[-1:]
        books[0]["runtime_supported"] = None
        env = Env(books)
        try:
            a = env.analyze()
            self.assertEqual(a.excluded[0]["reason"], "Unicode runtime unsupported for this resource family")
        finally:
            env.close()
        ascii_book = [rec("BOOKS-EN.FLX", 0, "`f2Synthetic heading\r\n`f1Edited.`pPage two.",
                          "`f2Heading\r\n`f1Synthetic text.`pNext page.", category="book")]
        env = Env(ascii_book)
        try:
            a = env.analyze()
            self.assertEqual(list(a.included), ["BOOKS-EN.FLX"])
            self.assertEqual(a.runtime, [])
            manifest = build(a, env.root / "out", env.game)
            self.assertIn("BOOKS-EN.FLX", manifest["resource_output_sha256"])
            self.assertIsNone(manifest["runtime_pack_sha256"])
        finally:
            env.close()

    def test_runtime_renderer_capability_scalars(self):
        env = Env([rec("text.flx", 1, "破折號—不支援", TEXTS[1]),
                   rec("TYPENAME.FLX", 1, "工具", "Synthetic tool", category="item-name"),
                   rec("text.flx", 2, "重複", TEXTS[2]), rec("text.flx", 3, "重複", TEXTS[3])])
        try:
            a = env.analyze()
            bad = next(i for i in a.issues if i.code == "runtime-unsupported-scalar")
            self.assertEqual(bad.data["scalars"], ["U+2014"])
            self.assertIn("identical runtime target", " ".join(i.message for i in a.issues
                                                              if i.code == "runtime-capacity"))
        finally:
            env.close()

    def test_deterministic_build_manifest_audit_and_safety(self):
        records = [r for r in self.records() if r["status"] != "untranslated"]
        env = Env(records)
        try:
            a = env.analyze()
            m1 = build(a, env.root / "out1", env.game)
            m2 = build(env.analyze(), env.root / "out2", env.game)
            self.assertEqual(m1, m2)
            files = sorted(p.relative_to(env.root / "out1").as_posix()
                           for p in (env.root / "out1").rglob("*") if p.is_file())
            self.assertEqual(files, ["build-manifest.json", "glyph-manifest.json", "mutation-audit.json",
                                     "qa/layout-report.json", "qa/qa-report.json", "runtime/allowlist.u9ct",
                                     "static/TYPENAME.FLX", "static/text.flx"])
            for name in files:
                self.assertEqual((env.root / "out1" / name).read_bytes(), (env.root / "out2" / name).read_bytes())
            self.assertEqual(m1["runtime_pack_version"], 3)
            self.assertEqual(m1["mutation_audit_status"], "PASS")
            self.assertFalse(m1["installed"])
            for key in ("source_game_sha256", "canonical_store_sha256", "glossary_sha256", "font_sha256",
                        "runtime_contract_sha256", "resource_output_sha256", "runtime_pack_sha256",
                        "translation_counts_by_status", "translation_counts_by_resource", "glyph_counts",
                        "layout_qa_counts", "profile", "tool_version", "git_commit"):
                self.assertIn(key, m1)
            audit = json.loads((env.root / "out1/mutation-audit.json").read_text(encoding="utf-8"))
            text = next(x for x in audit["resources"] if x["resource"] == "text.flx")
            self.assertEqual(text["changed_entries"], [0, 1, 2, 5])
            self.assertEqual(text["unexpected_byte_differences"], [])
            self.assertEqual(env.game.joinpath("static/text.flx").read_bytes(), env.files["text.flx"])
            with self.assertRaisesRegex(ValueError, "new or empty"):
                build(env.analyze(), env.root / "out1", env.game)
            with self.assertRaisesRegex(ValueError, "game installation"):
                build(env.analyze(), env.game / "build", env.game)
            with self.assertRaisesRegex(ValueError, "ignored private directory"):
                build(env.analyze(), ROOT / "translation" / "build-test", env.game)
        finally:
            env.close()


class MutationAuditTests(unittest.TestCase):
    def test_adapter_audits_detect_unintended_changes(self):
        adapter = ADAPTERS["text.flx"]
        source = text_fixture(tuple(TEXTS))
        out, audit = adapter.build(source, {1: "中文"})
        self.assertEqual((audit["status"], audit["changed_entries"]), ("PASS", [1]))
        self.assertEqual(audit["unchanged_entry_count"], len(TEXTS) - 1)
        self.assertGreater(audit["relocated_offsets"], 0)
        self.assertEqual([f["offset"] for f in audit["changed_metadata_fields"]], ["0x58", "0x5c"])
        sneaky, _ = adapter.build(source, {1: "中文", 3: "偷改"})
        bad = mutation_audit(adapter, source, sneaky, {1: "中文"})
        self.assertEqual(bad["status"], "FAIL")
        self.assertIn("unselected payloads changed: [3]", bad["unexpected_byte_differences"])
        header = bytearray(out); header[0x70] ^= 0xFF
        self.assertIn("unknown header fields changed", " ".join(
            mutation_audit(adapter, source, bytes(header), {1: "中文"})["unexpected_byte_differences"]))
        self.assertIn("not changed", " ".join(
            mutation_audit(adapter, source, source, {1: "中文"})["unexpected_byte_differences"]))

    def test_typename_marker_preserves_opaque_bytes(self):
        adapter = ADAPTERS["TYPENAME.FLX"]
        out, audit = adapter.build(name_fixture(), {1: "合成工具"})
        self.assertEqual(audit["status"], "PASS")
        units = adapter.units(out)
        self.assertEqual(units[1].text, "U9T0001")
        self.assertEqual(adapter.archive(out).records[1]["trailing_hex"], "a500")
        self.assertFalse(adapter.units(name_fixture())[0].editable)


class PackAndMigrationTests(unittest.TestCase):
    def test_native_contract_mirrors_runtime_headers(self):
        identity = (ROOT / "runtime/U9ChtRuntime/identity.h").read_text(encoding="utf-8")
        cache = (ROOT / "runtime/U9ChtRuntime/glyph_cache.h").read_text(encoding="utf-8")
        version = (ROOT / "runtime/common/version_manifest.h").read_text(encoding="utf-8")
        consts = dict(re.findall(r"(MaxPlans|MaxText|MaxGlyphScalars)\s*=\s*(\d+)", identity))
        self.assertEqual(int(consts["MaxPlans"]), RUNTIME_CONTRACT["max_plans"])
        self.assertEqual(int(consts["MaxText"]), RUNTIME_CONTRACT["max_plan_utf16_units"])
        self.assertEqual(int(consts["MaxGlyphScalars"]), RUNTIME_CONTRACT["max_glyph_scalars"])
        self.assertIn(f"NameDomain = 0x{RUNTIME_CONTRACT['name_domain']:08X}", identity)
        self.assertIn(f"GlyphCacheCapacity = {RUNTIME_CONTRACT['glyph_cache_capacity']}", cache)
        self.assertIn(f'"{RUNTIME_CONTRACT["runtime"]}"', version)
        self.assertEqual(len(contract_sha256()), 64)

    def test_generated_pack_equals_legacy_showcase_builders(self):
        from u9cht.representative import build_inventory
        from u9cht.showcase import build_resource
        source = text_fixture(("", "Synthetic ASCII", "Third"))
        rows = [rec("text.flx", 1, "合成，測試", "Synthetic ASCII", status="showcase-draft"),
                rec("text.flx", 2, "第二\n行", "Third", status="showcase-draft")]
        legacy_doc = {"schema": "u9cht-showcase-v1", "source_archive_sha256": digest(source),
                      "entries": [dict(r, source_utf16_units=r["source_units"]) for r in rows]}
        for r in legacy_doc["entries"]:
            for k in ("resource", "entry_id", "category", "review", "source_units"):
                r.pop(k)
        legacy_text, legacy_pack, _ = build_resource(source, legacy_doc)
        new_text, _ = ADAPTERS["text.flx"].build(source, {1: rows[0]["target"], 2: rows[1]["target"]})
        self.assertEqual(new_text, legacy_text)
        self.assertEqual(encode_pack(rows, digest(new_text)), legacy_pack)
        names = name_fixture()
        name_row = rec("TYPENAME.FLX", 1, "合成工具", "Synthetic tool", status="showcase-draft",
                       category="item-name")
        name_doc = {"schema": "u9cht-showcase-names-v1", "source_archive_sha256": digest(names),
                    "entries": [{"key": "TYPENAME.FLX:1", "target": "合成工具", "status": "showcase-draft",
                                 "source_sha256": name_row["source_sha256"]}]}
        _, legacy_names, legacy_v3, _ = build_inventory(source, legacy_doc, names, name_doc)
        new_names, _ = ADAPTERS["TYPENAME.FLX"].build(names, {1: "合成工具"})
        self.assertEqual(new_names, legacy_names)
        self.assertEqual(encode_pack(rows + [name_row], digest(new_text), digest(new_names)), legacy_v3)

    def test_pack_capacity_rejected_not_raised(self):
        rows = [rec("text.flx", i, f"測{i}", "x") for i in range(65)]
        with self.assertRaisesRegex(ValueError, "65 runtime plans exceed bounded capacity 64"):
            encode_pack(rows, "0" * 64)
        many = [rec("text.flx", 0, "".join(chr(0x4E00 + i) for i in range(513)), "x")]
        with self.assertRaisesRegex(ValueError, "glyph scalars exceed"):
            encode_pack(many, "0" * 64)

    def test_frozen_snapshots_and_single_source_of_truth(self):
        self.assertEqual(frozen_issues(ROOT), [])
        records, issues, _ = load_store(ROOT / "translation/zh-TW")
        self.assertEqual([i for i in issues if i.level == "error"], [])
        snapshot = {}
        for path in FROZEN_SHA256:
            doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
            for e in doc["entries"]:
                snapshot[e["key"]] = e["target"]
        by = {r["key"]: r for r in records}
        self.assertEqual(set(snapshot), {k for k, r in by.items() if r.get("migrated_from")})
        for key, target in snapshot.items():
            if by[key]["status"] == "showcase-draft":       # untouched migrated record
                self.assertEqual(by[key]["target"], target, key)

    def test_migration_is_deterministic_and_lossless(self):
        records, _, _ = load_store(ROOT / "translation/zh-TW")
        units = {}
        for r in records:     # synthetic units carrying the recorded source identity
            units.setdefault(r["resource"], {})[r["entry_id"]] = SourceUnit(
                r["entry_id"], None, r["source_sha256"], r["source_units"], True)
        first, second = migrate(ROOT, units), migrate(ROOT, units)
        self.assertEqual(dumps_jsonl(first), dumps_jsonl(second))
        self.assertEqual(dumps_jsonl(first), b"".join(
            (ROOT / "translation/zh-TW" / f).read_bytes() for f in ("text.jsonl", "typename.jsonl", "books.jsonl")))
        self.assertEqual(len(first), 61)
        statuses = {r["status"] for r in first}
        self.assertEqual(statuses, {"showcase-draft"})
        book_record = next(r for r in first if r["resource"] == "BOOKS-EN.FLX")
        self.assertFalse(book_record["runtime_supported"])
        broken = copy.deepcopy(units)
        broken["text.flx"][4164] = SourceUnit(4164, None, "0" * 64, 129, True)
        with self.assertRaisesRegex(ValueError, "does not match local source"):
            migrate(ROOT, broken)

    def test_tracked_store_contains_no_original_source_text(self):
        for name in ("text.jsonl", "typename.jsonl", "books.jsonl"):
            for line in (ROOT / "translation/zh-TW" / name).read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertFalse({"source", "text", "english"} & set(row))
                self.assertNotRegex(row["target"], r"[A-Za-z]{3,} [a-z]{3,} [a-z]{3,} [a-z]{3,}")


class ThroughputTests(unittest.TestCase):
    """1,000 synthetic records; proves tooling scale, not translation coverage."""

    def test_one_thousand_records(self):
        n = 1000
        texts = [f"Synthetic source {i}" for i in range(n)]
        records = [rec("text.flx", i, f"合成譯文第{i}號。", texts[i], category="subtitle") for i in range(n)]
        random.Random(1).shuffle(records)
        env = Env(records, texts=texts)
        try:
            data = (env.paths.store / "text.jsonl").read_bytes()
            self.assertEqual(data.count(b"\n"), n)
            loaded, issues, _ = load_store(env.paths.store)
            self.assertEqual(([r["entry_id"] for r in loaded], issues), (list(range(n)), []))
            by_key = {r["key"]: r for r in loaded}
            self.assertEqual(by_key["text.flx:777"]["target"], "合成譯文第777號。")
            a = env.analyze()
            self.assertEqual(len(a.included["text.flx"]), n)
            self.assertEqual(sum(row["status"] == "PASS" for row in a.layout), n)
            self.assertEqual(a.glyphs["unique_scalar_count"], len(set("合成譯文第號。")))
            self.assertEqual(codes(a, "error"), ["runtime-capacity"])
            self.assertIn("1000 runtime plans exceed bounded capacity 64",
                          [i.message for i in a.issues if i.code == "runtime-capacity"])
            out, audit = ADAPTERS["text.flx"].build(env.files["text.flx"],
                                                    {r["entry_id"]: r["target"] for r in loaded})
            self.assertEqual((audit["status"], audit["changed_entry_count"]), ("PASS", n))
            again, _ = ADAPTERS["text.flx"].build(env.files["text.flx"],
                                                  {r["entry_id"]: r["target"] for r in reversed(loaded)})
            self.assertEqual(out, again)
        finally:
            env.close()


GAME = Path(os.environ.get("U9_GAME_DIR") or ROOT / ".local/runtime-game")
FONT = Path(os.environ.get("U9_CJK_FONT") or ROOT / ".local/p5-highres/font/NotoSansCJKtc-Regular.otf")
LOCAL = (GAME / "static/text.flx").exists() and FONT.exists() and os.name == "nt"


@unittest.skipUnless(LOCAL, "LOCAL-ONLY: SKIPPED WHEN ASSETS ABSENT")
class LocalShowcaseRegressionTests(unittest.TestCase):
    LEGACY = {
        "opening": (["text.flx:4164,4166-4203"],
                    {"static/text.flx": "71eea15597f45a1cfb280a5bab1239665cf1f14cc53f7968a6327e02f7de4d47",
                     "runtime/allowlist.u9ct": "3163a669749dc94ad7573bf3b2dd7cdedbac9648c64e9c374a0412bd3ff4d1dd"}),
        "npc-name": (["text.flx:4030-4052", "TYPENAME.FLX:5290"],
                     {"static/text.flx": "1f72ff74dc3876b6cb16525381fa018535ec29d147ce33c6bbb5cef041c12191",
                      "static/TYPENAME.FLX": "7a765bf78a8dd6c9fd7812bb2c347208a5ae1e04d8eea8e6152b64aab606e432",
                      "runtime/allowlist.u9ct": "54b07a817f6d2320b758bde77fcb5cc0a43ea8f35b57333039ebb86aa8b9f49c"}),
    }

    def provider(self):
        from u9cht.l10n.pipeline import load_json, metrics_from_font
        meta = load_json(CAPS)["runtime"]["font"]
        return lambda scalars: metrics_from_font(FONT, meta, sorted(scalars))

    def test_canonical_store_rebuilds_exact_historical_showcase_artifacts(self):
        for name, (only, expected) in self.LEGACY.items():
            with tempfile.TemporaryDirectory() as tmp:
                a = analyze(game_dir=GAME, metrics_provider=self.provider(), selection=parse_selection(only))
                self.assertEqual(a.errors, [], name)
                manifest = build(a, Path(tmp) / "out", GAME)
                for path, sha in expected.items():
                    self.assertEqual(manifest["files"][path], sha, (name, path))

    def test_full_development_build_and_migration_check(self):
        from u9cht.l10n.adapters import ADAPTERS as A
        from u9cht.l10n.pipeline import load_json, read_game
        game = read_game(GAME, load_json(ROOT / "translation/sources.json"), [])
        units = {r: A[r].units(d) for r, d in game.items()}
        self.assertEqual(dumps_jsonl(migrate(ROOT, units)), b"".join(
            (ROOT / "translation/zh-TW" / f).read_bytes() for f in ("text.jsonl", "typename.jsonl", "books.jsonl")))
        a = analyze(game_dir=GAME, metrics_provider=self.provider())
        self.assertEqual(a.errors, [])
        self.assertEqual((len(a.runtime), a.glyphs["unique_scalar_count"], a.glyphs["missing_glyph_count"]),
                         (60, 347, 0))
        self.assertEqual([e["key"] for e in a.excluded], ["BOOKS-EN.FLX:182"])
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build(a, Path(tmp) / "out", GAME)
            self.assertEqual(manifest["mutation_audit_status"], "PASS")
            self.assertEqual(manifest["runtime_pack_version"], 3)


if __name__ == "__main__":
    unittest.main()
