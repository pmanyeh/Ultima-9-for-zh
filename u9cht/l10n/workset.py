"""Local translator worksets (LOCAL ONLY: they contain original English).

Export merges the user's lawful local source with canonical targets. Import is
all-or-nothing: any conflict aborts with a deterministic report and no writes.
"""
import hashlib
import json
from pathlib import Path

from .adapters import ADAPTERS
from .store import (RESOURCE_FILES, STATUS_RANK, dumps_jsonl, make_key, normalize, parse_jsonl,
                    record_revision, sort_key, validate_record)

WORK_FIELDS = ("key", "resource", "entry_id", "source", "source_sha256", "source_units",
               "status", "category", "speaker", "context", "notes", "terms", "target", "review",
               "base_revision")
EDITABLE = ("status", "category", "speaker", "context", "notes", "terms", "target", "review")
DEFAULT_CATEGORY = {"text.flx": "dialogue", "TYPENAME.FLX": "item-name", "BOOKS-EN.FLX": "book"}


def export_workset(records, game, selection=None, include_untranslated=True):
    """Return {resource: jsonl bytes} plus a manifest. ``game``: resource -> bytes."""
    by_key = {r["key"]: r for r in records}
    out, manifest = {}, {"schema": "u9cht-workset-v1", "local_only": True, "resources": {}}
    for resource, data in game.items():
        units = ADAPTERS[resource].units(data)
        rows = []
        for entry_id, unit in sorted(units.items()):
            if not unit.editable:
                continue
            if selection is not None and entry_id not in selection.get(resource, ()):
                continue
            key = make_key(resource, entry_id)
            canonical = by_key.get(key)
            if canonical is None and not include_untranslated:
                continue
            row = {"key": key, "resource": resource, "entry_id": entry_id, "source": unit.text,
                   "source_sha256": unit.sha256, "source_units": unit.units}
            if canonical is not None:
                if canonical["source_sha256"] != unit.sha256:
                    row["source_drift"] = {"expected": canonical["source_sha256"], "observed": unit.sha256}
                base = normalize(canonical)
                row.update({k: base[k] for k in EDITABLE})
                row["base_revision"] = record_revision(canonical)
            else:
                row.update({"status": "untranslated", "category": DEFAULT_CATEGORY[resource],
                            "speaker": None, "context": None, "notes": None, "terms": [],
                            "target": "", "review": {"terminology": False, "language": False,
                                                     "runtime": False},
                            "base_revision": None})
            rows.append({k: row[k] for k in WORK_FIELDS} | ({"source_drift": row["source_drift"]}
                                                             if "source_drift" in row else {}))
        out[resource] = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for r in rows).encode("utf-8")
        manifest["resources"][resource] = {"source_sha256": hashlib.sha256(data).hexdigest(),
                                           "rows": len(rows)}
    return out, manifest


def import_workset(records, work_rows, game=None, create=False, allow_status_regression=False,
                   force=False):
    """Merge workset rows into canonical records.

    Returns (new_records, report). ``report['conflicts']`` non-empty means the
    caller must not write anything.
    """
    by_key = {r["key"]: r for r in records}
    conflicts, changes, seen = [], [], set()
    units = {res: ADAPTERS[res].units(data) for res, data in (game or {}).items()}
    updated = dict(by_key)
    for row in work_rows:
        key = row.get("key")
        if not isinstance(key, str):
            conflicts.append({"key": None, "reason": "row without key"})
            continue
        if key in seen:
            conflicts.append({"key": key, "reason": "duplicate key in workset"})
            continue
        seen.add(key)
        unknown = sorted(set(row) - set(WORK_FIELDS) - {"source_drift"})
        if unknown:
            conflicts.append({"key": key, "reason": f"unknown workset fields {unknown}"})
            continue
        current = by_key.get(key)
        resource = row.get("resource")
        if resource in units:
            unit = units[resource].get(row.get("entry_id"))
            if unit is None or unit.sha256 != row.get("source_sha256"):
                conflicts.append({"key": key, "reason": "workset source hash does not match local source (SOURCE DRIFT)"})
                continue
        if current is None:
            if row.get("status") == "untranslated" and not row.get("target"):
                continue        # untouched new row: nothing to import
            if not create:
                conflicts.append({"key": key, "reason": "unknown key; use explicit create mode"})
                continue
            if resource not in units:
                conflicts.append({"key": key, "reason": "create mode requires the local source resource"})
                continue
            candidate = {"key": key, "resource": resource, "entry_id": row.get("entry_id"),
                         "source_sha256": row.get("source_sha256"), "source_units": row.get("source_units")}
            candidate.update({k: row.get(k) for k in EDITABLE})
        else:
            if row.get("source_sha256") != current["source_sha256"] or \
                    row.get("source_units") != current["source_units"]:
                conflicts.append({"key": key, "reason": "source hash/units differ from canonical record"})
                continue
            base = normalize(current)
            if all(row.get(k) == base[k] for k in EDITABLE):
                continue        # no change
            if row.get("base_revision") != record_revision(current):
                conflicts.append({"key": key, "reason": "canonical record changed since workset export "
                                                       "(refusing to overwrite newer canonical data)"})
                continue
            old, new = current["status"], row.get("status")
            if old in STATUS_RANK and new in STATUS_RANK and STATUS_RANK[new] < STATUS_RANK[old] \
                    and not allow_status_regression:
                conflicts.append({"key": key, "reason": f"status regression {old} -> {new} requires --allow-status-regression"})
                continue
            if old == "approved" and new != "approved" and row.get("target") != current["target"] and not force:
                conflicts.append({"key": key, "reason": "approved translation cannot be overwritten by a "
                                                       f"{new} target without --force"})
                continue
            candidate = dict(base)
            candidate.update({k: row.get(k) for k in EDITABLE})
        problems = [i for i in validate_record(candidate, resource) if i.level == "error"]
        if problems:
            conflicts.append({"key": key, "reason": "invalid record: " + "; ".join(p.message for p in problems)})
            continue
        updated[key] = normalize(candidate)
        changes.append({"key": key, "action": "create" if current is None else "update",
                        "status": f"{current['status'] if current else '-'} -> {candidate['status']}",
                        "target_changed": current is None or current["target"] != candidate["target"]})
    conflicts.sort(key=lambda c: (c["key"] or "", c["reason"]))
    changes.sort(key=lambda c: c["key"])
    report = {"schema": "u9cht-workset-import-v1", "rows": len(work_rows), "changes": changes,
              "conflicts": conflicts, "status": "CONFLICT" if conflicts else "OK"}
    return sorted(updated.values(), key=sort_key), report


def read_workset_files(paths):
    rows, issues = [], []
    for path in paths:
        parsed, problems = parse_jsonl(Path(path).read_bytes(), Path(path).name)
        rows += parsed
        issues += problems
    return rows, issues


def write_records(directory, records):
    directory = Path(directory)
    for resource, filename in RESOURCE_FILES.items():
        (directory / filename).write_bytes(dumps_jsonl([r for r in records if r["resource"] == resource]))
