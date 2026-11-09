"""Resource adapters: one per independently verified FLX family.

Each adapter exposes the same small interface while keeping its own binary
format (no family is converted to another family's semantics):

* ``units(data)``   -> {entry_id: SourceUnit} with exact source hashes
* ``stored(entry_id, target)`` -> value written into the archive
* ``build(data, {entry_id: target})`` -> (bytes, mutation audit)
"""
import hashlib
from dataclasses import dataclass

from ..books import TOKENS, BookArchive
from .runtime_pack import BOOK_DOMAIN
from ..flx import FormatError, TextArchive, digest
from ..representative import NAME_DOMAIN, name_marker
from ..typename import TypeNameArchive


@dataclass(frozen=True)
class SourceUnit:
    entry_id: int
    text: str | None        # local original text; never committed
    sha256: str
    units: int
    editable: bool
    reason: str | None = None
    aliases: tuple = ()      # other IDs sharing this physical payload


class Adapter:
    resource = None
    archive_class = None
    editable_field = None
    locked_fields = ()
    unit_name = None
    runtime_domain = None

    def archive(self, data):
        return self.archive_class(data)

    def _alias_map(self, archive):
        groups = {}
        for entry in archive.entries:
            if entry.is_used:
                groups.setdefault((entry.offset, entry.length), []).append(entry.index)
        return {i: tuple(x for x in ids if x != i) for ids in groups.values() for i in ids}

    def units(self, data):
        raise NotImplementedError

    def stored(self, entry_id, target):
        raise NotImplementedError

    def source_tokens(self, text):
        return []

    def build(self, data, translations):
        archive = self.archive(data)
        document = archive.export()
        rows = {r["id"]: r for r in document["entries"]}
        intended = {}
        for entry_id, target in sorted(translations.items()):
            if entry_id not in rows:
                raise FormatError(f"{self.resource}:{entry_id}: no such source entry")
            value = self.stored(entry_id, target)
            rows[entry_id][self.editable_field] = value
            intended[entry_id] = value
        output = archive.rebuild(document)
        audit = mutation_audit(self, data, output, intended)
        if audit["status"] != "PASS":
            raise FormatError(f"{self.resource}: unexpected mutation: {audit['unexpected_byte_differences']}")
        return output, audit


class TextAdapter(Adapter):
    resource = "text.flx"
    archive_class = TextArchive
    editable_field = "text"
    locked_fields = ("encoding", "bom", "terminator")
    unit_name = "utf16-code-units"
    runtime_domain = 0

    def units(self, data):
        archive = self.archive(data)
        aliases = self._alias_map(archive)
        out = {}
        for r in archive.records:
            text = r["text"]
            marker = text.endswith(" : BEGIN FILE")
            out[r["id"]] = SourceUnit(r["id"], text, digest(text.encode("utf-16-le")),
                                      len(text.encode("utf-16-le")) // 2, not marker,
                                      "source file marker is locked" if marker else None,
                                      aliases[r["id"]])
        return out

    def stored(self, entry_id, target):
        return target


class TypeNameAdapter(Adapter):
    """Chinese labels use the measured ASCII marker bridge plus a runtime plan."""
    resource = "TYPENAME.FLX"
    archive_class = TypeNameArchive
    editable_field = "name"
    locked_fields = ("reference_i32", "icon_u16", "trailing_hex")
    unit_name = "ascii-bytes"
    runtime_domain = NAME_DOMAIN

    def units(self, data):
        archive = self.archive(data)
        aliases = self._alias_map(archive)
        out = {}
        for r in archive.records:
            name = r["name"]
            raw = (name or "").encode("ascii")
            out[r["id"]] = SourceUnit(r["id"], name, digest(raw), len(raw),
                                      name is not None and r["id"] < 8192,
                                      None if name is not None else "no label storage",
                                      aliases[r["id"]])
        return out

    def stored(self, entry_id, target):
        return name_marker(entry_id)


