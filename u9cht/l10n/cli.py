"""Command-line entry points for the P7 localization pipeline."""
import argparse
import json
import os
import sys
from pathlib import Path

from .adapters import ADAPTERS
from .pipeline import (PRIVATE_DIRS, ROOT, Paths, analyze, build, load_json, metrics_from_font,
                       parse_selection, qa_report, read_game)
from .store import Issue, dumps_jsonl, load_store

LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}


def _game_dir(value):
    value = value or os.environ.get("U9_GAME_DIR")
    return Path(value) if value else None


def _font(value):
    value = value or os.environ.get("U9_CJK_FONT")
    return Path(value) if value else None


def _private(path):
    target = Path(path).resolve()
    if target.is_relative_to(ROOT) and (target == ROOT or target.relative_to(ROOT).parts[0] not in PRIVATE_DIRS):
        raise SystemExit("FAIL: local outputs inside the repository must use an ignored private directory (.local/)")
    return target


def _provider(font, paths):
    if font is None:
        return None
    meta = load_json(paths.capabilities)["runtime"]["font"]
    return lambda scalars: metrics_from_font(font, meta, sorted(scalars))


def _print_issues(issues, limit):
    shown = sorted(issues, key=lambda i: (LEVEL_ORDER[i.level], i.code, i.key or ""))
    for issue in shown[:limit]:
        print(f"  {issue.level.upper():7} {issue.code:32} {issue.key or '-'}: {issue.message}")
    if len(shown) > limit:
        print(f"  ... {len(shown) - limit} more (see report)")


def _summary(a, report):
    print(f"profile:  {a.profile}")
    print(f"records:  {len(a.records)}  " +
          "  ".join(f"{k}={v}" for k, v in report["records_by_status"].items() if v))
    print(f"checks:   source={a.checks.get('source')}  font={a.checks.get('font')}")
    c = report["issue_counts"]
    print(f"issues:   errors={c['error']}  warnings={c['warning']}  info={c['info']}")
    lc = report["layout_counts"]
    print(f"layout:   PASS: {lc['PASS']:5}  WARNING: {lc['WARNING']:4}  OVERFLOW: {lc['OVERFLOW']:4}  "
          f"UNKNOWN: {lc['UNKNOWN-LAYOUT']:4}")
    g = a.glyphs
    print(f"glyphs:   scalars={g['unique_scalar_count']}  han={g['unique_han_count']}  "
          f"punct={g['punctuation_count']}  latin/native={g['latin_native_count']}  "
          f"missing={g['missing_glyph_count']}  cache={g['cache_requirement']}/{g['cache_capacity']}")
    print(f"selected: runtime plans={report['runtime_plan_count']}  excluded={len(report['excluded'])}")


