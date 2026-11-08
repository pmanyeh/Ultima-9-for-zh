"""Validation and deterministic build orchestration.

Pure function of inputs -> output directory. Never installs into or writes to
the original game installation; installation is a separate explicit step.
"""
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import TOOL_VERSION
from .adapters import ADAPTERS
from .glossary import (annotation_issues, annotation_mode, first_occurrences, glossary_issues,
                       parse_glossary, terminology_issues)
from .terms import text_sections
from .qa import (alias_issues, check_layout, font_issues, layout_summary, source_issues,
                 token_issues)
from .runtime_pack import (RUNTIME_CONTRACT, capacity_issues, collect_scalars, contract_sha256,
                           encode_pack, glyph_manifest, runtime_scalar_issues,
                           shared_text_targets)
from .store import RESOURCE_FILES, STATUSES, Issue, load_store, parse_key, sort_key, store_digest

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DIRS = {".local", "game", "oracle", "research-private", "private-data", "output"}
PROFILES = {
    # showcase-draft is the migrated P6-S/P6-S2 status; it ranks as draft.
    "development": ("draft", "showcase-draft", "review", "approved"),
    "approved": ("approved",),
}


@dataclass
class Paths:
    store: Path = ROOT / "translation" / "zh-TW"
    glossary: Path = ROOT / "translation" / "glossary" / "U9_TERMS.csv"
    capabilities: Path = ROOT / "translation" / "resource-capabilities.json"
    sources: Path = ROOT / "translation" / "sources.json"


@dataclass
class Analysis:
    profile: str
    records: list
    issues: list = field(default_factory=list)
    included: dict = field(default_factory=dict)       # resource -> [records]
    runtime: list = field(default_factory=list)        # runtime pack records
    excluded: list = field(default_factory=list)
    layout: list = field(default_factory=list)
    glyphs: dict | None = None
    hashes: dict = field(default_factory=dict)
    game: dict = field(default_factory=dict)            # resource -> bytes
    checks: dict = field(default_factory=dict)

    @property
    def errors(self):
        return [i for i in self.issues if i.level == "error"]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_selection(specs):
    """'text.flx:4164,4166-4203' -> {resource: set(ids)}; None means all."""
    if not specs:
        return None
    out = {}
    for spec in specs:
        resource, _, ranges = spec.rpartition(":")
        if resource not in RESOURCE_FILES or not ranges:
            raise ValueError(f"invalid selection {spec!r}")
        for part in ranges.split(","):
            lo, _, hi = part.partition("-")
            lo, hi = int(lo), int(hi or lo)
            if hi < lo:
                raise ValueError(f"invalid range {part!r}")
            out.setdefault(resource, set()).update(range(lo, hi + 1))
    return out


def read_game(game_dir, sources, issues, allow_resource_drift=False):
    game = {}
    if game_dir is None:
        return game
    for resource, meta in sources["resources"].items():
        path = Path(game_dir) / meta["path"]
        try:
            data = path.read_bytes()
        except OSError:
            issues.append(Issue("error", "missing-source-resource", resource,
                                f"cannot read {meta['path']} under the game directory"))
            continue
        observed = hashlib.sha256(data).hexdigest()
        if observed != meta["sha256"]:
            issues.append(Issue("warning" if allow_resource_drift else "error", "resource-drift", resource,
                                "resource hash differs from the recorded source baseline",
                                {"expected_sha256": meta["sha256"], "observed_sha256": observed}))
            if not allow_resource_drift:
                continue
        game[resource] = data
    return game


def metrics_from_font(font_path, font_meta, scalars):
    """Measure scalars with the hash-pinned font through the existing GDI path."""
    from ..gdi_raster import GdiRasterizer
    metrics = {}
    for em in RUNTIME_CONTRACT["raster_sizes_px"]:
        metrics[em] = {}
        with GdiRasterizer(font_path, font_meta["family"], font_meta["sha256"], em) as raster:
            for s in scalars:
                g = raster.rasterize(s)
                metrics[em][s] = {"index": g.index, "advance": g.advance,
                                  "coverage_sha256": hashlib.sha256(g.alpha).hexdigest()}
    return metrics


def _capability(capabilities, resource, name):
    return capabilities["resources"].get(resource, {}).get(name, {}).get("value", False)


