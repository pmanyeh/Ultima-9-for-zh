"""Canonical translation records: schema rules, keys and deterministic JSONL.

One logical record per line, sorted by (resource, entry_id), fixed field order,
UTF-8 without BOM, LF line endings. Original English is never stored here;
identity is resource + entry ID + exact source SHA-256 + source unit count.
"""
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

RESOURCE_FILES = {"text.flx": "text.jsonl", "TYPENAME.FLX": "typename.jsonl",
                  "BOOKS-EN.FLX": "books.jsonl"}
RESOURCE_ORDER = tuple(RESOURCE_FILES)
KEY_RE = re.compile(r"(text\.flx|TYPENAME\.FLX|BOOKS-EN\.FLX):(0|[1-9][0-9]{0,5})")

STATUSES = ("untranslated", "draft", "review", "approved", "blocked", "showcase-draft")
# showcase-draft exists only for migrated P6-S/P6-S2 work; it ranks as draft.
STATUS_RANK = {"untranslated": 0, "draft": 1, "showcase-draft": 1, "review": 2, "approved": 3}
CATEGORIES = ("subtitle", "dialogue", "response", "item-name", "book", "journal",
              "ui", "system", "other")
REVIEW_KEYS = ("terminology", "language", "runtime")

FIELDS = ("key", "resource", "entry_id", "status", "category", "speaker", "context",
          "notes", "terms", "target", "source_sha256", "source_units", "review",
          "runtime_supported", "runtime_evidence", "migrated_from")
REQUIRED = ("key", "resource", "entry_id", "status", "category", "target",
            "source_sha256", "source_units", "review")
OPTIONAL_DEFAULTS = {"speaker": None, "context": None, "notes": None, "terms": [],
                     "runtime_supported": None, "runtime_evidence": [],
                     "migrated_from": None}

# Deliberately small diagnostic list of Simplified-only forms; never a converter.
# A clean result does not prove that no Simplified form is present.
SIMPLIFIED_ONLY = frozenset(
    "这们为说话请键标动开关体显览击绿应从进电脑装备剑战斗发书锁门过远够让来时图"
    "对个国会学没样还当东边见间问现长队乐听写给头经买卖认识转务导师")


@dataclass(frozen=True)
class Issue:
    level: str          # error | warning | info
    code: str
    key: str | None
    message: str
    data: dict = field(default_factory=dict)

    def as_dict(self):
        out = {"level": self.level, "code": self.code, "key": self.key, "message": self.message}
        if self.data:
            out["data"] = self.data
        return out


def parse_key(key):
    m = KEY_RE.fullmatch(key) if isinstance(key, str) else None
    if not m:
        raise ValueError(f"invalid canonical key: {key!r}")
    return m.group(1), int(m.group(2))


def make_key(resource, entry_id):
    key = f"{resource}:{entry_id}"
    parse_key(key)
    return key


def sort_key(record):
    return (RESOURCE_ORDER.index(record["resource"]), record["entry_id"])


def normalize(record):
    """Return the record with fixed field order and explicit optional defaults."""
    out = {}
    for name in FIELDS:
        if name in record:
            value = record[name]
        elif name in OPTIONAL_DEFAULTS:
            value = OPTIONAL_DEFAULTS[name]
            value = list(value) if isinstance(value, list) else value
        else:
            continue
        if name == "review" and isinstance(value, dict):
            value = {k: value[k] for k in REVIEW_KEYS if k in value} | \
                    {k: v for k, v in value.items() if k not in REVIEW_KEYS}
        out[name] = value
    for name in record:
        if name not in out:
            out[name] = record[name]   # unknown fields survive so validation can report them
    return out


def dumps_record(record):
    return json.dumps(normalize(record), ensure_ascii=False, separators=(",", ":"))


def dumps_jsonl(records):
    rows = sorted((normalize(r) for r in records), key=sort_key)
    return "".join(dumps_record(r) + "\n" for r in rows).encode("utf-8")


