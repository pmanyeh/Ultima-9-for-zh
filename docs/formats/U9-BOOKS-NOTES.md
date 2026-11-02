# Readable-item resource evidence — P6-S2

2026-11-01. This investigation began after a human opened the actual bedroom
book. The English screen and its hash are private under `.local/p6s2/scout/`.
This demonstrates the game's native readable-item surface, not a generic item
description panel and not yet Chinese rendering.

## Source and independent format inspection

The visible heading and paragraphs match BOOKS-EN.FLX slot182 uniquely in the
local archive. The controlled single-entry ASCII heading edit was subsequently observed in
the actual native open book: `U9_BOOK_0182`. Source provenance is now
**CONFIRMED / RUNTIME PASS** for this slot. This is not a Chinese-rendering pass.

- Archive SHA-256
  `a0653ef3608537575e707faa56aca6f24efc2eddaab554d49279d6c1c1a8858b`;
  221,316 bytes, 4,096 slots,460 used.
- Every used record accounts for exactly all bytes as `<u32 title_length>`,
  title bytes, `<u32 body_length>`, body bytes. All titles include one final NUL.
  Body lengths describe bytes, not UTF-16 units; bodies are not uniformly
  NUL-terminated (only one ends in NUL).
- All local titles are ASCII. Eight bodies contain non-ASCII bytes, including
  one embedded OLE2 document already described by the pinned upstream. Their
  encoding/meaning is not generalized; the importer preserves them opaquely.
- Selected slot182: offset132511, record size663, title field18 bytes,
  body637 bytes, ASCII with font/page markup. Body SHA-256
  `b5a04c84c115a6fb062742df015035882ade1f7398eb04f39e85f4c9144dafb2`.
- Native markup includes case-sensitive bytes such as backtick-font-number and
  backtick-page commands. CRLF paragraphs, existing NULs and marker order must
  survive edits. The writer rejects their removal or alteration; it does not
  normalize unexplained bytes or import Chinese into the unverified byte format.
- Export → JSON serialization → import is BYTE-PERFECT PASS for the entire
  archive, including the opaque binary record and all unused slots/padding.

The separately implemented `BookArchive` shares only the independently validated
FLX container preservation helper with other families. It does not use the
text.flx UTF-16 payload parser. TITAN0.7.8/tgwUltima commit
`2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`, `titan/u9/books.py`, is a reference,
not the local round-trip evidence. Public tests are wholly synthetic.

## Other actual information surface

Clicking the bedroom clock produces player-facing time information. The actual
English screen was captured privately. Its variable sentence matches the native
format at VA0x7A8B3C, referenced by formatting code at0x6551F5 and then passed
through0x624680. This is STRONG EVIDENCE of a runtime/executable string source;
the matching sentence was not found in text.flx or misctext.flx. It must not be
attributed to BOOKS-EN merely because a separate book is readable.

## Remaining unknowns

No generic description panel has been established or ruled out. The open book's
actual font/layout/texture path and a final-resolution Unicode bridge remain
UNKNOWN. A bounded read-only constructor/typename trace saw zero target hits in
its sampling interval and detached cleanly; this negative sample does not prove
that either function is absent from every book-related path. No renderer
replacement, simulated page or external overlay has been implemented.

## Controlled runtime source confirmation

Session `npc-01` used exactly one changed book payload (182), preserving all
unselected payloads, opaque bytes and container padding. Rebuilt archive SHA-256
`3dfb9e1ade6211f3fbf46e15f6edd71d38c74b33f85faf1f4e537bfdc1f5b073`,
221305 bytes. The title in the visible body changes to `U9_BOOK_0182`, and
original English paragraphs remain. Native page projection remains intact.
Private image `01-book182-ascii-probe.jpg`, SHA-256
`3f5450dcac21587fb137b1bb38d822133c8af6767c83f718026935b7c66d1527`,
bounded1069x826 capture at configured1600x1200. Runtime remains the frozen
0.2.0-p6s build. The subsequent formal NPC test triggered a renderer guard exit. All original
resources/configuration were restored; this source proof remains valid, while
the session is not a successful normal-exit showcase. See the P6-S2 report.
