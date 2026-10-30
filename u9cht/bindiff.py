"""Metadata-only binary/PE comparison. Positional clusters are NOT functions."""

import hashlib
import re

from .pe import PEImage


def changed_ranges(left, right):
    """Half-open positional ranges, including missing tail bytes on either side."""
    ranges, start = [], None
    for index in range(max(len(left), len(right))):
        different = index >= min(len(left), len(right)) or left[index] != right[index]
        if different and start is None:
            start = index
        elif not different and start is not None:
            ranges.append((start, index))
            start = None
    if start is not None:
        ranges.append((start, max(len(left), len(right))))
    return ranges


def cluster_ranges(ranges, gap=32):
    if gap < 0:
        raise ValueError("negative clustering gap")
    result = []
    previous_end = -1
    for start, end in ranges:
        if start < 0 or end <= start or start < previous_end:
            raise ValueError("ranges must be ordered, nonoverlapping and nonempty")
        if result and start - result[-1]["end"] <= gap:
            result[-1]["end"] = end
            result[-1]["changed_bytes"] += end - start
            result[-1]["ranges"] += 1
        else:
            result.append({"start": start, "end": end, "changed_bytes": end - start, "ranges": 1})
        previous_end = end
    return result


def positional_summary(left, right, gap=32):
    ranges = changed_ranges(left, right)
    clusters = cluster_ranges(ranges, gap)
    return {"left_size": len(left), "right_size": len(right),
            "changed_bytes": sum(end - start for start, end in ranges),
            "range_count": len(ranges), "clustering_gap": gap,
            "cluster_count": len(clusters),
            "largest_clusters": sorted(clusters, key=lambda row: row["changed_bytes"], reverse=True)[:16],
            "interpretation": "positional comparison; movement/relocation is not semantic change"}


def compare_pe(left, right):
    a, b = PEImage(left), PEImage(right)

    def imports(image):
        return {(row["dll"].lower(), row["name"], row["ordinal"]) for row in image.imports()}

    def resources(image):
        return {tuple(row["path"]): {**row, "sha256": hashlib.sha256(image.read(
            image.rva_offset(row["rva"], row["size"]), row["size"])).hexdigest()}
            for row in image.resources()}

    sa, sb = imports(a), imports(b)
    ra, rb = resources(a), resources(b)
    sections = []
    for name in sorted({s["name"].lower() for p in (a, b) for s in p.sections}):
        aa = [s for s in a.sections if s["name"].lower() == name]
        bb = [s for s in b.sections if s["name"].lower() == name]
        if len(aa) > 1 or len(bb) > 1:
            raise ValueError("ambiguous duplicate PE section names")
        row = {"name": name, "left": aa[0] if aa else None, "right": bb[0] if bb else None}
        if aa and bb:
            x, y = aa[0], bb[0]
            row["section_relative_diff"] = positional_summary(
                a.read(x["raw_offset"], x["raw_size"]), b.read(y["raw_offset"], y["raw_size"]))
        sections.append(row)
    return {"left": a.metadata(), "right": b.metadata(), "sections": sections,
            "imports_added": sorted(sb - sa, key=str), "imports_removed": sorted(sa - sb, key=str),
            "resources": [{"path": list(key), "left": ra.get(key), "right": rb.get(key)}
                          for key in sorted(ra.keys() | rb.keys(), key=str)],
            "whole_file_positional_diff": positional_summary(left, right)}


def instruction_token(mnemonic, operands, image_ranges):
    """Candidate matching only: mask control targets and in-image addresses.

    Register/stack operands and non-address constants remain. No equivalence is
    inferred solely from a token match; call graph and behavior need review.
    """
    branch = mnemonic.startswith("j") or mnemonic in ("call", "loop", "loope", "loopne")

    def replace(match):
        value = int(match[0], 16)
        if branch:
            return "TARGET"
        return "ADDRESS" if any(start <= value < end for start, end in image_ranges) else match[0]

    return mnemonic + " " + re.sub(r"0x[0-9a-fA-F]+", replace, operands)


def sequence_matches(haystack, needle):
    if not needle:
        raise ValueError("empty instruction anchor")
    return [index for index in range(len(haystack) - len(needle) + 1)
            if haystack[index] == needle[0] and haystack[index:index + len(needle)] == needle]
