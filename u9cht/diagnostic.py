"""Validate P3 single-entry diagnostic mutations without weakening FLX guards."""

from .flx import FormatError, TextArchive, digest, verify


def analyze_mutation(original, rebuilt, entry_id, expected_text, *, same_length=True):
    """Require exactly one changed payload and only predictable relocation.

    This reports an intentional mutation, not an unchanged round-trip PASS.
    It does not authorize deployment, determine runtime success or diagnose fonts.
    """
    before, after = TextArchive(original), TextArchive(rebuilt)
    if len(before.entries) != len(after.entries):
        raise FormatError("diagnostic changed slot count")
    if type(entry_id) is not int or not 0 <= entry_id < len(before.entries):
        raise FormatError("invalid diagnostic entry ID")
    old_entry, new_entry = before.entries[entry_id], after.entries[entry_id]
    if not old_entry.is_used or not new_entry.is_used:
        raise FormatError("diagnostic must target a used entry")
    records = {row["id"]: row for row in before.records}
    new_records = {row["id"]: row for row in after.records}
    if new_records[entry_id]["text"] != expected_text:
        raise FormatError("diagnostic replacement text mismatch")
    changed = [a.index for a, b in zip(before.entries, after.entries)
               if before.payload(a) != after.payload(b)]
    if changed != [entry_id]:
        raise FormatError("diagnostic must change exactly the selected payload")
    delta = new_entry.length - old_entry.length
    if same_length and delta != 0:
        raise FormatError("same-length diagnostic changed entry size")
    if not same_length and delta == 0:
        raise FormatError("changed-length diagnostic must change entry size")
    if len(rebuilt) - len(original) != delta:
        raise FormatError("unexpected diagnostic file-size delta")
    changed_offsets = []
    for old, new in zip(before.entries, after.entries):
        expected_offset = old.offset + (delta if old.is_used and old.offset > old_entry.offset else 0)
        if new.offset != expected_offset:
            raise FormatError("unexpected diagnostic entry relocation")
        if old.index != entry_id and old.length != new.length:
            raise FormatError("unrelated diagnostic entry length changed")
        if old.offset != new.offset:
            changed_offsets.append(old.index)
    old_header, new_header = bytearray(original[:0x80]), bytearray(rebuilt[:0x80])
    # Both declared sizes were already checked by the strict archive constructor.
    old_header[0x58:0x60] = new_header[0x58:0x60]
    if old_header != new_header or before.padding() != after.padding():
        raise FormatError("diagnostic changed unknown header bytes or padding")
    result = verify(original, rebuilt)
    result.pop("status")  # A changed semantic payload intentionally fails equality.
    result.pop("runtime")
    result.update({
        "validation": "EXPECTED SINGLE-ENTRY MUTATION",
        "entry_id": entry_id,
        "original_text": records[entry_id]["text"],
        "replacement_text": expected_text,
        "original_entry_size": old_entry.length,
        "rebuilt_entry_size": new_entry.length,
        "entry_offset": old_entry.offset,
        "size_delta": delta,
        "changed_payload_ids": changed,
        "changed_offset_count": len(changed_offsets),
        "all_unmodified_payloads_identical": True,
        "source_sha256": digest(original),
    })
    return result
