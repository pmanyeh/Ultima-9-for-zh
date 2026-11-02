# TYPENAME evidence — P6-S2

2026-11-01; pinned executable and game baseline from P0. This resource is
independent of the UTF-16 text.flx payload format.

## Confirmed local format

- SHA-256 `26c9042d2e8f0f55559c84c22113ae62348ed0694375ad02b4fe65fea9e3f4ca`;
  134,200 bytes, 8,192 used slots. Slot IDs remain unchanged.
- Each payload begins with a six-byte `<iH` pair. The signed i32 and u16 are
  preserved, with no modification of their gameplay meanings.
- 6,160 records contain only that header. 2,032 contain a NUL-terminated ASCII
  label after it; every local label byte is below128. No local post-terminator
  bytes were found. Synthetic tests nevertheless preserve such unknown bytes.
- Payload offsets occur in all four modulo4 classes. There is no inferred
  alignment padding requirement. Existing non-payload bytes are copied exactly.
- No BOM or UTF-16 label storage was found. ASCII is empirically established;
  behavior for non-ASCII legacy bytes remains UNKNOWN. The current writer rejects
  Chinese rather than claiming an unverified on-disk encoding.
- Export → serialized JSON → import is BYTE-PERFECT PASS, with identical SHA-256,
  size and zero differences. This does not yet prove runtime loading or Chinese.

## Reference and implementation

TITAN0.7.8 / tgwUltima commit
`2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`, `titan/u9/typename.py`, is a format
reference. Its field names suggest readable-text and icon references; actual
selected-object runtime behavior must confirm these meanings. The project reuses
the already validated TITAN container reader through `Archive`, with a separate
payload parser and source-layout writer. The upstream generic writer regenerates
unknown container bytes, so it is unsuitable for the preservation requirement
already documented in `docs/research/reference-projects.md`.

Private receipts and source export: `.local/p6s2/`. The public repository contains
synthetic fixtures only. Object/type correlation was initially pending; the
later controlled5290 probe and Chinese result are recorded below. Unobserved
candidate IDs from archive labels remain leads, not inventory evidence.
## Additional static consumer leads (not runtime confirmation)

The pinned executable has two directly decoded calls to the label-copy helper
at VA0x553770:0x49A438 and0x53606D. The latter proceeds to a formatted diagnostic
message box; it must not be classified as inventory-label rendering merely
because it requests a type name. The former constructs a native widget through
0x41ACE0, which duplicates the narrow label and measures it through0x5C5E50.
This is a **STRONG EVIDENCE** candidate for an object label. Its selected runtime
type ID, inventory applicability, lifetime and final pixel path remain UNKNOWN.
No new hook or Unicode routing change follows from these static leads alone.

## Single-entry inventory probe

Slot5290's ASCII label was changed from `First Aid Kit` to
`U9_FIRSTAID_5290` in a private copy, after the exact round-trip above.
The audit establishes that only payload5290 changes; all other payloads,
unknown header bytes and padding are preserved. Modified size134203 bytes;
SHA-256 `7285f08e58689c8a7907a5ca5ba24fd08099aa746cf4211310bff8b81dc0916c`.

The private `typename-probe-04` session uses bootstrap mode: no Unicode hooks
or font are enabled, text/books remain original. A white first-aid object was
moved from the belt into the open backpack through the native drag interaction.
Its visual appearance alone does not establish type5290. The marker must still
be observed through the native held-X examine labels and correlated with the
resource-copy/widget/font/width/raster chain. A brief key press produced no
label and no trace observations; this is inconclusive, not a path failure.

The bounded hardware-debug-register probe changes no executable instructions
and restores debug state on detach. Its initial candidate points are0x553770
and0x41ACE0; downstream sampling is enabled only after the exact marker matches.
Neither a selected-item ID nor Unicode support is promoted to CONFIRMED yet.

## Final checkpoint -2026-11-02

The subsequent held-X runtime trace and saved ASCII screenshot confirmed5290
for the real backpack object. The narrowly extended0.2.3 route then displayed
the Chinese draft `急救箱` (human confirmed), completed404 final composites and
retired four owned-label/raster/queue lifetimes. These later measurements
supersede the earlier pending consumer/identity statements above. Details and
hashes are in `docs/research/P6S2_INVENTORY_LABEL_PATH.md`.

The Chinese name remains a Unicode plan; on-disk storage is the ASCII marker
`U9T14AA`, not an inferred multibyte Chinese encoding. The private modified
archive SHA-256 is
`7a765bf78a8dd6c9fd7812bb2c347208a5ae1e04d8eea8e6152b64aab606e432`.
Only5290 is changed. No Chinese inventory screenshot was saved, final exit1
lacks cleanup records, and the full inventory category is incomplete. Original
assets/settings are restored. The human requested stopping PoC and committing
the checkpoint; no further resource expansion follows.
