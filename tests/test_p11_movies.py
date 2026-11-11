"""P11 movie subtitle records (synthetic data only)."""
import json
import unittest
from pathlib import Path

from u9cht.l10n.movies import load_movie_records, movie_cue_file

ROOT = Path(__file__).resolve().parents[1]


def row(movie, n, start, end, target="合成字幕", status="draft"):
    return json.dumps({"key": f"movies:{movie}:{n:02d}", "movie": movie, "start_ms": start, "end_ms": end,
                       "status": status, "target": target, "notes": ""}, ensure_ascii=False)


class MovieSubtitleTests(unittest.TestCase):
    def test_valid_records_and_cue_file(self):
        recs, problems = load_movie_records("\n".join([row("intro", 2, 5000, 6000, "第二\n行"), row("intro", 1, 1000, 2000),
                                                       row("ambush", 1, 0, 900, status="review")]))
        self.assertEqual(problems, [])
        data = movie_cue_file(recs, ("draft",)).decode("utf-8").splitlines()
        self.assertEqual(data[1:], ["intro\t1000\t2000\t合成字幕", "intro\t5000\t6000\t第二\\n行"])
        self.assertIn("ambush\t0\t900\t合成字幕", movie_cue_file(recs, ("draft", "review")).decode("utf-8"))

    def test_rejections(self):
        bad = [row("intro", 1, 2000, 1000), row("nosuch", 1, 0, 10), row("intro", 3, 0, 10, ""),
               row("intro", 4, 0, 10, "This text contains english words"), row("intro", 5, 0, 10, status="done"),
               json.dumps({"key": "movies:intro:06", "movie": "intro"})]
        recs, problems = load_movie_records("\n".join(bad))
        self.assertEqual(recs, [])
        self.assertEqual(len(problems), 6)
        recs, problems = load_movie_records("\n".join([row("raven", 1, 0, 3000), row("raven", 2, 2500, 4000)]))
        self.assertTrue(any("overlaps" in p for p in problems))

    def test_tracked_movie_store_is_valid_and_has_no_english_prose(self):
        path = ROOT / "translation/zh-TW/movies.jsonl"
        recs, problems = load_movie_records(path.read_text(encoding="utf-8"))
        self.assertEqual(problems, [])
        self.assertTrue(recs)
        for r in recs:
            self.assertNotIn("source", r)
