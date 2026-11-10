"""Generated runtime glyph/translation pack (existing U9CTP51 v2/v3 format).

This module produces the byte format ``runtime/U9ChtRuntime/identity.cpp``
consumes. Capacity limits mirror the native limits and are enforced here, so a
pack the runtime would refuse is never built.
"""
import hashlib
import json
import random
import struct
from fractions import Fraction

from ..flx import digest

RUNTIME_CONTRACT = {
    "runtime": "U9ChtRuntime/0.2.23-p10-1",
    "magic": "U9CTP51",
    "pack_versions": {"2": "text.flx plans only", "3": "text.flx plus TYPENAME marker plans",
                      "4": "text.flx, TYPENAME and UTF-16 BOOKS-EN plans"},
    "max_plans": 16384,
    "max_plan_utf16_units": 512,
    "max_book_plan_utf16_units": 8192,
    "max_glyph_scalars": 8192,
    "glyph_cache_capacity": 16384,
    "raster_sizes_px": [20, 40],
    "logical_units_per_em": 16,
    # Runtime refuses a font unless every CJK glyph advances exactly this many units (LayoutCellUnits).
    "custom_logical_advance": 16,
    "custom_scalar_ranges": [[0x2015, 0x2015], [0x2026, 0x2026], [0x3000, 0x303F], [0x30FB, 0x30FB], [0x3400, 0x9FFF], [0xFF01, 0xFF60]],
    "native_ascii_range": [32, 126],
    "newline_allowed": {"text.flx": True, "TYPENAME.FLX": False, "BOOKS-EN.FLX": True, "misctext.flx": False},
    # Book bodies keep their source paragraph CRLF and tabs; the game's reader converts them.
    "extra_controls": {"BOOKS-EN.FLX": [9, 13]},
    "book_domain": 0x20000000,
    "name_domain": 0x10000000,
    # misctext.flx strings are matched by wide content exactly like text.flx; their plans use
    # text-domain entry IDs at this base (text.flx < 7390 slots; misctext < 348 slots).
    "misc_entry_base": 0xC000,
    # P10-1 M1: a string built by the misctext factory (constructor return 0x6161AB) carries a 4-byte marker
    # (0x8F + three base-94 digits of the plan index) before its slot string; text flows and unbounded
    # draw-string calls strip it in place.
    "misc_ui_marker": {"lead": 0x8F, "digits": 3, "base": 94, "ctor_return": 0x6161AB,
                       "strip_points": ["text_flow_init 0x5C7620", "draw_string 0x5C5C00 (unbounded)"],
                       "width_point": "string_width 0x5C6240", "drop_cap_entry": 255,
                       "message_box_inset_px": 8},
    "name_entry_max": 8191,
    "name_marker": "U9T%04X",
    "identical_text_targets_share_one_plan": True,
}


def contract_sha256(contract=RUNTIME_CONTRACT):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


BOOK_DOMAIN = RUNTIME_CONTRACT["book_domain"]
MISC_ENTRY_BASE = RUNTIME_CONTRACT["misc_entry_base"]
TEXT_DOMAIN_RESOURCES = ("text.flx", "misctext.flx")

# Above every text.flx slot and below the v3 limit of 65536 text entries.
FILLER_ENTRY_BASE = 40000


def is_custom(scalar):
    return any(lo <= scalar <= hi for lo, hi in RUNTIME_CONTRACT["custom_scalar_ranges"])


def scalar_class(scalar):
    if 0x3400 <= scalar <= 0x9FFF or 0x20000 <= scalar <= 0x3FFFF or 0xF900 <= scalar <= 0xFAFF:
        return "han"
    if scalar in (0x2015, 0x2026, 0x30FB) or 0x3000 <= scalar <= 0x303F or 0xFF01 <= scalar <= 0xFF60:
        return "punctuation"
    if 32 <= scalar <= 126 or scalar == 10:
        return "native"
    return "other"


