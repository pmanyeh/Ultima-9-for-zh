"""Terminology authority (U9_TERMS.csv) and deterministic terminology QA.

No blind search/replace: prose is only checked where a record explicitly tags a
term (``terms``), or reported as a diagnostic when local source text is present.
"""
import csv
import io
import re

from .store import Issue

COLUMNS = ("source", "target", "category", "status", "enforcement", "count", "example", "reference", "notes",
           "annotate")
CATEGORIES = ("person", "place", "organization", "title", "virtue", "spell", "monster", "item",
              "UI", "system", "other")
# Same meaning as the Ultima VIII authority file: keep = stays English, approved = use target,
# proposed = suggestion, todo = undecided, ignore = not a name; blocked = a rejected target.
STATUSES = ("todo", "proposed", "approved", "keep", "ignore", "blocked")
NEEDS_TARGET = ("proposed", "approved", "keep", "blocked")
ENFORCEMENT = ("mandatory", "recommended", "informational")
# English after the Chinese name, half-width: 艾蓮娜(Elaina). always = every line; first = the first
# line of each conversation file (text.flx entry order) or each book/label; never = no annotation.
ANNOTATE = ("", "always", "first", "never")
ANNOTATE_DEFAULT = {"person": "always", "place": "first", "organization": "first", "title": "first",
                    "spell": "first", "monster": "first", "other": "first"}


def annotation_mode(row):
    return row["annotate"] or ANNOTATE_DEFAULT.get(row["category"], "never")


def annotated(row):
    return f"{row['target']}({row['source']})"


def parse_glossary(data):
    """Parse CSV bytes. Returns (rows, issues)."""
    issues = []
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        return [], [Issue("error", "glossary-utf8", None, str(error))]
    if text.startswith("﻿"):
        return [], [Issue("error", "glossary-bom", None, "glossary must not start with a BOM")]
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        return [], [Issue("error", "glossary-empty", None, "glossary is empty")]
    if tuple(header) != COLUMNS:
        return [], [Issue("error", "glossary-header", None, f"columns must be {list(COLUMNS)}")]
    rows = []
    for number, values in enumerate(reader, 2):
        where = f"U9_TERMS.csv:{number}"
        if len(values) != len(COLUMNS):
            issues.append(Issue("error", "glossary-row", where, "wrong column count"))
            continue
        row = dict(zip(COLUMNS, values))
        row["line"] = number
        if not row["source"].strip() or row["source"] != row["source"].strip():
            issues.append(Issue("error", "glossary-source", where, "empty or padded source term"))
        if row["category"] not in CATEGORIES:
            issues.append(Issue("error", "glossary-category", where, f"invalid category {row['category']!r}"))
        if row["status"] not in STATUSES:
            issues.append(Issue("error", "glossary-status", where, f"invalid status {row['status']!r}"))
        if row["enforcement"] not in ENFORCEMENT:
            issues.append(Issue("error", "glossary-enforcement", where,
                                f"invalid enforcement {row['enforcement']!r}"))
        if row["target"] != row["target"].strip() or (row["status"] in NEEDS_TARGET and not row["target"]):
            issues.append(Issue("error", "glossary-target", where, "empty or padded target"))
        if row["status"] == "keep" and row["target"] != row["source"]:
            issues.append(Issue("error", "glossary-keep", where, "a kept term must have target == source"))
        if row["annotate"] not in ANNOTATE:
            issues.append(Issue("error", "glossary-annotate", where, f"invalid annotate {row['annotate']!r}"))
        if row["count"] and not row["count"].isdigit():
            issues.append(Issue("error", "glossary-count", where, "count must be a non-negative integer"))
        if not row["reference"].strip():
            issues.append(Issue("error", "glossary-reference", where, "reference is required"))
        rows.append(row)
    return rows, issues


VARIANT = re.compile(r"(?:^|;\s*)variant of ([^;]+?)\s*(?:;|$)")
PLURAL = re.compile(r"^plural of (.+)$")


def variant_base(row):
    """Source term this row is declared to be a spelling variant or plural of, or None."""
    m = VARIANT.search(row.get("notes", "")) or PLURAL.match(row.get("reference", "").strip())
    return m.group(1).strip() if m else None


def glossary_issues(rows):
    """Internal glossary consistency."""
    issues, pairs = [], set()
    approved_by_source, approved_by_target = {}, {}
    for row in rows:
        pair = (row["source"], row["target"])
        if pair in pairs:
            issues.append(Issue("error", "glossary-duplicate", row["source"], "duplicate source/target row"))
        pairs.add(pair)
        if row["status"] in ("approved", "keep"):
            approved_by_source.setdefault(row["source"], set()).add(row["target"])
            approved_by_target.setdefault(row["target"], set()).add(row["source"])
    for source, targets in sorted(approved_by_source.items()):
        if len(targets) > 1:
            issues.append(Issue("error", "term-multiple-approved-targets", source,
                                "same source term has multiple approved targets",
                                {"targets": sorted(targets)}))
    # Spelling variants of one term ("Scroll: Fireball" / "Fireball Scroll") may share a target
    # only when the row says so: notes "variant of <source>" or reference "plural of <source>".
    by_source = {r["source"]: r for r in rows}
    canonical = {}
    for row in rows:
        base = variant_base(row)
        if base is None or row["status"] not in ("approved", "keep"):
            continue
        b = by_source.get(base)
        explicit = VARIANT.search(row.get("notes", ""))
        if not explicit and b and b["target"] != row["target"]:
            continue  # tool-written "plural of" hint; the human chose a different target
        if not b or b["status"] not in ("approved", "keep") or b["target"] != row["target"] or variant_base(b):
            issues.append(Issue("error", "glossary-variant", row["source"],
                                "variant must name an approved row with the same target that is not itself a variant",
                                {"variant_of": base}))
            continue
        canonical[row["source"]] = base
    for target, sources in sorted(approved_by_target.items()):
        if len({canonical.get(s, s) for s in sources}) > 1:
            issues.append(Issue("error", "term-target-conflict", target,
                                "same approved target is used for conflicting source terms",
                                {"sources": sorted(sources)}))
    return issues


