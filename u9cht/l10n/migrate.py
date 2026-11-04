"""Deterministic one-way migration of the frozen P6-S/P6-S2 showcase stores.

Targets, keys, source hashes, speaker/context/notes and the showcase-draft
status are preserved exactly; nothing is promoted. Runtime evidence references
are copied from the committed phase report JSON, not inferred.
"""
import json
from pathlib import Path

from .store import normalize, sort_key

SHOWCASE = {
    "opening": "translation/showcase/opening.zh-TW.json",
    "gypsy": "translation/showcase/gypsy-intro.zh-TW.json",
    "inventory": "translation/showcase/inventory.zh-TW.json",
    "books": "translation/showcase/reading-books.zh-TW.json",
}
# Frozen snapshot hashes (LF-normalized bytes). These files are historical P6
# evidence consumed by the legacy builders; they must not be edited. The single
# editable source of truth after P7 is translation/zh-TW/*.jsonl.
FROZEN_SHA256 = {
    "translation/showcase/opening.zh-TW.json": "e52cb450f74a85f2eb22258b11bb92ef974a019b08dd3c991d519b42035c094a",
    "translation/showcase/gypsy-intro.zh-TW.json": "f952063f5dc4270f58e862a82077552b0a7385a51cc308dd3352313623fb5a80",
    "translation/showcase/inventory.zh-TW.json": "b3568866804f8944457cec16a430d1c554123f36c37809485d55d928582f7448",
    "translation/showcase/reading-books.zh-TW.json": "1d947ad01e16fccdbf178380491b52f840c4aff33c6c71dd48663d4985faa51b",
}


def frozen_issues(root):
    import hashlib
    problems = []
    for path, expected in FROZEN_SHA256.items():
        data = (Path(root) / path).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != expected:
            problems.append(f"{path}: frozen showcase snapshot was edited; edit translation/zh-TW instead")
    return problems


def _evidence(root):
    p6s = json.loads((root / "reports/P6S_SHOWCASE_POC.json").read_text(encoding="utf-8"))["runtime"]
    p6s2 = json.loads((root / "reports/P6S2_REPRESENTATIVE_SURFACES.json").read_text(encoding="utf-8"))
    ev = {}

    def add(key, tag):
        ev.setdefault(key, set()).add(tag)

    for i in p6s["entry_ids_composited"]:
        add(f"text.flx:{i}", "P6-S:composited")
    for i in p6s["entry_ids_visually_confirmed"]:
        add(f"text.flx:{i}", "P6-S:screenshot")
    for i in p6s2["npc_fixed_verification"]["composited_entries"]:
        add(f"text.flx:{i}", "P6-S2:composited")
    for item in p6s2["runtime_incident"]["entries"]:
        if item.get("composites", 0) > 0:       # initial npc-01 session (4030 greeting)
            add(f"text.flx:{item['id']}", "P6-S2:composited")
    for item in p6s2["matrix"][0]["visual_evidence"]:
        for i in item.get("entry_ids", []):
            add(f"text.flx:{i}", "P6-S2:screenshot")
    for row in p6s2["matrix"]:
        if row.get("surface", "").lower().startswith("inventory") and "composites" in row.get("runtime", ""):
            add("TYPENAME.FLX:5290", "P6-S2:composited")
    return ev


def _terms(target, review_terms):
    return sorted(t for t in review_terms if t in target)


def migrate(root, units):
    """``units``: resource -> {entry_id: SourceUnit} from the local original game.

    Source unit counts absent from older stores are taken from the verified
    local source; every stored source hash must match it exactly.
    """
    root = Path(root)
    docs = {name: json.loads((root / path).read_text(encoding="utf-8")) for name, path in SHOWCASE.items()}
    evidence = _evidence(root)
    records = []

    def unit_for(resource, entry_id, sha):
        unit = units[resource].get(entry_id)
        if unit is None or unit.sha256 != sha:
            raise ValueError(f"{resource}:{entry_id}: migrated source hash does not match local source")
        return unit

    for name in ("opening", "gypsy"):
        doc = docs[name]
        for e in doc["entries"]:
            entry_id = int(e["key"].split(":")[1])
            unit = unit_for("text.flx", entry_id, e["source_sha256"])
            if unit.units != e["source_utf16_units"]:
                raise ValueError(f"{e['key']}: migrated unit count mismatch")
            category = "subtitle" if name == "opening" else (
                "response" if e.get("speaker") == "Avatar" else "dialogue")
            records.append({
                "key": e["key"], "resource": "text.flx", "entry_id": entry_id,
                "status": e["status"], "category": category, "speaker": e.get("speaker"),
                "context": e.get("context"), "notes": e.get("notes"),
                "terms": _terms(e["target"], doc.get("terminology_review", [])),
                "target": e["target"], "source_sha256": e["source_sha256"],
                "source_units": e["source_utf16_units"],
                "review": {"terminology": False, "language": False, "runtime": False},
                "runtime_supported": None,
                "runtime_evidence": sorted(evidence.get(e["key"], ())),
                "migrated_from": SHOWCASE[name]})
    for e in docs["inventory"]["entries"]:
        entry_id = int(e["key"].split(":")[1])
        unit = unit_for("TYPENAME.FLX", entry_id, e["source_sha256"])
        records.append({
            "key": e["key"], "resource": "TYPENAME.FLX", "entry_id": entry_id,
            "status": e["status"], "category": "item-name", "speaker": None,
            "context": e.get("context"), "notes": e.get("notes"), "terms": [],
            "target": e["target"], "source_sha256": e["source_sha256"], "source_units": unit.units,
            "review": {"terminology": False, "language": False, "runtime": False},
            "runtime_supported": None, "runtime_evidence": sorted(evidence.get(e["key"], ())),
            "migrated_from": SHOWCASE["inventory"]})
    for e in docs["books"]["entries"]:
        entry_id = int(e["key"].split(":")[1])
        unit = unit_for("BOOKS-EN.FLX", entry_id, e["source_body_sha256"])
        records.append({
            "key": e["key"], "resource": "BOOKS-EN.FLX", "entry_id": entry_id,
            "status": e["status"], "category": "book", "speaker": None,
            "context": e.get("context"),
            "notes": "Unicode book route unverified; kept out of runtime builds",
            "terms": [], "target": e["target"], "source_sha256": e["source_body_sha256"],
            "source_units": unit.units,
            "review": {"terminology": False, "language": False, "runtime": False},
            "runtime_supported": False, "runtime_evidence": [],
            "migrated_from": SHOWCASE["books"]})
    keys = [r["key"] for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate keys across showcase stores")
    return sorted((normalize(r) for r in records), key=sort_key)
