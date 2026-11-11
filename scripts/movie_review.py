"""Open one game movie in the U9Cht movie review tool, outside the game.

    python scripts/movie_review.py intro
    python scripts/movie_review.py samhayne --scale 2

Cue files are regenerated on every start (all statuses, so `review` cues are visible):
- Chinese cues from translation/zh-TW/movies.jsonl;
- optional English reference cues from LOCAL ONLY speech recognition output (.local/movie-asr/<movie>.medium.json).
Both are written under .local/movie-review/ (never tracked). Press R or F5 in the viewer after editing
translation/zh-TW/movies.jsonl and re-running this script's --cues-only mode to reload without restarting.
"""
import argparse
import configparser
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from u9cht.l10n.movies import MOVIES, load_movie_records, movie_cue_file  # noqa: E402
from u9cht.l10n.store import STATUSES  # noqa: E402

LOCAL = ROOT / ".local"


def write_cues(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    recs, problems = load_movie_records((ROOT / "translation/zh-TW/movies.jsonl").read_text(encoding="utf-8"))
    if problems:
        sys.exit("movies.jsonl problems:\n  " + "\n  ".join(problems))
    subs = out_dir / "movies.tsv"
    subs.write_bytes(movie_cue_file(recs, STATUSES))
    ref_lines = ["# LOCAL ONLY reference (speech recognition, unreviewed)"]
    for movie in MOVIES:
        p = LOCAL / "movie-asr" / f"{movie}.medium.json"
        if p.exists():
            for s in json.loads(p.read_text(encoding="utf-8")):
                words = s.get("words") or []
                start = words[0][0] if words else s["start"]
                end = words[-1][1] if words else s["end"]
                if s["text"].strip():
                    ref_lines.append(f"{movie}\t{int(start*1000)}\t{max(int(end*1000), int(start*1000)+500)}\t{s['text'].strip()}")
    ref = out_dir / "reference.tsv"
    ref.write_text("\n".join(ref_lines) + "\n", encoding="utf-8")
    return subs, ref


def default_font():
    ini = LOCAL / "p9-2" / "u9cht.ini"
    if ini.exists():
        c = configparser.ConfigParser(); c.read(ini, encoding="utf-8")
        f = c.get("font", "file", fallback="")
        if f and Path(f).exists():
            return f
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("movie", choices=MOVIES)
    ap.add_argument("--game-dir", default=str(LOCAL / "runtime-game"))
    ap.add_argument("--viewer", default=str(LOCAL / "p10-misc/build/Release/U9ChtMovieViewer.exe"))
    ap.add_argument("--font", default=None, help="CJK font file (default: [font] file of .local/p9-2/u9cht.ini)")
    ap.add_argument("--scale", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--cues-only", action="store_true", help="only regenerate the cue files (then press R in the viewer)")
    args = ap.parse_args()
    subs, ref = write_cues(LOCAL / "movie-review")
    if args.cues_only:
        print(f"cues written: {subs}"); return
    movie = Path(args.game_dir) / "Movies" / f"{args.movie}.dat"
    if not movie.exists():
        sys.exit(f"movie not found: {movie}")
    cmd = [args.viewer, str(movie), "--subs", str(subs), "--ref", str(ref), "--scale", str(args.scale)]
    font = args.font if args.font is not None else default_font()
    if font:
        cmd += ["--font", font]
    subprocess.Popen(cmd)


if __name__ == "__main__":
    main()