def _contains_term(source_text, term):
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", source_text) is not None


def contains_standalone(source_text, term, vocabulary=()):
    """True when ``term`` occurs outside every longer vocabulary term that contains it.

    "Shrine" inside "Shrine of Compassion" names the longer term, not "Shrine" on its own.
    """
    if term not in source_text or not _contains_term(source_text, term):
        return False
    candidates = (v for v in vocabulary if v != term and term in v and v in source_text)
    for longer in sorted((v for v in candidates if _contains_term(v, term)), key=len, reverse=True):
        source_text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(longer) + r"(?![A-Za-z0-9])", " ", source_text)
    return _contains_term(source_text, term)


def terminology_issues(records, rows, sources=None):
    """Record-level terminology checks.

    ``sources`` optionally maps key -> local original text (never committed).
    """
    issues = []
    by_source = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)
    blocked = sorted({r["target"] for r in rows if r["status"] == "blocked"})
    vocabulary = [r["source"] for r in rows if r["status"] in ("approved", "keep")]
    for record in records:
        key, target = record["key"], record["target"]
        if record["status"] in ("untranslated", "blocked"):
            continue
        for term in blocked:
            if term in target:
                issues.append(Issue("error", "blocked-term", key, f"blocked term {term!r} appears in target"))
        for term in record.get("terms", []):
            entries = by_source.get(term)
            if not entries:
                issues.append(Issue("warning", "term-not-in-glossary", key, f"tagged term {term!r} is not in the glossary"))
                continue
            approved = [e for e in entries if e["status"] in ("approved", "keep")]
            if not approved:
                if not any(e["target"] and e["target"] in target for e in entries):
                    issues.append(Issue("info", "term-undecided", key,
                                        f"tagged term {term!r} has no approved target yet"))
                continue
            expected = approved[0]
            if expected["target"] not in target:
                level = {"mandatory": "error", "recommended": "warning"}.get(expected["enforcement"], "info")
                issues.append(Issue(level, "term-not-used", key,
                                    f"tagged term {term!r} expects approved target {expected['target']!r}",
                                    {"enforcement": expected["enforcement"]}))
        if sources and key in sources:
            for term, entries in sorted(by_source.items()):
                approved = [e for e in entries if e["status"] in ("approved", "keep")]
                if not approved or term in record.get("terms", []):
                    continue
                if contains_standalone(sources[key], term, vocabulary) and approved[0]["target"] not in target:
                    issues.append(Issue("warning" if approved[0]["enforcement"] == "mandatory" else "info",
                                        "term-possibly-untagged", key,
                                        f"source contains {term!r}; approved target {approved[0]['target']!r} absent "
                                        "(diagnostic; ordinary prose may be ambiguous)"))
    return issues


def first_occurrences(terms, units_by_resource, sections, vocabulary=()):
    """{term: set(keys)} where a ``first`` term must be annotated.

    text.flx: the lowest entry ID per conversation file whose source contains the term.
    Every book and label is its own unit, so each occurrence there is a first one.
    """
    out = {term: set() for term in terms}
    for resource, units in sorted(units_by_resource.items()):
        seen = set()
        for entry_id in sorted(units):
            unit = units[entry_id]
            if not unit.editable or not unit.text:
                continue
            group = sections.get(entry_id) if resource == "text.flx" else (resource, entry_id)
            for term in terms:
                if (group, term) not in seen and contains_standalone(unit.text, term, vocabulary):
                    seen.add((group, term))
                    out[term].add(f"{resource}:{entry_id}")
    return out


def annotation_issues(records, rows, sources=None, first=None):
    """Check 譯名(English) against each approved, translated term's annotate mode."""
    issues = []
    decided = [r for r in rows if r["status"] == "approved" and r["target"] != r["source"]]
    vocabulary = [r["source"] for r in rows if r["status"] in ("approved", "keep")]
    level = {"mandatory": "error", "recommended": "warning"}
    for record in records:
        if record["status"] in ("untranslated", "blocked"):
            continue
        key, target, source = record["key"], record["target"], (sources or {}).get(record["key"])
        for row in decided:
            term = row["source"]
            if term not in record.get("terms", []) and not (source and contains_standalone(source, term, vocabulary)):
                continue
            mode, form = annotation_mode(row), annotated(row)
            if mode == "first" and first is None:
                continue
            required = mode == "always" or (mode == "first" and key in first.get(term, ()))
            if required and form not in target:
                issues.append(Issue(level.get(row["enforcement"], "info"), "annotation-missing", key,
                                    f"expected {form!r} ({mode})", {"term": term}))
            elif not required and form in target:
                issues.append(Issue("warning" if mode == "never" else "info", "annotation-unexpected", key,
                                    f"{form!r} is not expected here ({mode})", {"term": term}))
    return issues