def record_revision(record):
    """Stable fingerprint of one canonical record (used for workset conflicts)."""
    return hashlib.sha256(dumps_record(record).encode("utf-8")).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def parse_jsonl(data, origin="<jsonl>"):
    """Strictly parse JSONL bytes. Returns (records, issues)."""
    issues, records = [], []
    if data.startswith(b"\xef\xbb\xbf"):
        return [], [Issue("error", "bom", None, f"{origin}: UTF-8 BOM is not allowed")]
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        return [], [Issue("error", "malformed-utf8", None, f"{origin}: {error}")]
    if "\r" in text:
        issues.append(Issue("error", "crlf", None, f"{origin}: CR line endings are not allowed"))
    if text and not text.endswith("\n"):
        issues.append(Issue("error", "final-newline", None, f"{origin}: missing final newline"))
    for number, line in enumerate(text.split("\n")[:-1] if text else [], 1):
        if not line.strip():
            issues.append(Issue("error", "blank-line", None, f"{origin}:{number}: blank line"))
            continue
        try:
            value = json.loads(line, object_pairs_hook=_unique_object)
        except ValueError as error:
            issues.append(Issue("error", "malformed-json", None, f"{origin}:{number}: {error}"))
            continue
        if not isinstance(value, dict):
            issues.append(Issue("error", "not-object", None, f"{origin}:{number}: record must be an object"))
            continue
        records.append(value)
    return records, issues


def text_issues(key, resource, text):
    """Unicode / control diagnostics on a target string."""
    issues = []
    try:
        text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return [Issue("error", "invalid-unicode", key, "lone surrogate or unencodable scalar")]
    for i, ch in enumerate(text):
        o = ord(ch)
        cat = unicodedata.category(ch)
        if ch == "\n":
            continue
        if ch == "\r":
            if resource == "BOOKS-EN.FLX" and text[i + 1:i + 2] == "\n":
                continue
            issues.append(Issue("error", "control-character", key, "bare CR is not allowed"))
        elif o == 0xFFFD:
            issues.append(Issue("error", "replacement-character", key, "U+FFFD in target"))
        elif cat == "Co":
            issues.append(Issue("error", "private-use", key, f"private-use scalar U+{o:04X}"))
        elif cat == "Cn" or (o & 0xFFFE) == 0xFFFE or 0xFDD0 <= o <= 0xFDEF:
            issues.append(Issue("error", "unassigned-or-noncharacter", key, f"U+{o:04X}"))
        elif cat in ("Cc", "Cf", "Zl", "Zp"):
            issues.append(Issue("error", "control-character", key, f"prohibited control U+{o:04X}"))
    found = sorted(set(text) & SIMPLIFIED_ONLY)
    if found:
        issues.append(Issue("warning", "simplified-form", key,
                            "diagnostic: possible Simplified-only form(s); not auto-converted",
                            {"characters": "".join(found)}))
    return issues


def _type_ok(value, kind, nullable=False):
    if value is None:
        return nullable
    if kind is int:
        return type(value) is int
    return isinstance(value, kind)