class BooksAdapter(Adapter):
    """ASCII bodies keep their form; Chinese bodies use the game's own UTF-16 book format (P9-4)."""
    resource = "BOOKS-EN.FLX"
    archive_class = BookArchive
    editable_field = "body_text"
    locked_fields = ("title_length", "title_ascii")
    unit_name = "body-bytes"
    runtime_domain = BOOK_DOMAIN

    def units(self, data):
        archive = self.archive(data)
        aliases = self._alias_map(archive)
        out = {}
        for r in archive.records:
            body = bytes.fromhex(r["body_hex"])
            ok = r["body_text"] is not None
            out[r["id"]] = SourceUnit(r["id"], r["body_text"], digest(body), len(body), ok,
                                      None if ok else "opaque non-text body",
                                      aliases[r["id"]])
        return out

    def stored(self, entry_id, target):
        return target

    def source_tokens(self, text):
        return [t.decode("ascii") for t in TOKENS.findall(text.encode("utf-8"))]


ADAPTERS = {a.resource: a for a in (TextAdapter(), TypeNameAdapter(), BooksAdapter())}


def mutation_audit(adapter, original, output, intended):
    """Compare two archives of one family; any unintended change -> FAIL."""
    problems = []
    result = {"resource": adapter.resource,
              "original_sha256": digest(original), "output_sha256": digest(output),
              "original_size": len(original), "output_size": len(output)}
    try:
        left, right = adapter.archive(original), adapter.archive(output)
    except FormatError as error:
        result.update(status="FAIL", unexpected_byte_differences=[f"unparseable output: {error}"])
        return result
    if len(left.entries) != len(right.entries):
        problems.append("slot count changed")
    header = [o for o in range(0, 0x80, 4) if original[o:o + 4] != output[o:o + 4]]
    unexpected_header = [o for o in header if o not in (0x58, 0x5C)]
    if unexpected_header:
        problems.append(f"unknown header fields changed at {[hex(o) for o in unexpected_header]}")
    if left.padding() != right.padding():
        problems.append("container padding/gaps changed")
    l_rows = {r["id"]: r for r in left.export()["entries"]}
    r_rows = {r["id"]: r for r in right.export()["entries"]}
    if set(l_rows) != set(r_rows):
        problems.append("used-entry set changed")
    aliases = adapter._alias_map(left)
    expected = set(intended)
    for entry_id in intended:
        expected.update(aliases.get(entry_id, ()))
    changed, relocated = [], 0
    for a, b in zip(left.entries, right.entries):
        if (a.offset, a.length) != (b.offset, b.length) and a.is_used:
            relocated += a.offset != b.offset
        if not a.is_used:
            if b.is_used:
                problems.append(f"entry {a.index}: empty slot became used")
            continue
        if left.payload(a) != right.payload(b):
            changed.append(a.index)
    unexpected = sorted(set(changed) - expected)
    missing = sorted(i for i in expected if i not in changed and
                     l_rows[i][adapter.editable_field] != intended.get(i, l_rows[i][adapter.editable_field]))
    if unexpected:
        problems.append(f"unselected payloads changed: {unexpected[:20]}")
    if missing:
        problems.append(f"selected payloads not changed: {missing[:20]}")
    for entry_id in changed:
        before, after = l_rows[entry_id], r_rows.get(entry_id, {})
        for name in adapter.locked_fields:
            if before.get(name) != after.get(name):
                problems.append(f"entry {entry_id}: locked field {name} changed")
        want = intended.get(entry_id)
        if want is None:
            want = next((intended[x] for x in aliases.get(entry_id, ()) if x in intended), None)
        if after.get(adapter.editable_field) != want:
            problems.append(f"entry {entry_id}: stored value differs from intended value")
    used = sum(e.is_used for e in left.entries)
    result.update(
        changed_entries=sorted(changed),
        changed_entry_count=len(changed),
        unchanged_entry_count=used - len(changed),
        relocated_offsets=relocated,
        changed_metadata_fields=[{"offset": hex(o), "field": "declared file size",
                                  "original": original[o:o + 4].hex(), "output": output[o:o + 4].hex()}
                                 for o in header if o in (0x58, 0x5C)],
        unexpected_byte_differences=problems,
        status="PASS" if not problems else "FAIL")
    return result


def resource_sha256(data):
    return hashlib.sha256(data).hexdigest()