def analyze(paths=None, game_dir=None, metrics_provider=None, profile="development",
            selection=None, allow_resource_drift=False):
    """Run every validation stage; select records for the requested profile."""
    paths = paths or Paths()
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    records, issues, file_hashes = load_store(paths.store)
    a = Analysis(profile=profile, records=records, issues=issues)
    a.hashes = {"canonical_store_sha256": store_digest(file_hashes) if file_hashes else None,
                "canonical_store_files": dict(sorted(file_hashes.items())),
                "glossary_sha256": sha256_file(paths.glossary),
                "capabilities_sha256": sha256_file(paths.capabilities),
                "sources_sha256": sha256_file(paths.sources),
                "runtime_contract_sha256": contract_sha256()}
    capabilities, sources = load_json(paths.capabilities), load_json(paths.sources)
    a.hashes["font_sha256"] = capabilities["runtime"]["font"]["sha256"]
    rows, gloss = parse_glossary(paths.glossary.read_bytes())
    a.issues += gloss + glossary_issues(rows)

    # Source checks (local only; English stays out of Git).
    a.game = read_game(game_dir, sources, a.issues, allow_resource_drift)
    by_key = {r["key"]: r for r in records}
    local_sources, all_units = {}, {}
    a.checks["source"] = "NOT EXECUTED (no game directory)" if game_dir is None else "EXECUTED"
    if game_dir is not None:
        for resource, data in a.game.items():
            adapter = ADAPTERS[resource]
            units = all_units[resource] = adapter.units(data)
            for record in (r for r in records if r["resource"] == resource):
                unit = units.get(record["entry_id"])
                a.issues += source_issues(record, units, adapter.unit_name)
                if unit is not None and unit.sha256 == record["source_sha256"]:
                    a.issues += token_issues(adapter, record, unit)
                    a.issues += alias_issues(record, unit, by_key)
                    if unit.text is not None:
                        local_sources[record["key"]] = unit.text
    a.issues += terminology_issues(records, rows, local_sources or None)
    first = None
    if all_units:
        first_terms = sorted(r["source"] for r in rows if r["status"] == "approved" and
                             r["target"] != r["source"] and annotation_mode(r) == "first")
        sections = text_sections(all_units["text.flx"]) if "text.flx" in all_units else {}
        first = first_occurrences(first_terms, all_units, sections)
    a.issues += annotation_issues(records, rows, local_sources or None, first)

    # Selection by profile, request, runtime capability.
    allowed = PROFILES[profile]
    for record in records:
        reason = None
        resource, entry_id = parse_key(record["key"])
        non_ascii = any(ord(ch) >= 128 for ch in record["target"])
        if record["status"] not in allowed:
            reason = f"status {record['status']} not allowed in {profile} profile"
        elif selection is not None and entry_id not in selection.get(resource, ()):
            reason = "not selected"
        elif record.get("runtime_supported") is False:
            reason = "runtime_supported=false"
        elif not _capability(capabilities, resource, "translate_build"):
            reason = "resource family has no translation build support"
        elif non_ascii and not _capability(capabilities, resource, "unicode_runtime"):
            reason = "Unicode runtime unsupported for this resource family"
        elif non_ascii and _capability(capabilities, resource, "translate_build") == "ascii-only":
            reason = "resource writer supports ASCII only"
        if reason:
            if record["status"] != "untranslated":
                a.excluded.append({"key": record["key"], "status": record["status"], "reason": reason})
            continue
        a.included.setdefault(resource, []).append(record)
        if resource == "TYPENAME.FLX" or (resource == "text.flx" and non_ascii):
            a.runtime.append(record)

    # Renderer capability and font / layout QA on what would enter the runtime.
    for record in a.runtime:
        bad = runtime_scalar_issues(record["resource"], record["target"])
        if bad:
            a.issues.append(Issue("error", "runtime-unsupported-scalar", record["key"],
                                  "scalar(s) not carried by the bounded native pack",
                                  {"scalars": [f"U+{s:04X}" for s in bad]}))
    usage = collect_scalars(a.runtime)
    for problem in capacity_issues(a.runtime, list(usage)):
        a.issues.append(Issue("error", "runtime-capacity", None, problem))
    for key, owner in sorted(shared_text_targets(a.runtime).items()):
        a.issues.append(Issue("info", "runtime-shared-target", key,
                              f"identical target to {owner}; shares its runtime plan and its evidence counters"))
    metrics = None
    if metrics_provider is not None and usage:
        metrics = metrics_provider(list(usage))
        a.issues += font_issues(usage, metrics)
        a.checks["font"] = "EXECUTED"
    else:
        a.checks["font"] = "EXECUTED (no custom scalars)" if not usage else "NOT EXECUTED (no font)"
        if usage:
            a.issues.append(Issue("warning", "font-not-checked", None,
                                  "font coverage not checked; pass the pinned font"))
    a.glyphs = glyph_manifest(a.runtime, metrics)
    profiles = capabilities["layout_profiles"]
    included_records = [r for rs in a.included.values() for r in rs]
    a.layout = [check_layout(r, profiles, metrics) for r in sorted(included_records, key=sort_key)]
    for row in a.layout:
        if row["status"] == "OVERFLOW":
            a.issues.append(Issue("error", "layout-overflow", row["key"], "; ".join(row["issues"])))
        elif row["status"] == "WARNING":
            a.issues.append(Issue("error" if profile == "approved" else "warning", "layout-warning",
                                  row["key"], "; ".join(row["issues"])))
        elif row["status"] == "UNKNOWN-LAYOUT" and profile == "approved":
            a.issues.append(Issue("error", "layout-unknown", row["key"],
                                  "approved builds require measured layout"))
    return a