def runtime_scalar_issues(resource, text):
    """Characters the bounded native pack cannot carry (renderer capability)."""
    bad = []
    extra = RUNTIME_CONTRACT["extra_controls"].get(resource, ())
    for ch in text:
        o = ord(ch)
        if o in extra:
            continue
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
    if values[0] != RUNTIME_CONTRACT["custom_logical_advance"]:
        raise ValueError(f"U+{scalar:04X}: logical advance {values[0]} differs from the runtime layout cell")
    return int(values[0])


def plan_entry(record):
    from .store import parse_key
    resource, entry_id = parse_key(record["key"])
    if resource == "text.flx":
        return entry_id
    if resource == "misctext.flx":
        if entry_id >= 0x1000:
            raise ValueError(f"{record['key']}: outside misctext family")
        return MISC_ENTRY_BASE + entry_id
    if resource == "TYPENAME.FLX":
        if entry_id > RUNTIME_CONTRACT["name_entry_max"]:
            raise ValueError(f"{record['key']}: outside measured name family")
        return RUNTIME_CONTRACT["name_domain"] | entry_id
    if resource == "BOOKS-EN.FLX":
        if entry_id > 0xFFFF:
            raise ValueError(f"{record['key']}: outside book family")
        return BOOK_DOMAIN | entry_id
    raise ValueError(f"{record['key']}: resource has no runtime pack domain")


def shared_text_targets(records):
    """Map each text-domain record sharing a target -> the lowest plan entry's key.

    The engine identifies text only by its exact wide string, so entries with
    identical targets are indistinguishable at runtime and share one plan.
    """
    first, shared = {}, {}
    for record in sorted((r for r in records if r["resource"] in TEXT_DOMAIN_RESOURCES), key=plan_entry):
        owner = first.setdefault(record["target"], record["key"])
        if owner != record["key"]:
            shared[record["key"]] = owner
    return shared


def capacity_issues(records, scalars):
    c = RUNTIME_CONTRACT
    problems = []
    plans = len(records) - len(shared_text_targets(records))
    if plans > c["max_plans"]:
        problems.append(f"{plans} runtime plans exceed bounded capacity {c['max_plans']}")
    if len(scalars) > c["max_glyph_scalars"]:
        problems.append(f"{len(scalars)} glyph scalars exceed bounded capacity {c['max_glyph_scalars']}")
    rasters = len(scalars) * len(c["raster_sizes_px"])
    if rasters > c["glyph_cache_capacity"]:
        problems.append(f"{rasters} prewarmed rasters exceed glyph cache capacity {c['glyph_cache_capacity']}")
    for record in records:
        units = len(record["target"].encode("utf-16-le")) // 2
        limit = c["max_book_plan_utf16_units"] if record.get("resource") == "BOOKS-EN.FLX" else c["max_plan_utf16_units"]
        if units > limit:
            problems.append(f"{record['key']}: {units} UTF-16 units exceed plan limit")
    return problems


def encode_pack(records, text_sha256, typename_sha256=None, books_sha256=None):
    """Encode v2 (text only), v3 (text + names) or v4 (text, names and books)."""
    shared = shared_text_targets(records)
    plans = sorted(((plan_entry(r), r["target"]) for r in records if r["key"] not in shared),
                   key=lambda p: p[0])
    has_names = any(e & 0xF0000000 == RUNTIME_CONTRACT["name_domain"] for e, _ in plans)
    has_books = any(e & 0xF0000000 == BOOK_DOMAIN for e, _ in plans)
    scalars = sorted({ord(ch) for _, t in plans for ch in t if ord(ch) >= 128})
    problems = capacity_issues(records, scalars)
    if problems:
        raise ValueError("; ".join(problems))
    if any(not is_custom(s) for s in scalars):
        raise ValueError("scalar outside native custom ranges")
    version = 4 if has_books else 3 if has_names else 2
    pack = bytearray(b"U9CTP51\0" + struct.pack("<II", version, len(plans)))
    pack += text_sha256.encode("ascii")
    if has_names and typename_sha256 is None:
        raise ValueError("name plans require the installed TYPENAME hash")
    if has_books and books_sha256 is None:
        raise ValueError("book plans require the installed BOOKS-EN hash")
    if version == 3:
        pack += typename_sha256.encode("ascii")
    elif version == 4:
        # v4: TYPENAME hash (64 zeros when no names are selected), then the BOOKS-EN hash.
        pack += (typename_sha256 or "0" * 64).encode("ascii") + books_sha256.encode("ascii")
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


