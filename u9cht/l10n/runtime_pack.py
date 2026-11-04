"""Generated runtime glyph/translation pack (existing U9CTP51 v2/v3 format).

The native runtime (``runtime/U9ChtRuntime/identity.cpp``) is unchanged; this
module only produces the byte format it already consumes. Capacity limits are
the current bounded native limits and are enforced, never silently raised.
"""
import hashlib
import json
import struct
from fractions import Fraction

from ..flx import digest

RUNTIME_CONTRACT = {
    "runtime": "U9ChtRuntime/0.2.3-p6s2",
    "magic": "U9CTP51",
    "pack_versions": {"2": "text.flx plans only", "3": "text.flx plus TYPENAME marker plans"},
    "max_plans": 64,
    "max_plan_utf16_units": 512,
    "max_glyph_scalars": 512,
    "glyph_cache_capacity": 1024,
    "raster_sizes_px": [20, 40],
    "logical_units_per_em": 16,
    "custom_scalar_ranges": [[0x3000, 0x303F], [0x3400, 0x9FFF], [0xFF01, 0xFF60]],
    "native_ascii_range": [32, 126],
    "newline_allowed": {"text.flx": True, "TYPENAME.FLX": False},
    "name_domain": 0x10000000,
    "name_entry_max": 8191,
    "name_marker": "U9T%04X",
    "unique_text_plan_targets": True,
}


def contract_sha256(contract=RUNTIME_CONTRACT):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_custom(scalar):
    return any(lo <= scalar <= hi for lo, hi in RUNTIME_CONTRACT["custom_scalar_ranges"])


def scalar_class(scalar):
    if 0x3400 <= scalar <= 0x9FFF or 0x20000 <= scalar <= 0x3FFFF or 0xF900 <= scalar <= 0xFAFF:
        return "han"
    if 0x3000 <= scalar <= 0x303F or 0xFF01 <= scalar <= 0xFF60:
        return "punctuation"
    if 32 <= scalar <= 126 or scalar == 10:
        return "native"
    return "other"


def runtime_scalar_issues(resource, text):
    """Characters the bounded native pack cannot carry (renderer capability)."""
    bad = []
    for ch in text:
        o = ord(ch)
        if ch == "\n":
            if not RUNTIME_CONTRACT["newline_allowed"].get(resource, False):
                bad.append(o)
        elif not (32 <= o <= 126 or is_custom(o)):
            bad.append(o)
    return sorted(set(bad))


def collect_scalars(records):
    """Map each custom scalar -> sorted keys using it (deterministic)."""
    usage = {}
    for record in records:
        for ch in record["target"]:
            if ord(ch) >= 128:
                usage.setdefault(ord(ch), set()).add(record["key"])
    return {s: sorted(usage[s]) for s in sorted(usage)}


def logical_advance(metrics, scalar):
    """Exact engine logical advance; both raster sizes must agree."""
    values = []
    for em in RUNTIME_CONTRACT["raster_sizes_px"]:
        m = metrics[em].get(scalar)
        if m is None or m["index"] in (0, 0xFFFF):
            return None
        values.append(Fraction(m["advance"] * RUNTIME_CONTRACT["logical_units_per_em"], em))
    if len(set(values)) != 1 or values[0].denominator != 1 or not 1 <= values[0] <= 255:
        raise ValueError(f"U+{scalar:04X}: inconsistent/unrepresentable logical advance {values}")
    return int(values[0])


def plan_entry(record):
    from .store import parse_key
    resource, entry_id = parse_key(record["key"])
    if resource == "text.flx":
        return entry_id
    if resource == "TYPENAME.FLX":
        if entry_id > RUNTIME_CONTRACT["name_entry_max"]:
            raise ValueError(f"{record['key']}: outside measured name family")
        return RUNTIME_CONTRACT["name_domain"] | entry_id
    raise ValueError(f"{record['key']}: resource has no runtime pack domain")