def counts(records, name):
    out = {}
    for r in records:
        out[r[name]] = out.get(r[name], 0) + 1
    return dict(sorted(out.items()))


def qa_report(a):
    by_level = {"error": 0, "warning": 0, "info": 0}
    by_code = {}
    for issue in a.issues:
        by_level[issue.level] += 1
        by_code[issue.code] = by_code.get(issue.code, 0) + 1
    return {
        "schema": "u9cht-qa-report-v1",
        "profile": a.profile,
        "checks": a.checks,
        "issue_counts": by_level,
        "issue_codes": dict(sorted(by_code.items())),
        "issues": [i.as_dict() for i in a.issues],
        "records_by_status": {s: counts(a.records, "status").get(s, 0) for s in STATUSES},
        "records_by_resource": counts(a.records, "resource"),
        "included_by_resource": {r: len(v) for r, v in sorted(a.included.items())},
        "runtime_plan_count": len(a.runtime),
        "runtime_shared_target_count": len(shared_text_targets(a.runtime)),
        "excluded": a.excluded,
        "layout_counts": layout_summary(a.layout),
    }


def git_state():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit, not dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def check_output_dir(output, game_dir=None):
    target = Path(output).resolve()
    if game_dir is not None:
        game = Path(game_dir).resolve()
        if target == game or target.is_relative_to(game):
            raise ValueError("refusing to write build output inside the game installation")
    if target.is_relative_to(ROOT) and (target == ROOT or target.relative_to(ROOT).parts[0] not in PRIVATE_DIRS):
        raise ValueError("build output inside the repository must use an ignored private directory")
    if target.exists() and any(target.iterdir()):
        raise ValueError("output directory must be new or empty")
    return target


def build(a, output, game_dir=None):
    """Build resources + runtime pack in memory, then write all outputs."""
    if a.errors:
        raise ValueError(f"validation failed with {len(a.errors)} error(s); build refused")
    target = check_output_dir(output, game_dir)
    files, audits, outputs = {}, [], {}
    for resource in RESOURCE_FILES:
        records = a.included.get(resource, [])
        if not records:
            continue
        if resource not in a.game:
            raise ValueError(f"{resource}: local source resource is required to build")
        data, audit = ADAPTERS[resource].build(a.game[resource], {r["entry_id"]: r["target"] for r in records})
        audit["translated_keys"] = [r["key"] for r in records]
        audits.append(audit)
        outputs[resource] = data
        files[f"static/{resource}"] = data
    pack = None
    if a.runtime:
        text_hash = hashlib.sha256(outputs.get("text.flx", a.game.get("text.flx", b""))).hexdigest()
        if "text.flx" not in outputs and "text.flx" not in a.game:
            raise ValueError("runtime pack requires the text.flx hash")
        names = outputs.get("TYPENAME.FLX")
        pack = encode_pack(a.runtime, text_hash, hashlib.sha256(names).hexdigest() if names else None)
        files["runtime/allowlist.u9ct"] = pack
        a.glyphs["generated_pack_sha256"] = hashlib.sha256(pack).hexdigest()
    report = qa_report(a)
    files["qa/qa-report.json"] = _json(report)
    files["qa/layout-report.json"] = _json({"schema": "u9cht-layout-report-v1",
                                            "counts": report["layout_counts"], "rows": a.layout})
    files["glyph-manifest.json"] = _json(a.glyphs)
    files["mutation-audit.json"] = _json({"schema": "u9cht-mutation-audit-v1", "resources": audits})
    commit, clean = git_state()
    manifest = {
        "schema": "u9cht-build-manifest-v1",
        "tool_version": TOOL_VERSION,
        "profile": a.profile,
        "git_commit": commit,
        "git_tracked_worktree_clean": clean,
        "source_game_sha256": {r: hashlib.sha256(d).hexdigest() for r, d in sorted(a.game.items())},
        **a.hashes,
        "resource_output_sha256": {r: hashlib.sha256(d).hexdigest() for r, d in outputs.items()},
        "runtime_pack_sha256": hashlib.sha256(pack).hexdigest() if pack else None,
        "runtime_pack_version": (3 if any(r["resource"] == "TYPENAME.FLX" for r in a.runtime) else 2) if pack else None,
        "translation_counts_by_status": report["records_by_status"],
        "translation_counts_by_resource": report["records_by_resource"],
        "included_by_resource": report["included_by_resource"],
        "runtime_plan_count": len(a.runtime),
        "runtime_shared_target_count": report["runtime_shared_target_count"],
        "excluded_count": len(a.excluded),
        "glyph_counts": {k: v for k, v in a.glyphs.items() if k not in ("glyphs",)},
        "layout_qa_counts": report["layout_counts"],
        "mutation_audit_status": "PASS" if all(x["status"] == "PASS" for x in audits) else "FAIL",
        "installed": False,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["build-manifest.json"] = _json(manifest)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    return manifest