def decode_pack(pack):
    """Parse a v2/v3 pack into (text_sha256, typename_sha256, scalars, plans)."""
    if pack[:8] != b"U9CTP51\0":
        raise ValueError("not a U9CTP51 pack")
    version, count = struct.unpack_from("<II", pack, 8)
    if version not in (2, 3, 4):
        raise ValueError(f"unsupported pack version {version}")
    text_hash = pack[16:80].decode("ascii")
    at, name_hash = 80, None
    if version >= 3:
        name_hash, at = pack[80:144].decode("ascii"), 144
    if version == 4:
        at = 208
    glyphs = struct.unpack_from("<I", pack, at)[0]
    scalars = list(struct.unpack_from(f"<{glyphs}I", pack, at + 4))
    at += 4 + glyphs * 4
    plans = []
    for _ in range(count):
        entry, units = struct.unpack_from("<II", pack, at)
        plans.append((entry, pack[at + 8:at + 8 + units * 2].decode("utf-16-le")))
        at += 8 + units * 2
    if at != len(pack):
        raise ValueError("trailing pack bytes")
    return text_hash, name_hash, scalars, plans


def capacity_stress_pack(pack, han, plan_total=None, glyph_total=None, units=40, seed=0x8000):
    """Grow a real pack to capacity with synthetic plans the game can never draw.

    Filler uses entry IDs outside every text.flx slot and text that exists in no
    game resource, so it exercises load, prewarm and lookup only. Local diagnostic
    output; never a translation.
    """
    plan_total = plan_total or RUNTIME_CONTRACT["max_plans"]
    glyph_total = glyph_total or RUNTIME_CONTRACT["max_glyph_scalars"]
    text_hash, name_hash, scalars, plans = decode_pack(pack)
    fill = plan_total - len(plans)
    extra = [ord(c) for c in han if ord(c) not in set(scalars)][:glyph_total - len(scalars)]
    if fill < 0 or len(scalars) + len(extra) != glyph_total or fill < len(extra):
        raise ValueError("cannot reach the requested capacity from these inputs")
    existing = {t for _, t in plans}
    rng = random.Random(seed)
    every = sorted(set(scalars) | set(extra))
    filler = []
    for i in range(fill):
        # Index digits keep every filler text distinct; the first scalars cover all extras.
        lead = extra[i] if i < len(extra) else every[i % len(every)]
        body = "".join(chr(rng.choice(every)) for _ in range(units - 3))
        text = chr(lead) + chr(every[i // len(every)]) + chr(every[i % len(every)]) + body
        if text in existing:
            raise ValueError("filler collided with a real plan")
        existing.add(text)
        filler.append((FILLER_ENTRY_BASE + i, text))
    out = sorted(plans + filler, key=lambda p: p[0])
    data = bytearray(b"U9CTP51\0" + struct.pack("<II", 3 if name_hash else 2, len(out)))
    data += text_hash.encode("ascii") + (name_hash.encode("ascii") if name_hash else b"")
    data += struct.pack("<I", len(every)) + struct.pack(f"<{len(every)}I", *every)
    for entry, target in out:
        raw = target.encode("utf-16-le")
        data += struct.pack("<II", entry, len(raw) // 2) + raw
    return bytes(data)


def pack_sha256(pack):
    return digest(pack)
