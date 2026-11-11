"""P11 movie subtitles: translation/zh-TW/movies.jsonl -> runtime/movies.tsv.

Each record is one subtitle cue of one movie (Movies/<movie>.dat). The store keeps only the Chinese text and the
timing; English transcripts stay local (LOCAL ONLY ASR output under .local/). The runtime (runtime/U9ChtMovie)
reads the generated cue file next to the runtime pack.
"""
import json
import re

from .store import STATUSES

MOVIES = ("ambush", "armageddon", "column", "goodendgame", "intro", "maelstrom", "moongate", "prison",
          "pyros", "raven", "samhayne", "skarabrae")
FIELDS = ("key", "movie", "start_ms", "end_ms", "status", "target", "notes")
KEY = re.compile(r"^movies:([a-z]+):(\d{2})$")
ENGLISH_PROSE = re.compile(r"[A-Za-z]{3,} [a-z]{3,} [a-z]{3,} [a-z]{3,}")


def load_movie_records(data):
    """Parse and validate the JSONL text. Returns (records, problems)."""
    records, problems = [], []
    for n, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            problems.append(f"line {n}: invalid JSON ({e.msg})")
            continue
        if not isinstance(r, dict) or set(r) != set(FIELDS):
            problems.append(f"line {n}: fields must be exactly {', '.join(FIELDS)}")
            continue
        m = KEY.match(r["key"]) if isinstance(r["key"], str) else None
        if not m or m.group(1) != r["movie"] or r["movie"] not in MOVIES:
            problems.append(f"line {n}: key/movie mismatch or unknown movie")
            continue
        if not (isinstance(r["start_ms"], int) and isinstance(r["end_ms"], int) and 0 <= r["start_ms"] < r["end_ms"]):
            problems.append(f"{r['key']}: invalid time range")
            continue
        if r["status"] not in STATUSES:
            problems.append(f"{r['key']}: unknown status {r['status']!r}")
            continue
        t = r["target"]
        if not isinstance(t, str) or not t.strip() or "\t" in t or "\r" in t or ENGLISH_PROSE.search(t):
            problems.append(f"{r['key']}: target must be non-empty Chinese text without tabs, CR or English prose")
            continue
        records.append(r)
    keys = [r["key"] for r in records]
    if len(keys) != len(set(keys)):
        problems.append("duplicate keys")
    by_movie = {}
    for r in records:
        by_movie.setdefault(r["movie"], []).append(r)
    for movie, cues in by_movie.items():
        cues.sort(key=lambda r: r["start_ms"])
        for a, b in zip(cues, cues[1:]):
            if b["start_ms"] < a["end_ms"]:
                problems.append(f"{b['key']}: overlaps {a['key']}")
    return records, problems


def movie_cue_file(records, statuses):
    """UTF-8 cue file text (runtime/U9ChtMovie/subtitles.h format) for records whose status is in `statuses`."""
    lines = ["# U9-CHT movie subtitles (generated from translation/zh-TW/movies.jsonl)"]
    for r in sorted(records, key=lambda r: (r["movie"], r["start_ms"])):
        if r["status"] in statuses:
            lines.append(f"{r['movie']}\t{r['start_ms']}\t{r['end_ms']}\t{r['target'].replace(chr(10), chr(92) + 'n')}")
    return ("\n".join(lines) + "\n").encode("utf-8")
