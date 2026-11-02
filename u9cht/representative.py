"""P6-S2 bounded text plus independently proven native item-label bridge.

TYPENAME keeps ASCII marker storage. The name namespace is deliberately separate
from text.flx IDs; the native pack checks both exact installed resource hashes.
No claim of a general legacy-byte Chinese encoding is made.
"""
import re
import struct

from .flx import digest, verify
from .showcase import validate_store, build_resource, MAX_PLANS, MAX_SCALARS
from .typename import TypeNameArchive

NAME_DOMAIN = 0x10000000


def name_marker(entry):
    if not isinstance(entry, int) or not 0 <= entry < 8192:
        raise ValueError("typename ID outside measured family")
    return f"U9T{entry:04X}"


def validate_names(doc):
    if doc.get("schema") != "u9cht-showcase-names-v1" or not doc.get("entries"):
        raise ValueError("invalid/empty inventory store")
    seen, scalars = set(), set()
    for record in doc["entries"]:
        if not re.fullmatch(r"TYPENAME\.FLX:\d+", record.get("key", "")):
            raise ValueError("invalid typename key")
        entry = int(record["key"].split(":")[1])
        name_marker(entry)
        if entry in seen:
            raise ValueError("duplicate typename ID")
        seen.add(entry)
        if "\n" in record.get("target", ""):
            raise ValueError("native item label is single-line")
        # Validate scalar/status/hash rules independently. Equal labels for
        # different native item types are legal: identity comes from the marker.
        sample = dict(record, key=f"text.flx:{entry}")
        scalars.update(validate_store({"schema": "u9cht-showcase-v1", "entries": [sample]}))
    if len(seen) > MAX_PLANS or len(scalars) > MAX_SCALARS:
        raise ValueError("bounded inventory corpus exceeded")
    return sorted(scalars)


def build_inventory(text_source, text_doc, typename_source, name_doc):
    """Build resources and a v3 pack, without writing/installing any game file."""
    text_scalars = validate_store(text_doc)
    name_scalars = validate_names(name_doc)
    if digest(typename_source) != name_doc.get("source_archive_sha256"):
        raise ValueError("pristine typename archive hash mismatch")
    text, _, text_audit = build_resource(text_source, text_doc)
    original = TypeNameArchive(typename_source)
    exported = original.export()
    records = {r["id"]: r for r in exported["entries"]}
    selected = []
    for record in name_doc["entries"]:
        entry = int(record["key"].split(":")[1])
        source = records.get(entry, {}).get("name")
        if source is None or digest(source.encode("ascii")) != record["source_sha256"]:
            raise ValueError("typename label source hash mismatch")
        records[entry]["name"] = name_marker(entry)
        selected.append(entry)
    names = original.rebuild(exported)
    rebuilt = TypeNameArchive(names)
    changed = [a.index for a, b in zip(original.entries, rebuilt.entries)
               if original.payload(a) != rebuilt.payload(b)]
    if changed != sorted(selected) or original.padding() != rebuilt.padding():
        raise ValueError("typename mutation scope/padding mismatch")
    scalars = sorted(set(text_scalars) | set(name_scalars))
    count = len(text_doc["entries"]) + len(name_doc["entries"])
    if count > MAX_PLANS or len(scalars) > MAX_SCALARS:
        raise ValueError("combined corpus capacity exceeded")
    pack = bytearray(b"U9CTP51\0" + struct.pack("<II", 3, count))
    pack += digest(text).encode("ascii") + digest(names).encode("ascii")
    pack += struct.pack("<I", len(scalars)) + struct.pack(f"<{len(scalars)}I", *scalars)
    for domain, doc in ((0, text_doc), (NAME_DOMAIN, name_doc)):
        for record in doc["entries"]:
            entry = int(record["key"].split(":")[1])
            data = record["target"].encode("utf-16-le")
            pack += struct.pack("<II", domain | entry, len(data)//2) + data
    audit = verify(typename_source, names)
    audit.update(status="EXPECTED SELECTED ASCII NAME MARKERS", changed_payload_ids=changed,
                 unselected_payloads_preserved=True, unknown_padding_preserved=True)
    return text, names, bytes(pack), {"text": text_audit, "typename": audit, "scalars": scalars}