def capacity_issues(records, scalars):
    c = RUNTIME_CONTRACT
    problems = []
    if len(records) > c["max_plans"]:
        problems.append(f"{len(records)} runtime plans exceed bounded capacity {c['max_plans']}")
    if len(scalars) > c["max_glyph_scalars"]:
        problems.append(f"{len(scalars)} glyph scalars exceed bounded capacity {c['max_glyph_scalars']}")
    rasters = len(scalars) * len(c["raster_sizes_px"])
    if rasters > c["glyph_cache_capacity"]:
        problems.append(f"{rasters} prewarmed rasters exceed glyph cache capacity {c['glyph_cache_capacity']}")
    for record in records:
        units = len(record["target"].encode("utf-16-le")) // 2
        if units > c["max_plan_utf16_units"]:
            problems.append(f"{record['key']}: {units} UTF-16 units exceed plan limit")
    texts = {}
    for record in records:
        if record["resource"] == "text.flx":
            if record["target"] in texts:
                problems.append(f"{record['key']}: identical runtime target to {texts[record['target']]} "
                                "(native identity would be ambiguous)")
            texts.setdefault(record["target"], record["key"])
    return problems


def encode_pack(records, text_sha256, typename_sha256=None):
    """Encode the existing v2 (text only) or v3 (text + names) pack format."""
    plans = sorted(((plan_entry(r), r["target"]) for r in records), key=lambda p: p[0])
    has_names = any(e & RUNTIME_CONTRACT["name_domain"] for e, _ in plans)
    scalars = sorted({ord(ch) for _, t in plans for ch in t if ord(ch) >= 128})
    problems = capacity_issues(records, scalars)
    if problems:
        raise ValueError("; ".join(problems))
    if any(not is_custom(s) for s in scalars):
        raise ValueError("scalar outside native custom ranges")
    version = 3 if has_names else 2
    pack = bytearray(b"U9CTP51\0" + struct.pack("<II", version, len(plans)))
    pack += text_sha256.encode("ascii")
    if has_names:
        if typename_sha256 is None:
            raise ValueError("name plans require the installed TYPENAME hash")
        pack += typename_sha256.encode("ascii")
    pack += struct.pack("<I", len(scalars)) + struct.pack(f"<{len(scalars)}I", *scalars)
    for entry, target in plans:
        data = target.encode("utf-16-le")
        pack += struct.pack("<II", entry, len(data) // 2) + data
    return bytes(pack)


def glyph_manifest(records, metrics=None):
    """Deterministic glyph manifest from the active runtime translations."""
    usage = collect_scalars(records)
    native = sorted({ord(ch) for r in records for ch in r["target"] if 32 <= ord(ch) <= 126})
    classes = {}
    for s in usage:
        classes[scalar_class(s)] = classes.get(scalar_class(s), 0) + 1
    rows, missing = [], []
    for s, keys in usage.items():
        row = {"scalar": f"U+{s:04X}", "char": chr(s), "class": scalar_class(s), "keys": keys}
        if metrics is not None:
            advance = None
            try:
                advance = logical_advance(metrics, s)
            except ValueError as error:
                row["error"] = str(error)
            if advance is None:
                missing.append(s)
            else:
                row["logical_advance"] = advance
                row["coverage_sha256"] = {str(em): metrics[em][s]["coverage_sha256"]
                                          for em in RUNTIME_CONTRACT["raster_sizes_px"]
                                          if "coverage_sha256" in metrics[em][s]}
        rows.append(row)
    sizes = len(RUNTIME_CONTRACT["raster_sizes_px"])
    return {
        "unique_scalar_count": len(usage),
        "unique_han_count": classes.get("han", 0),
        "punctuation_count": classes.get("punctuation", 0),
        "other_custom_count": classes.get("other", 0),
        "latin_native_count": len(native),
        "missing_glyph_count": len(missing) if metrics is not None else None,
        "missing_glyphs": [f"U+{s:04X}" for s in missing],
        "cache_requirement": len(usage) * sizes,
        "cache_capacity": RUNTIME_CONTRACT["glyph_cache_capacity"],
        "runtime_contract_sha256": contract_sha256(),
        "glyphs": rows,
    }


def pack_sha256(pack):
    return digest(pack)
