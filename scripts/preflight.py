"""Read-only local baseline capture. No game content or absolute paths in output."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE_NAMES = {"u9.exe", "ultima9.exe", "text.flx", "misctext.flx", "typename.flx"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture(game_dir=None, baseline=None):
    """Hash only baseline files; preserve game paths as relative identifiers."""
    result = {
        "schema": "u9cht-preflight-v1",
        "status": "BLOCKED",
        "environment": {"python": platform.python_version(), "os": platform.platform()},
        "inputs": [
            {"filename": name, "sha256": sha256(ROOT / name)}
            for name in ("AGENTS.md", "ULTIMA_IX_CHT_MASTER_PLAN.md")
        ],
        "assets": [],
        "blockers": [],
        "baseline_verified": False,
    }
    if not game_dir:
        result["blockers"].append("GAME_DIR_NOT_CONFIGURED")
        return result
    base = Path(game_dir).resolve()
    if not base.is_dir():
        result["blockers"].append("GAME_DIR_NOT_FOUND")
        return result
    # Scan only the supplied install, without following links or junctions.
    for directory, subdirs, filenames in os.walk(base, followlinks=False):
        subdirs[:] = sorted(
            name for name in subdirs
            if name != ".git"
            and not (Path(directory) / name).is_symlink()
            and not (Path(directory) / name).is_junction()
        )
        for name in sorted(filenames):
            if name.lower() not in BASELINE_NAMES and not (
                name.lower().startswith("books-") and name.lower().endswith(".flx")
            ):
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.resolve().is_relative_to(base):
                result["blockers"].append("LINKED_BASELINE_FILE")
                continue
            result["assets"].append({
                "filename": path.relative_to(base).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            })
    names = {Path(item["filename"]).name.lower() for item in result["assets"]}
    if "text.flx" not in names:
        result["blockers"].append("TEXT_FLX_NOT_FOUND")
    if not names.intersection({"u9.exe", "ultima9.exe"}):
        result["blockers"].append("GAME_EXE_NOT_FOUND")
    # Matching a recorded local baseline is distinct from certifying its patch provenance.
    if baseline is None:
        result["blockers"].append("EDITION_PATCH_AND_EXPECTED_HASHES_UNCONFIRMED")
    else:
        expected = baseline.get("assets") if isinstance(baseline, dict) else None
        if not isinstance(expected, list) or not expected:
            result["blockers"].append("INVALID_BASELINE")
        elif expected != result["assets"]:
            result["blockers"].append("STOP_BASELINE_MISMATCH")
        elif not result["blockers"]:
            result["baseline_verified"] = True
            result["status"] = "PASS WITH LIMITATIONS"
            result["warnings"] = ["LOCAL_HASH_MATCH_IS_NOT_PATCH_PROVENANCE_CERTIFICATION"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", default=os.environ.get("U9_GAME_DIR"))
    parser.add_argument("--output", type=Path, default=ROOT / ".local/preflight.json")
    parser.add_argument("--baseline", type=Path, help="previously recorded local hash baseline")
    args = parser.parse_args()
    if args.output.resolve().exists():
        parser.error("output already exists; choose a fresh output path")
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        result = capture(args.game_dir, baseline)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
    except OSError:
        print("BLOCKED: baseline file access failed", file=sys.stderr)
        return 2
    print(result["status"] + ": " + ", ".join(result["blockers"]))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
