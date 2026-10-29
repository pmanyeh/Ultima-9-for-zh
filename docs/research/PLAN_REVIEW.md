# Master Plan review — initial batch

Date: 2026-10-29, Asia/Taipei.

The plan's evidence-first sequence, original-resource preservation, resource-only
round-trip gate and small subsequent PoC are suitable for this project. No change
to the supplied Master Plan or AGENTS.md was needed. Execution stops after P2.

- CONFIRMED: this English `text.flx` supports strict UTF-16LE decoding and exact
  unchanged export/import. This does not establish CJK glyph support.
- CONFIRMED: the pinned TITAN reader can be reused with validation; its generic
  repacker does not satisfy unknown-byte preservation on synthetic edge cases.
- CONFIRMED: 3,823 local text entry offsets are not multiples of four. A writer
  must preserve observed layout rather than add guessed alignment.
- UNKNOWN: whether the engine implements UCS-2-only semantics or accepts UTF-16
  surrogate pairs. The observed corpus has no supplementary code points.
- UNKNOWN: native CJK rendering and exact font lookup. The user has no Japanese
  installation; no Japanese assets were obtained. P4 cannot yet use that oracle.
- UNKNOWN: the exact installed patch label. The observed GOG English installation
  is frozen by hashes/build ID, without declaring it to be 1.19f or 1.19h.

Runtime smoke success is recorded separately from byte equality. Neither result
means a translated string or Chinese glyph has been tested. After explicit P3
authorization, the next experiment should change one safe, visible entry and
record its own archive/encoding/glyph evidence.