def validate_record(record, expected_resource=None):
    """Structural/schema/language validation of a single canonical record."""
    key = record.get("key") if isinstance(record.get("key"), str) else None
    issues = []
    unknown = sorted(set(record) - set(FIELDS))
    if unknown:
        issues.append(Issue("error", "unknown-field", key, f"unknown fields {unknown}"))
    missing = [f for f in REQUIRED if f not in record]
    if missing:
        issues.append(Issue("error", "missing-field", key, f"missing fields {missing}"))
        return issues
    try:
        resource, entry_id = parse_key(record["key"])
    except ValueError as error:
        return issues + [Issue("error", "invalid-key", key, str(error))]
    if record["resource"] != resource or record["entry_id"] != entry_id or type(record["entry_id"]) is not int:
        issues.append(Issue("error", "key-mismatch", key, "key does not match resource/entry_id"))
    if expected_resource and resource != expected_resource:
        issues.append(Issue("error", "invalid-resource", key, f"record belongs in {RESOURCE_FILES[resource]}"))
    if record["status"] not in STATUSES:
        issues.append(Issue("error", "invalid-status", key, f"invalid status {record['status']!r}"))
    if record["category"] not in CATEGORIES:
        issues.append(Issue("error", "invalid-category", key, f"invalid category {record['category']!r}"))
    for name in ("speaker", "context", "notes", "migrated_from"):
        if not _type_ok(record.get(name), str, nullable=True):
            issues.append(Issue("error", "invalid-type", key, f"{name} must be string or null"))
    for name in ("terms", "runtime_evidence"):
        value = record.get(name, [])
        if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value) \
                or len(set(value)) != len(value) or value != sorted(value):
            issues.append(Issue("error", "invalid-type", key, f"{name} must be a sorted unique string list"))
    if not _type_ok(record.get("runtime_supported"), bool, nullable=True):
        issues.append(Issue("error", "invalid-type", key, "runtime_supported must be boolean or null"))
    if not isinstance(record["source_sha256"], str) or not re.fullmatch("[0-9a-f]{64}", record["source_sha256"]):
        issues.append(Issue("error", "invalid-source-hash", key, "source_sha256 must be 64 lowercase hex"))
    if type(record["source_units"]) is not int or record["source_units"] < 0:
        issues.append(Issue("error", "invalid-source-units", key, "source_units must be a non-negative integer"))
    review = record["review"]
    if not isinstance(review, dict) or set(review) != set(REVIEW_KEYS) or \
            any(type(v) is not bool for v in review.values()):
        issues.append(Issue("error", "invalid-review", key, f"review must hold booleans {list(REVIEW_KEYS)}"))
    target = record["target"]
    if not isinstance(target, str):
        return issues + [Issue("error", "invalid-type", key, "target must be a string")]
    if record["status"] == "untranslated":
        if target:
            issues.append(Issue("error", "untranslated-with-target", key, "untranslated record must have empty target"))
    elif not target.strip():
        issues.append(Issue("error", "empty-target", key, "empty target with translated status"))
    issues += text_issues(key, resource, target)
    return issues


def load_store(directory):
    """Load all canonical JSONL files. Returns (records, issues, file_hashes)."""
    directory = Path(directory)
    records, issues, hashes, seen = [], [], {}, {}
    for resource, filename in RESOURCE_FILES.items():
        path = directory / filename
        if not path.exists():
            issues.append(Issue("error", "missing-store-file", None, f"missing {filename}"))
            continue
        data = path.read_bytes()
        hashes[filename] = hashlib.sha256(data).hexdigest()
        rows, parse = parse_jsonl(data, filename)
        issues += parse
        for row in rows:
            row_issues = validate_record(row, resource)
            issues += row_issues
            key = row.get("key")
            if isinstance(key, str):
                if key in seen:
                    issues.append(Issue("error", "duplicate-key", key, "duplicate canonical key"))
                    continue
                seen[key] = row
            if not any(i.level == "error" for i in row_issues):
                records.append(row)
        if not any(i.level == "error" for i in parse) and rows and \
                all(isinstance(r.get("resource"), str) and r.get("resource") in RESOURCE_FILES and
                    type(r.get("entry_id")) is int for r in rows):
            if dumps_jsonl(rows) != data:
                issues.append(Issue("error", "non-canonical-serialization", None,
                                    f"{filename}: not in deterministic canonical form/order; "
                                    "rewrite with the pipeline serializer"))
    return sorted(records, key=sort_key), issues, hashes


def store_digest(file_hashes):
    lines = "".join(f"{name}\0{file_hashes[name]}\n" for name in sorted(file_hashes))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def write_store(directory, records):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    by_resource = {r: [] for r in RESOURCE_FILES}
    for record in records:
        by_resource[record["resource"]].append(record)
    for resource, filename in RESOURCE_FILES.items():
        (directory / filename).write_bytes(dumps_jsonl(by_resource[resource]))
