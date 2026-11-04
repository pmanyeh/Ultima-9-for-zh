"""Terminology authority (U9_TERMS.csv) and deterministic terminology QA.

No blind search/replace: prose is only checked where a record explicitly tags a
term (``terms``), or reported as a diagnostic when local source text is present.
"""
import csv
import io
import re

from .store import Issue

COLUMNS = ("source", "target", "category", "status", "enforcement", "reference", "notes")
CATEGORIES = ("person", "place", "virtue", "item", "spell", "organization", "monster",
              "UI", "system", "other")
STATUSES = ("draft", "review", "approved", "blocked")
ENFORCEMENT = ("mandatory", "recommended", "informational")


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
        if not row["target"].strip() or row["target"] != row["target"].strip():
            issues.append(Issue("error", "glossary-target", where, "empty or padded target"))
        if not row["reference"].strip():
            issues.append(Issue("error", "glossary-reference", where, "reference is required"))
        rows.append(row)
    return rows, issues


def glossary_issues(rows):
    """Internal glossary consistency."""
    issues, pairs = [], set()
    approved_by_source, approved_by_target = {}, {}
    for row in rows:
        pair = (row["source"], row["target"])
        if pair in pairs:
            issues.append(Issue("error", "glossary-duplicate", row["source"], "duplicate source/target row"))
        pairs.add(pair)
        if row["status"] == "approved":
            approved_by_source.setdefault(row["source"], set()).add(row["target"])
            approved_by_target.setdefault(row["target"], set()).add(row["source"])
    for source, targets in sorted(approved_by_source.items()):
        if len(targets) > 1:
            issues.append(Issue("error", "term-multiple-approved-targets", source,
                                "same source term has multiple approved targets",
                                {"targets": sorted(targets)}))
    for target, sources in sorted(approved_by_target.items()):
        if len(sources) > 1:
            issues.append(Issue("error", "term-target-conflict", target,
                                "same approved target is used for conflicting source terms",
                                {"sources": sorted(sources)}))
    return issues


def _contains_term(source_text, term):
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", source_text) is not None


def terminology_issues(records, rows, sources=None):
    """Record-level terminology checks.

    ``sources`` optionally maps key -> local original text (never committed).
    """
    issues = []
    by_source = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)
    blocked = sorted({r["target"] for r in rows if r["status"] == "blocked"})
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
            approved = [e for e in entries if e["status"] == "approved"]
            if not approved:
                if not any(e["target"] in target for e in entries):
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
                approved = [e for e in entries if e["status"] == "approved"]
                if not approved or term in record.get("terms", []):
                    continue
                if _contains_term(sources[key], term) and approved[0]["target"] not in target:
                    issues.append(Issue("warning" if approved[0]["enforcement"] == "mandatory" else "info",
                                        "term-possibly-untagged", key,
                                        f"source contains {term!r}; approved target {approved[0]['target']!r} absent "
                                        "(diagnostic; ordinary prose may be ambiguous)"))
    return issues