def cmd_validate(args):
    from .migrate import frozen_issues
    paths = Paths()
    a = analyze(paths, _game_dir(args.game_dir), _provider(_font(args.font), paths), args.profile,
                parse_selection(args.only), args.allow_resource_drift)
    a.issues += [Issue("error", "frozen-snapshot-edited", None, p) for p in frozen_issues(ROOT)]
    report = qa_report(a)
    out = _private(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "qa-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "layout-report.json").write_text(json.dumps({"schema": "u9cht-layout-report-v1",
                                                        "counts": report["layout_counts"], "rows": a.layout},
                                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "glyph-manifest.json").write_text(json.dumps(a.glyphs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("U9-CHT translation validation")
    _summary(a, report)
    _print_issues(a.issues, args.max_issues)
    print("RESULT:   " + ("FAIL" if a.errors else "PASS"))
    return 1 if a.errors else 0


def cmd_build(args):
    paths = Paths()
    game = _game_dir(args.game_dir)
    font = _font(args.font)
    if game is None or font is None:
        raise SystemExit("FAIL: build requires --game-dir/U9_GAME_DIR and --font/U9_CJK_FONT")
    a = analyze(paths, game, _provider(font, paths), args.profile, parse_selection(args.only))
    report = qa_report(a)
    print("U9-CHT localization build")
    _summary(a, report)
    if a.errors:
        _print_issues(a.issues, args.max_issues)
        print("RESULT:   BUILD REFUSED (validation errors)")
        return 1
    manifest = build(a, _private(args.output), game)
    print(f"outputs:  {', '.join(sorted(manifest['files']))}")
    print(f"pack:     {manifest['runtime_pack_sha256']}")
    for resource, sha in manifest["resource_output_sha256"].items():
        print(f"resource: {resource} {sha}")
    print(f"audit:    {manifest['mutation_audit_status']}")
    print("RESULT:   PASS (not installed; installation is a separate explicit step)")
    return 0


def cmd_export(args):
    from .workset import export_workset
    paths = Paths()
    game_dir = _game_dir(args.game_dir)
    if game_dir is None:
        raise SystemExit("FAIL: export requires --game-dir or U9_GAME_DIR")
    issues = []
    game = read_game(game_dir, load_json(paths.sources), issues)
    if any(i.level == "error" for i in issues):
        _print_issues(issues, 20)
        return 1
    if args.resource:
        game = {r: d for r, d in game.items() if r in args.resource}
    records, problems, _ = load_store(paths.store)
    if any(i.level == "error" for i in problems):
        _print_issues(problems, 20)
        return 1
    files, manifest = export_workset(records, game, parse_selection(args.only), not args.existing_only)
    out = _private(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for resource, data in files.items():
        path = out / f"{resource}.work.jsonl"
        if path.exists() and not args.overwrite:
            raise SystemExit(f"FAIL: {path.name} exists; pass --overwrite")
        path.write_bytes(data)
    (out / "workset-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for resource, meta in manifest["resources"].items():
        print(f"exported {meta['rows']:6} rows  {resource}  (LOCAL ONLY: contains original English)")
    return 0


def cmd_import(args):
    from .workset import import_workset, read_workset_files, write_records
    paths = Paths()
    records, problems, _ = load_store(paths.store)
    if any(i.level == "error" for i in problems):
        _print_issues(problems, 20)
        return 1
    rows, parse = read_workset_files(args.workset)
    if parse:
        _print_issues(parse, 20)
        return 1
    game = {}
    game_dir = _game_dir(args.game_dir)
    if game_dir is not None:
        issues = []
        game = read_game(game_dir, load_json(paths.sources), issues)
        if any(i.level == "error" for i in issues):
            _print_issues(issues, 20)
            return 1
    updated, report = import_workset(records, rows, game, args.create, args.allow_status_regression, args.force)
    print(json.dumps({k: report[k] for k in ("status", "rows")} |
                     {"changes": len(report["changes"]), "conflicts": report["conflicts"]},
                     ensure_ascii=False, indent=2))
    if report["conflicts"]:
        print("RESULT: CONFLICT - canonical store not modified")
        return 1
    if args.dry_run:
        print("RESULT: dry run - canonical store not modified")
        return 0
    write_records(paths.store, updated)
    print(f"RESULT: imported {len(report['changes'])} change(s)")
    return 0


def cmd_migrate(args):
    from .migrate import frozen_issues, migrate
    paths = Paths()
    game_dir = _game_dir(args.game_dir)
    if game_dir is None:
        raise SystemExit("FAIL: migration requires --game-dir or U9_GAME_DIR (source verification)")
    problems = frozen_issues(ROOT)
    if problems:
        raise SystemExit("FAIL: " + "; ".join(problems))
    issues = []
    game = read_game(game_dir, load_json(paths.sources), issues)
    if any(i.level == "error" for i in issues):
        _print_issues(issues, 20)
        return 1
    units = {r: ADAPTERS[r].units(d) for r, d in game.items()}
    records = migrate(ROOT, units)
    expected = {f: dumps_jsonl([r for r in records if r["resource"] == res])
                for res, f in (("text.flx", "text.jsonl"), ("TYPENAME.FLX", "typename.jsonl"),
                               ("BOOKS-EN.FLX", "books.jsonl"))}
    if args.check:
        differs = [f for f, data in expected.items()
                   if not (paths.store / f).exists() or (paths.store / f).read_bytes() != data]
        print(f"migrated {len(records)} records; canonical store " + ("DIFFERS: " + ", ".join(differs) if differs else "matches"))
        return 1 if differs else 0
    if any((paths.store / f).exists() for f in expected) and not args.force:
        raise SystemExit("FAIL: canonical store exists; migration is one-way (use --check, or --force to re-create)")
    paths.store.mkdir(parents=True, exist_ok=True)
    for f, data in expected.items():
        (paths.store / f).write_bytes(data)
    print(f"migrated {len(records)} records into translation/zh-TW")
    return 0


def cmd_terms(args):
    """Refresh the authority file from the game text; hand-edited fields are kept."""
    from .glossary import parse_glossary
    from . import terms as tm
    paths = Paths()
    game_dir = _game_dir(args.game_dir)
    if game_dir is None:
        raise ValueError("terms needs --game-dir or U9_GAME_DIR (local original resources)")
    issues = []
    game = read_game(game_dir, load_json(paths.sources), issues)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        _print_issues(errors, args.max_issues)
        return 1
    units = {name: ADAPTERS[name].units(data) for name, data in game.items()}
    collected = tm.collect(units["text.flx"], units["TYPENAME.FLX"], units["BOOKS-EN.FLX"], args.minimum)
    old, gloss = parse_glossary(paths.glossary.read_bytes())
    if [i for i in gloss if i.level == "error"]:
        _print_issues(gloss, args.max_issues)
        return 1
    u8_path = args.u8_authority or os.environ.get("U8_AUTHORITY")
    u8 = tm.load_u8_authority(Path(u8_path).read_bytes()) if u8_path else {}
    rows = tm.merge(old, collected, u8)
    data = tm.render_csv(rows)
    if args.check:
        current = paths.glossary.read_bytes().replace(b"\r\n", b"\n")
        print("PASS: authority file is current" if current == data else "FAIL: authority file is stale")
        return 0 if current == data else 1
    paths.glossary.write_bytes(data)
    if args.review:
        review = _private(args.review)
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_bytes(tm.render_review(rows, collected, u8))
        print(f"review:   {review} (LOCAL ONLY: contains source sentences)")
    s = tm.summary(rows)
    print(f"terms:    {s['terms']}  u8 rows loaded: {len(u8)}")
    print("category: " + "  ".join(f"{k}={v}" for k, v in s["by_category"].items()))
    print("status:   " + "  ".join(f"{k}={v}" for k, v in s["by_status"].items()))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="u9cht-l10n", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="aggregate structural/source/language/terminology/font/layout QA")
    v.add_argument("--game-dir")
    v.add_argument("--font")
    v.add_argument("--profile", default="development", choices=("development", "approved"))
    v.add_argument("--only", action="append")
    v.add_argument("--allow-resource-drift", action="store_true")
    v.add_argument("--report-dir", default=str(ROOT / ".local" / "qa"))
    v.add_argument("--max-issues", type=int, default=40)
    v.set_defaults(func=cmd_validate)

    b = sub.add_parser("build", help="deterministic build into a private output directory")
    b.add_argument("--game-dir")
    b.add_argument("--font")
    b.add_argument("--language", default="zh-TW", choices=("zh-TW",))
    b.add_argument("--profile", default="development", choices=("development", "approved"))
    b.add_argument("--only", action="append", help="e.g. text.flx:4164,4166-4203 (repeatable)")
    b.add_argument("--output", required=True)
    b.add_argument("--max-issues", type=int, default=40)
    b.set_defaults(func=cmd_build)

    e = sub.add_parser("export-workset", help="create a LOCAL ONLY translator workset")
    e.add_argument("--game-dir")
    e.add_argument("--language", default="zh-TW", choices=("zh-TW",))
    e.add_argument("--resource", action="append", choices=tuple(ADAPTERS))
    e.add_argument("--only", action="append")
    e.add_argument("--existing-only", action="store_true", help="only keys already in the canonical store")
    e.add_argument("--output", required=True)
    e.add_argument("--overwrite", action="store_true")
    e.set_defaults(func=cmd_export)

    i = sub.add_parser("import-workset", help="merge a translated workset into the canonical store")
    i.add_argument("workset", nargs="+")
    i.add_argument("--game-dir")
    i.add_argument("--create", action="store_true", help="allow keys absent from the canonical store")
    i.add_argument("--allow-status-regression", action="store_true")
    i.add_argument("--force", action="store_true", help="allow overwriting approved targets")
    i.add_argument("--dry-run", action="store_true")
    i.set_defaults(func=cmd_import)

    m = sub.add_parser("migrate-showcase", help="one-way deterministic migration of frozen P6 stores")
    m.add_argument("--game-dir")
    m.add_argument("--check", action="store_true")
    m.add_argument("--force", action="store_true")
    m.set_defaults(func=cmd_migrate)

    t = sub.add_parser("terms", help="refresh U9_TERMS.csv candidates from the game text (hand edits kept)")
    t.add_argument("--game-dir")
    t.add_argument("--u8-authority", help="Ultima VIII authority.tsv for series names (or U8_AUTHORITY)")
    t.add_argument("--review", help="LOCAL ONLY review TSV with one source sentence per term (.local/...)")
    t.add_argument("--minimum", type=int, default=3, help="mid-sentence occurrences needed for a text name")
    t.add_argument("--check", action="store_true", help="exit 1 if the committed file would change")
    t.add_argument("--max-issues", type=int, default=40)
    t.set_defaults(func=cmd_terms)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as error:
        message = "file access failed" if isinstance(error, OSError) else str(error)
        print("FAIL: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
