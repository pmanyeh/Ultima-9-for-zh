"""P8-A terminology authority: synthetic fixtures only (no game text)."""
import csv
import io
import unittest
from pathlib import Path

from u9cht.l10n import glossary as gl
from u9cht.l10n import terms as tm
from u9cht.l10n.adapters import SourceUnit

ROOT = Path(__file__).resolve().parents[1]


def unit(entry_id, text, editable=True):
    return SourceUnit(entry_id, text, "0" * 64, len(text), editable)


def text_units():
    lines = [
        (0, "\\u9\\Source\\Usecode\\ConvoLib\\Qarth\\Belmor.cpp : BEGIN FILE", False),
        (1, "Welcome, Avatar. The road to Qarth is long."),
        (2, "Hail Avatar! I am Belmor, from the Silver Keep."),
        (3, "Lord Ashen sent me. Ask Lord Ashen, not me."),
        (4, "Thou art the Avatar, are thou not? Seek the Silver Keep."),
        (5, "She wears a Copper Necklace, the fool. I sell a Copper Necklace or a fine Copper Necklace."),
        (6, "Go to the Silver Keep. Then speak with Lord Ashen and the Avatar's friend Belmor."),
    ]
    return {i: unit(i, text, *rest) for i, text, *rest in lines}


def typename_units():
    labels = {10: "Copper Ring", 11: "Gold Necklace", 12: "Silver Necklace", 13: "Apple", 14: "Apple"}
    return {i: unit(i, label) for i, label in labels.items()}


U8 = ("# comment\ncategory\tenglish\ttranslation\tstatus\tcount\texample\tnote\tannotate\n"
      "title\tAvatar\t聖者\tapproved\t1\tx\t\t\n"
      "person\tBelmor\t貝爾摩\tproposed\t1\tx\t\t\n"
      "item\tApple\t蘋果\tproposed\t1\tx\t\t\n"
      "other\tLord Ashen\t\ttodo\t1\tx\t\t\n").encode("utf-8")


