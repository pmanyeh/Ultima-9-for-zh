"""Bounded showcase validation/build helpers; no game installation writes."""
import re
import struct
from fractions import Fraction

from .flx import TextArchive, digest, verify

MAX_PLANS, MAX_TEXT, MAX_SCALARS, CACHE_CAPACITY = 64, 512, 512, 1024
FORBID_START = frozenset("，。、！？；：）》」』】〕〉")
FORBID_END = frozenset("（《「『【〔〈")
# A deliberately small, unambiguous diagnostic list, not an automatic converter.
# A clean result does not establish that every possible Simplified form is absent.
SIMPLIFIED_ONLY = frozenset("这们为说话请键标动开关体显览击绿应从进电脑装备剑战斗发书锁门过远够让来时图")


def validate_store(doc):
    if doc.get("schema") != "u9cht-showcase-v1" or not doc.get("entries"):
        raise ValueError("invalid/empty showcase store")
    if len(doc["entries"]) > MAX_PLANS:
        raise ValueError("too many showcase plans")
    ids, texts, scalars = set(), set(), set()
    for r in doc["entries"]:
        if not re.fullmatch(r"text\.flx:\d+", r.get("key", "")):
            raise ValueError("invalid key")
        i = int(r["key"].split(":")[1])
        if i in ids:
            raise ValueError("duplicate entry ID")
        ids.add(i)
        t = r.get("target", "")
        if not isinstance(t, str) or not t.strip() or t in texts:
            raise ValueError("empty/ambiguous target")
        texts.add(t)
        t.encode("utf-16-le", errors="strict")
        if len(t) > MAX_TEXT or any(not (32 <= ord(c) < 127 or c == "\n" or
                0x3000 <= ord(c) <= 0x303F or 0x3400 <= ord(c) <= 0x9FFF or
                0xFF01 <= ord(c) <= 0xFF60) for c in t):
            raise ValueError("unsupported Unicode/control in showcase")
        if set(t) & SIMPLIFIED_ONLY:
            raise ValueError("detectable Simplified-only form")
        if r.get("status") != "showcase-draft":
            raise ValueError("showcase-draft status required")
        if not re.fullmatch("[0-9a-f]{64}", r.get("source_sha256", "")):
            raise ValueError("source hash required")
        for line in t.split("\n"):
            if not line.strip() or line[0] in FORBID_START or line[-1] in FORBID_END:
                raise ValueError("invalid line boundary")
        scalars.update(ord(c) for c in t if ord(c) >= 128)
    if len(scalars) > MAX_SCALARS or 2*len(scalars) > CACHE_CAPACITY:
        raise ValueError("glyph-cache capacity exceeded")
    return sorted(scalars)


def logical_advances(metrics):
    """Require exact, consistent engine metrics at both measured output sizes."""
    out = {}
    for scalar in metrics["40"]:
        values = [Fraction(metrics[str(em)][scalar]["advance"]*16, em) for em in (20, 40)]
        if values[0] != values[1] or values[0].denominator != 1 or not 1 <= values[0] <= 255:
            raise ValueError("unrepresentable scalable glyph advance")
        out[int(scalar)] = int(values[0])
    return out


def width(text, advances, native_bound=16):
    # Latin stays native. This is a conservative authoring budget per native
    # ASCII character, not a claim that its actual width equals the CJK advance.
    return sum(advances[ord(c)] if ord(c) >= 128 else native_bound for c in text)


def author_breaks(text, advances, limit=528):
    """Greedy authored breaks; preserve ASCII words and basic punctuation pairs."""
    result = []
    for paragraph in text.split("\n"):
        tokens = re.findall(r"[A-Za-z0-9]+(?:[ '\-][A-Za-z0-9]+)*|.", paragraph)
        line = ""
        for token in tokens:
            if width(token, advances) > limit:
                raise ValueError("unbreakable Latin token exceeds authoring budget")
            if line and width(line+token, advances) > limit:
                # Move opening punctuation, or the character before closing
                # punctuation, onto the next line. Never split an ASCII word.
                carry = ""
                if line[-1] in FORBID_END or token[0] in FORBID_START:
                    m = re.search(r"[A-Za-z0-9]+$|.$", line)
                    carry, line = m.group(), line[:m.start()]
                if not line.strip():
                    raise ValueError("no legal authored line break")
                result.append(line.rstrip()); line = carry+token.lstrip()
            else:
                line += token
        if line.strip():
            result.append(line.rstrip())
    for line in result:
        if width(line, advances) > limit or line[0] in FORBID_START or line[-1] in FORBID_END:
            raise ValueError("authored line violates width/punctuation")
    return "\n".join(result)


def check_layout(doc, metrics, limit=528):
    scalars = validate_store(doc)
    advances = logical_advances(metrics)
    if any(s not in advances or any(metrics[str(em)][str(s)]["index"] in (0, 65535)
                                    for em in (20, 40)) for s in scalars):
        raise ValueError("missing font glyph")
    widths = {}
    for r in doc["entries"]:
        values = [width(line, advances) for line in r["target"].split("\n")]
        if max(values) > limit:
            raise ValueError("line width overflow")
        widths[r["key"]] = values
    return widths


def build_resource(source, doc):
    scalars = validate_store(doc)
    if digest(source) != doc["source_archive_sha256"]:
        raise ValueError("pristine source hash mismatch")
    archive = TextArchive(source)
    exported = archive.export()
    records = {r["id"]: r for r in exported["entries"]}
    selected = []
    for r in doc["entries"]:
        i = int(r["key"].split(":")[1])
        if i not in records or digest(records[i]["text"].encode("utf-16-le")) != r["source_sha256"]:
            raise ValueError("entry source hash mismatch")
        records[i]["text"] = r["target"]; selected.append(i)
    rebuilt = archive.rebuild(exported)
    check = TextArchive(rebuilt)
    changed = [a.index for a, b in zip(archive.entries, check.entries)
               if archive.payload(a) != check.payload(b)]
    if changed != sorted(selected) or archive.padding() != check.padding():
        raise ValueError("FLX mutation scope/padding mismatch")
    if len(archive.entries) != len(check.entries) or any(source[i] != rebuilt[i]
            for i in range(0x80) if not 0x58 <= i < 0x60):
        raise ValueError("FLX unknown header/slot change")
    sha = digest(rebuilt)
    pack = bytearray(b"U9CTP51\0" + struct.pack("<II", 2, len(selected)) + sha.encode("ascii"))
    pack += struct.pack("<I", len(scalars)) + struct.pack(f"<{len(scalars)}I", *scalars)
    for r in doc["entries"]:
        data = r["target"].encode("utf-16-le")
        pack += struct.pack("<II", int(r["key"].split(":")[1]), len(data)//2) + data
    audit = verify(source, rebuilt)
    audit.update(status="EXPECTED SELECTED SHOWCASE MUTATION", changed_payload_ids=changed,
                 unselected_payloads_preserved=True, unknown_padding_preserved=True)
    return rebuilt, bytes(pack), audit
