"""Source-drift, layout, punctuation and font-coverage QA.

Layout preflight never edits text: canonical targets keep their authored LF
exactly; this module only measures and reports.
"""
import re

from .runtime_pack import logical_advance
from .store import Issue

FORBID_START = frozenset("，。、！？；：）》」』】〕〉")
FORBID_END = frozenset("（《「『【〔〈")
PLACEHOLDER = re.compile(r"%[-+ #0-9.]*[a-zA-Z]")
LAYOUT_STATES = ("PASS", "WARNING", "OVERFLOW", "UNKNOWN-LAYOUT")


def source_issues(record, units, resource_units_name):
    """Compare one canonical record with the local original resource."""
    key = record["key"]
    unit = units.get(record["entry_id"])
    if unit is None:
        return [Issue("error", "missing-source-entry", key, "entry does not exist in the local source resource")]
    issues = []
    if unit.sha256 != record["source_sha256"]:
        issues.append(Issue("error", "source-drift", key, "SOURCE DRIFT: entry source hash differs",
                            {"resource": record["resource"], "entry_id": record["entry_id"],
                             "expected_source_sha256": record["source_sha256"],
                             "observed_source_sha256": unit.sha256}))
        return issues
    if unit.units != record["source_units"]:
        issues.append(Issue("error", "source-units-mismatch", key,
                            f"source_units {record['source_units']} != observed {unit.units} {resource_units_name}"))
    if not unit.editable and record["status"] != "untranslated":
        issues.append(Issue("error", "locked-source-entry", key, unit.reason or "entry is not editable"))
    if record["status"] in ("untranslated", "blocked") or unit.text is None:
        return issues
    src_ph = sorted(PLACEHOLDER.findall(unit.text))
    dst_ph = sorted(PLACEHOLDER.findall(record["target"]))
    if src_ph != dst_ph:
        issues.append(Issue("error", "placeholder-mismatch", key, "placeholder tokens differ",
                            {"source": src_ph, "target": dst_ph}))
    return issues


def token_issues(adapter, record, unit):
    if unit is None or unit.text is None or record["status"] in ("untranslated", "blocked"):
        return []
    before, after = adapter.source_tokens(unit.text), adapter.source_tokens(record["target"])
    if before != after:
        return [Issue("error", "control-token-mismatch", record["key"],
                      "control-token sequence (page/font/CRLF markers) differs from source",
                      {"source_count": len(before), "target_count": len(after)})]
    return []


def alias_issues(record, unit, by_key):
    issues = []
    if unit is None or record["status"] in ("untranslated", "blocked"):
        return issues
    for alias in unit.aliases:
        other = by_key.get(f"{record['resource']}:{alias}")
        if other is None or other["target"] != record["target"] or other["status"] != record["status"]:
            issues.append(Issue("error", "alias-mismatch", record["key"],
                                f"entry shares its payload with {alias}; aliases need identical target/status"))
    return issues


def layout_profile(record, profiles):
    for profile in profiles:
        if profile["resource"] == record["resource"] and record["category"] in profile["categories"]:
            return profile
    return None


def check_layout(record, profiles, metrics):
    """Return a layout report row; does not modify the target."""
    profile = layout_profile(record, profiles)
    row = {"key": record["key"], "category": record["category"], "status": "UNKNOWN-LAYOUT",
           "issues": []}
    if profile is None:
        row["issues"].append("no measured layout geometry for this resource/category")
        return row
    row["budget_logical"] = profile["budget_logical"]
    lines = record["target"].split("\n")
    widths = []
    for line in lines:
        width = 0
        for ch in line:
            o = ord(ch)
            if o < 128:
                width += profile["native_ascii_estimate"]
                continue
            advance = None
            if metrics is not None:
                try:
                    advance = logical_advance(metrics, o)
                except ValueError as error:
                    row["issues"].append(str(error))
            if advance is None:
                row["issues"].append(f"no measured advance for U+{o:04X}")
                return row
            width += advance
        widths.append(width)
    row["line_widths"] = widths
    row["line_count"] = len(lines)
    status = "PASS"
    if not profile["multiline"] and len(lines) > 1:
        status = "OVERFLOW"
        row["issues"].append("single-line surface contains an authored line break")
    if max(widths) > profile["budget_logical"]:
        status = "OVERFLOW"
        row["issues"].append(f"line width {max(widths)} exceeds budget {profile['budget_logical']}")
    warnings = []
    if profile.get("observed_max_lines") and len(lines) > profile["observed_max_lines"]:
        warnings.append(f"{len(lines)} lines exceed observed maximum {profile['observed_max_lines']}")
    for number, line in enumerate(lines, 1):
        if not line.strip():
            warnings.append(f"line {number} is empty")
            continue
        if line != line.strip():
            warnings.append(f"line {number} has leading/trailing whitespace")
        if line[0] in FORBID_START:
            warnings.append(f"line {number} starts with prohibited punctuation {line[0]!r}")
        if line[-1] in FORBID_END and number < len(lines):
            warnings.append(f"line {number} ends with opening punctuation {line[-1]!r}")
        if line[-1] in FORBID_END and number == len(lines):
            warnings.append(f"text ends with opening punctuation {line[-1]!r}")
    row["issues"] += warnings
    if status == "PASS" and warnings:
        status = "WARNING"
    if any(ord(ch) < 128 and ch not in "\n" for ch in record["target"]):
        row["native_ascii_width_is_estimate"] = True
    row["status"] = status
    return row


def layout_summary(rows):
    counts = {state: 0 for state in LAYOUT_STATES}
    for row in rows:
        counts[row["status"]] += 1
    return counts


def font_issues(usage, metrics):
    """Every custom scalar used by active translations must exist in the font."""
    issues = []
    for scalar, keys in usage.items():
        try:
            ok = logical_advance(metrics, scalar) is not None
            problem = "missing glyph in pinned font"
        except ValueError as error:
            ok, problem = False, str(error)
        if not ok:
            issues.append(Issue("error", "font-missing-glyph", keys[0],
                                f"U+{scalar:04X} {chr(scalar)!r}: {problem}",
                                {"scalar": f"U+{scalar:04X}", "character": chr(scalar), "keys": keys}))
    return issues