class TermCollectionTests(unittest.TestCase):
    def test_names_skip_sentence_openers_and_keep_titles(self):
        self.assertEqual(list(tm.names_in("Hail Avatar! Thou art brave. Ask Lord Ashen now.")),
                         ["Avatar", "Lord Ashen"])
        self.assertEqual(list(tm.names_in("Seek the Avatar’s friend in the Silver Keep.")),
                         ["Avatar", "Silver Keep"])
        self.assertEqual(list(tm.names_in("Avatar. Britannia")), [])

    def test_sections_and_collection(self):
        units = text_units()
        self.assertEqual(tm.text_sections(units)[3], "Qarth/Belmor")
        found = tm.collect(units, typename_units(), {}, minimum=3)
        self.assertEqual(found["Avatar"]["count"], 4)
        self.assertEqual(found["Avatar"]["example"], "text.flx:1")
        self.assertEqual(found["Lord Ashen"]["category"], "person")
        self.assertEqual(found["Silver Keep"]["category"], "place")
        self.assertEqual(found["Qarth"]["category"], "place")      # region directory, one mention
        self.assertEqual(found["Belmor"]["category"], "person")    # conversation file name
        self.assertEqual(found["Copper Necklace"]["category"], "item")
        self.assertEqual(found["Apple"], {"category": "item", "count": 2, "example": "TYPENAME.FLX:13",
                                          "context": "examine label", "sample": "Apple"})
        self.assertNotIn("Thou", found)

    def test_merge_keeps_hand_edits_and_uses_u8_for_names_only(self):
        found = tm.collect(text_units(), typename_units(), {}, minimum=3)
        old = [{"source": "Belmor", "target": "貝莫", "category": "person", "status": "approved",
                "enforcement": "mandatory", "count": "1", "example": "old", "reference": "human",
                "notes": "", "annotate": "first"},
               {"source": "Gone", "target": "", "category": "other", "status": "todo",
                "enforcement": "recommended", "count": "3", "example": "text.flx:99", "reference": "scan",
                "notes": "", "annotate": ""}]
        rows = {r["source"]: r for r in tm.merge(old, found, tm.load_u8_authority(U8))}
        self.assertEqual((rows["Avatar"]["target"], rows["Avatar"]["status"]), ("聖者", "proposed"))
        self.assertEqual(rows["Avatar"]["reference"], "U8 authority.tsv (approved)")
        b = rows["Belmor"]
        self.assertEqual((b["target"], b["status"], b["reference"]), ("貝莫", "approved", "human"))
        self.assertEqual(b["notes"], "U8 proposed: 貝爾摩")
        self.assertEqual((b["annotate"], rows["Avatar"]["annotate"]), ("first", ""))
        self.assertEqual(b["example"], found["Belmor"]["example"])
        self.assertEqual((rows["Apple"]["target"], rows["Apple"]["status"]), ("", "todo"))
        self.assertEqual((rows["Lord Ashen"]["status"], rows["Lord Ashen"]["target"]), ("todo", ""))
        self.assertEqual((rows["Gone"]["count"], rows["Gone"]["example"]), ("0", "text.flx:99"))
        found["Avatars"] = dict(found["Avatar"])
        found["Avatars"]["category"] = "other"
        merged = {r["source"]: r for r in tm.merge(old, found, tm.load_u8_authority(U8))}
        plural = merged["Avatars"]
        self.assertEqual((plural["target"], plural["status"], plural["reference"], plural["category"]),
                         ("聖者", "proposed", "plural of Avatar", merged["Avatar"]["category"]))

    def test_rendered_file_is_a_valid_deterministic_glossary(self):
        found = tm.collect(text_units(), typename_units(), {}, minimum=3)
        rows = tm.merge([], found, tm.load_u8_authority(U8))
        data = tm.render_csv(rows)
        self.assertEqual(data, tm.render_csv(tm.merge([], found, tm.load_u8_authority(U8))))
        parsed, issues = gl.parse_glossary(data)
        self.assertEqual(issues + gl.glossary_issues(parsed), [])
        order = [r["category"] for r in parsed]
        self.assertEqual(order, sorted(order, key=gl.CATEGORIES.index))
        self.assertEqual(tm.render_csv(tm.merge(parsed, found, tm.load_u8_authority(U8))), data)
        review = tm.render_review(rows, found)
        self.assertIn(b"Welcome, Avatar.", review)
        self.assertNotIn(b"Welcome", data)


class AnnotationTests(unittest.TestCase):
    HEADER = ",".join(gl.COLUMNS) + "\n"
    ROWS = ("Elaina,艾蓮娜,person,approved,mandatory,,,ref,,\n"
            "Qarth,卡斯,place,approved,recommended,,,ref,,\n"
            "Avatar,聖者,title,approved,recommended,,,ref,,never\n"
            "Lycaeum,Lycaeum,place,keep,mandatory,,,ref,,\n"
            "Paws,帕斯,place,proposed,mandatory,,,ref,,\n")

    def rows(self):
        rows, issues = gl.parse_glossary((self.HEADER + self.ROWS).encode("utf-8"))
        self.assertEqual(issues, [])
        return rows

    @staticmethod
    def record(entry_id, target, terms=()):
        return {"key": f"text.flx:{entry_id}", "status": "draft", "target": target, "terms": list(terms)}

    def test_modes(self):
        rows = self.rows()
        self.assertEqual([gl.annotation_mode(r) for r in rows], ["always", "first", "never", "first", "first"])
        units = {0: unit(0, "\\u9\\Source\\Usecode\\ConvoLib\\Qarth\\Belmor.cpp : BEGIN FILE", False),
                 1: unit(1, "Elaina waits in Qarth."), 2: unit(2, "Qarth again, with Elaina."),
                 3: unit(3, "\\u9\\Source\\Usecode\\ConvoLib\\Qarth\\Ivo.cpp : BEGIN FILE", False),
                 4: unit(4, "Qarth is cold, Avatar."), 5: unit(5, "Paws and Lycaeum.")}
        sources = {f"text.flx:{i}": u.text for i, u in units.items()}
        first = gl.first_occurrences(["Qarth"], {"text.flx": units}, tm.text_sections(units))
        self.assertEqual(first, {"Qarth": {"text.flx:1", "text.flx:4"}})
        records = [self.record(1, "艾蓮娜(Elaina)在卡斯(Qarth)等候。"),
                   self.record(2, "又是卡斯，還有艾蓮娜。"),
                   self.record(4, "卡斯(Qarth)很冷，聖者(Avatar)。"),
                   self.record(5, "帕斯與 Lycaeum。")]
        got = {(i.key, i.code, i.level) for i in gl.annotation_issues(records, rows, sources, first)}
        self.assertEqual(got, {("text.flx:2", "annotation-missing", "error"),
                               ("text.flx:4", "annotation-unexpected", "warning")})
        records[1] = self.record(2, "又是卡斯(Qarth)，還有艾蓮娜(Elaina)。")
        got = {(i.key, i.code, i.level) for i in gl.annotation_issues(records, rows, sources, first)}
        self.assertIn(("text.flx:2", "annotation-unexpected", "info"), got)
        self.assertNotIn(("text.flx:2", "annotation-missing", "error"), got)
        # Without the game text, "first" cannot be decided and is not reported.
        tagged = [self.record(9, "卡斯很遠", ["Qarth"]), self.record(10, "艾蓮娜", ["Elaina"])]
        self.assertEqual([(i.key, i.code) for i in gl.annotation_issues(tagged, rows)],
                         [("text.flx:10", "annotation-missing")])


