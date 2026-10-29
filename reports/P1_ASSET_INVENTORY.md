# Phase

P1 — Game Asset Inventory. Evidence 2026-10-28; report 2026-10-29 (Asia/Taipei).

# Scope

Read-only English installation directory/resource inventory. No Japanese
comparison. Only `text.flx` proceeds to payload round-trip under P2.

# Status

PASS WITH LIMITATIONS. Resource families identified to explicit evidence levels;
exact font storage, runtime consumers of every family and locale mappings remain
unconfirmed.

# Environment

Same Windows/Python/Git baseline as P0; standard-library inventory script.

# Inputs

Observed GOG English installation and pinned TITAN source, per P0. Public
`P1_ASSET_INDEX.json` records relative filenames, sizes, SHA-256, container counts,
entry-size distributions and small header samples. No payload dumps are included.

# Work Performed

Inventoried 41 candidate archives, all with bounded version-2 directories.
Counted installation subdirectories: static 375 files, runtime 165, sound 7,
Movies 12, savegame 0. Separate save, speech and video directories are absent;
sound/Speech.flx exists. No resource was written back to the installation.

# Findings

| Resource | Slots / used | Role and evidence |
| --- | --- | --- |
| static/text.flx | 7,656 / 7,656 | CONFIRMED decoded text with 266 source markers and opening subtitle 4164; dialogue role has STRONG EVIDENCE from source grouping/upstream |
| static/misctext.flx | 348 / 340 | STRONG EVIDENCE: short UI/system messages per pinned upstream; payload not round-tripped |
| static/BOOKS-EN.FLX | 4,096 / 460 | STRONG EVIDENCE: readable-object/books family per pinned upstream; encoding not locally established |
| static/TYPENAME.FLX | 8,192 / 8,192 | STRONG EVIDENCE: object names/references per pinned upstream; separate record layout |
| static/bitmap16.flx, bitmapC.flx, bitmapsh.flx | 8,000 / 6,599; 6,576; 6,597 | HYPOTHESIS: possible glyph/bitmap search candidates; no font entries located |
| static/Mbrk.*, Tbrk.*, Tnbrk.* | 348 / 340; 7,656 / 7,656; 8,192 / 8,192 | STRONG EVIDENCE: locale/dialect variants from filenames, counts and upstream; suffix-to-language mapping UNKNOWN |

CONFIRMED: FLX-like archives also occur under non-.flx extensions (texture and
dialect variants). A filename-extension-only inventory is insufficient.
No standalone filename containing “font” was found by this candidate scan.
Exact font storage may instead involve bitmap entries or executable resources;
that remains UNKNOWN. BOOKS-EN's language suffix is observed; other language
installs and cross-locale compatibility have not been compared.

# Evidence

`P1_ASSET_INDEX.json`, P0 hashes, `docs/formats/U9-FLX-NOTES.md`,
`docs/research/reference-projects.md`. Initial index encoding/consumer fields
remain UNKNOWN where only container inventory was performed; the table above
adds explicitly attributed upstream evidence rather than claiming payload proof.

# Tests

`python scripts/inventory.py --game-dir $env:U9_GAME_DIR --output reports/P1_ASSET_INDEX.json`:
exit 0; “Inventoried 41 resources; no payloads exported”. The output is
create-only; repeat with a fresh output path. Header/table/payload bounds were
checked for all candidates. Synthetic inventory checks are included in the final
test suite; source bytes remain unchanged.

# Results

Dialogue, UI, books, object-name and locale-variant leads are separated by
resource family. Font candidates are hypotheses, not a font implementation.
The text-only P2 scope is retained.

# Files Changed

`scripts/inventory.py`, `tests/test_inventory.py`, `P1_ASSET_INDEX.json`,
this report and `docs/formats/U9-FLX-NOTES.md`.

# Risks

Identical container layout does not establish identical payload encoding. Upstream
consumer descriptions do not replace local runtime validation of each family.

# Blockers

No blocker for text.flx round-trip. Native CJK/font conclusions require later
authorized research; Japanese oracle currently unavailable.

# Deviations From Master Plan

Actual directory names are savegame/Movies, not save/video; speech is inside
sound/Speech.flx. Non-.flx candidate extensions were included to avoid omissions.

# Recommendation

Proceed only with text.flx under the already-authorized P2. Do not generalize
the text importer to books, names or locale variants.
