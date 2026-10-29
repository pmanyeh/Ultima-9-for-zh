# U9 FLX / text.flx notes

Evidence date: 2026-10-28–29. Applicable baseline SHA-256:
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.
All local measurements below are CONFIRMED for this file only.

| Offset | Observed field |
| --- | --- |
| `0x00` | 76-byte comment region, preserved verbatim |
| `0x4C` | u32, observed zero; purpose UNKNOWN |
| `0x50` | u32 little-endian slot count: 7,656 |
| `0x54` | u32 observed 2; meaning/version interpretation is upstream evidence |
| `0x58`, `0x5C` | u32 file sizes: both 1,200,660 |
| `0x60–0x7F` | Reserved/unknown bytes, preserved verbatim |
| `0x80` | Directory: 7,656 `(u32 offset, u32 byte_length)` pairs |

The table ends at `0xEFC0` (61,376), exactly where the first payload begins.
All slots are used, in bounds and non-overlapping, with 7,656 unique ranges.
All 7,655 adjacent payload gaps are zero; there is no trailer. Entries are 6–1,072
bytes. 3,823 offsets are not four-byte aligned; no padding is synthesized.

Small diagnostic sample at `0x4C` (32 bytes):

```text
00 00 00 00 e8 1d 00 00 02 00 00 00 14 52 12 00
14 52 12 00 00 00 00 00 00 00 00 00 01 00 00 00
```

## Text encoding and identifiers

- CONFIRMED: all 7,656 payloads have even byte lengths, strictly decode as
  UTF-16LE, have no BOM and end in exactly one U+0000 code unit.
- CONFIRMED: lengths include the two-byte terminator and count bytes, not glyphs.
- CONFIRMED: no other C0 control characters occur in these decoded payloads.
  Three characters are above ASCII; none are above U+FFFF.
- STRONG EVIDENCE: UTF-16LE-like/UCS-2LE storage. The observed BMP-only corpus
  cannot distinguish the engine's support for surrogate pairs.
- CONFIRMED: 266 records end in ` : BEGIN FILE`; those structural markers cannot
  be edited by the importer.
- CONFIRMED: entry 4164, offset `676832`, size `260`, matches the opening subtitle
  observed during runtime. No record was translated or otherwise changed.
- UNKNOWN: how the engine reacts to malformed Unicode. The tool rejects odd
  lengths, malformed UTF-16 and missing terminators; this is tool policy rather
  than a claim about engine behavior.

## Preservation and validation

An export stores source SHA-256, slot count and each used entry's ID, offset,
size, encoding, BOM/terminator metadata and decoded text. The importer requires
the original template and validates the entire record set. It re-encodes every
entry, retains all non-payload bytes, physical order and consistent exact aliases,
and validates the finished archive. Missing/duplicate/tampered metadata, bounds
errors, half-empty slots, partial overlaps and conflicting aliases are rejected.

Multiple trailing NULs and a BOM survive synthetic unchanged round-trips without
normalization. Synthetic resizing also preserves unknown header/gap/trailer bytes.
These synthetic cases are not assertions about shipped game variants.

`misctext.flx`, books, names and dialect resources received container inventory
only. Their payload semantics and encodings must be verified separately before
using this text importer. Font and renderer behavior remain UNKNOWN.