class VariantTests(unittest.TestCase):
    HEADER = ",".join(gl.COLUMNS) + "\n"

    def issues(self, body):
        rows, issues = gl.parse_glossary((self.HEADER + body).encode("utf-8"))
        self.assertEqual(issues, [])
        return [(i.code, i.key) for i in gl.glossary_issues(rows)]

    def test_declared_variants_may_share_a_target(self):
        base = ("Fireball Scroll,火球術捲軸,item,approved,recommended,,,ref,,\n"
                "Scroll: Fireball,火球術捲軸,item,approved,recommended,,,ref,{note},\n")
        self.assertEqual(self.issues(base.format(note="")), [("term-target-conflict", "火球術捲軸")])
        self.assertEqual(self.issues(base.format(note="spell; variant of Fireball Scroll")), [])
        # The variant must point at an approved row with the same target.
        self.assertEqual(self.issues(base.format(note="variant of Fire Scroll")),
                         [("glossary-variant", "Scroll: Fireball"), ("term-target-conflict", "火球術捲軸")])
        chain = base.format(note="variant of Fireball Scroll") + \
            "Fireball scroll,火球術捲軸,item,approved,recommended,,,ref,variant of Scroll: Fireball,\n"
        self.assertIn(("glossary-variant", "Fireball scroll"), self.issues(chain))

    def test_plural_hint(self):
        rows = ("Gargoyle,石像鬼,monster,approved,recommended,,,ref,,\n"
                "Gargoyles,{t},monster,approved,recommended,,,plural of Gargoyle,,\n")
        self.assertEqual(self.issues(rows.format(t="石像鬼")), [])
        # A human-chosen different target for the plural is not an error.
        self.assertEqual(self.issues(rows.format(t="石像鬼族")), [])


class CommittedAuthorityTests(unittest.TestCase):
    def test_committed_file_is_consistent(self):
        rows, issues = gl.parse_glossary((ROOT / "translation/glossary/U9_TERMS.csv").read_bytes())
        self.assertEqual(issues + gl.glossary_issues(rows), [])

    def test_committed_file_holds_no_source_sentences(self):
        data = (ROOT / "translation/glossary/U9_TERMS.csv").read_bytes()
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
        self.assertTrue(rows)
        for r in rows:
            self.assertRegex(r["example"], r"^((text\.flx|TYPENAME\.FLX|BOOKS-EN\.FLX):\d+)?$")
            self.assertLessEqual(len(r["source"]), 60)
            self.assertNotIn(":\\", r["notes"] + r["reference"])


if __name__ == "__main__":
    unittest.main()
