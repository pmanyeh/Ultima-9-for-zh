# Phase

P2 — FLX Text Round-Trip, limited to text.flx. Binary test 2026-10-28;
runtime/resume and report 2026-10-29 (Asia/Taipei).

# Scope

Read → structured JSON export → source-locked import → binary verification →
independent-copy runtime smoke. No actual game string changed. P3 not executed.

# Status

PASS WITH LIMITATIONS. **BYTE-PERFECT PASS** and **RUNTIME PASS (startup smoke)**
are separate results; no CJK rendering claim is made.

# Environment

Windows/Python baseline in P0. Independent game copy `.local/runtime-game/`.
GOG DirectX 1–7 wrapper 1.1.0.6423; glide2x.dll 2.61.00.0658 also present.
Active renderer backend and inherited Windows compatibility flags were not traced.
Configured game display 1600×1200; captured screenshot 1920×1200.

# Inputs

Observed GOG English installation, exact patch label UNKNOWN. Executable SHA-256:
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.

Original and rebuilt text.flx SHA-256:
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.

# Work Performed

Reused the unchanged, pinned MIT TITAN container reader with strict prevalidation.
Implemented structured export, source SHA/metadata checks, Unicode decoding and
original-layout rebuilding. Preserved every unknown non-payload byte; did not
normalize headers, reorder payloads or synthesize alignment.

Exported all 7,656 entries to `.local/working/text.json`, imported to
`.local/output/text.rebuilt.flx`, and verified equality. Created an independent
595-file installation copy (~1.74 GB) and placed the unchanged rebuilt resource
there. Launched the copy, observed the opening scene/subtitle and closed the copy
through its quit UI. Original installation resources were not overwritten.

# Findings

CONFIRMED: 7,656 UTF-16LE-decodable entries; single trailing NUL, no BOM,
6–1,072-byte entry lengths, zero inter-entry padding/trailer. 3,823 offsets are
not 4-byte aligned. No supplementary characters appear; engine UCS-2 versus
UTF-16 surrogate support remains UNKNOWN. Structural details and diagnostic
samples are in `P2_TEXT_STRUCTURE.json` and the format notebook.

CONFIRMED: opening subtitle matches entry 4164 (offset 676832, size 260).
Modified entry ID: none. Before/after short excerpt is unchanged:
“Avatar, arise from your slumber!” No crash was observed in the smoke test.

Assumptions disproven: generic repacking cannot be assumed to preserve unknown
bytes, and four-byte alignment cannot be assumed for text entries. Unicode
storage alone does not prove Chinese glyph availability.

# Evidence

| Check | Result |
| --- | --- |
| Original size / rebuilt size | 1,200,660 / 1,200,660 bytes |
| Differing bytes / ranges | 0 / none |
| Changed header fields | none |
| Changed offsets or lengths | none |
| Changed padding | false |
| Changed semantic content | false |
| Round-trip | BYTE-PERFECT PASS |
| Startup runtime smoke | RUNTIME PASS |

Structured evidence: `P2_ROUNDTRIP_DIFF.json`, `P2_TEXT_STRUCTURE.json`,
`P2_RUNTIME.json`. Local screenshot: `.local/evidence/P2_20261029_startup.png`.
The screenshot is intentionally ignored, not packaged or committed.

# Tests

```powershell
python -m unittest discover -s tests -v
python -m u9cht text export "$env:U9_GAME_DIR/static/text.flx" --output .local/working/text.json
python -m u9cht text import "$env:U9_GAME_DIR/static/text.flx" --input .local/working/text.json --output .local/output/text.rebuilt.flx
python -m u9cht verify-roundtrip "$env:U9_GAME_DIR/static/text.flx" .local/output/text.rebuilt.flx
```

Export/import/verify each exit 0; 7,656 entries exported, 1,200,660 bytes rebuilt,
BYTE-PERFECT PASS. Create-only outputs require fresh names when repeating.
The initial suite ran 19 tests: 19 passed with local assets configured, or
18 passed/1 skipped without them. The final suite ran 23 tests: 23 passed with
local assets configured. A clean clone without assets ran 23 tests: 22 passed,
1 LOCAL-ONLY test skipped. Both exit 0; exact results are in `VALIDATION.json`.

Synthetic tests cover empty/ASCII/extended/CJK strings, BOM and multiple NUL
preservation, unused slots, aliases/conflicting edits, odd lengths, malformed
Unicode/terminators, bad bounds/tables, partial overlap, non-index physical order,
unknown bytes/gaps/trailer, resizing, tampered metadata and CLI overwrite/privacy
guards. LOCAL-ONLY integration is skipped when U9_GAME_DIR/assets are absent.

# Results

Exporter, importer and byte-equality checks pass for the exact observed baseline.
Runtime smoke passes for the executable copy with the rebuilt resource present.
No file-I/O trace was collected; the observation proves successful startup and
matching rendered text, not an independent trace of the archive open call.

# Files Changed

`u9cht/`, `tests/test_flx.py`, `tests/test_cli.py`,
`tests/test_local_integration.py`, P2 reports/evidence metadata, README and format
notes. Licensed upstream source/notice are included; all game-derived exports,
rebuilt FLX, runtime copy and screenshots remain ignored.

# Risks

Runtime testing covers startup only. Synthetic resizing/Unicode support in tools
does not establish engine behavior for changed content. Full translation-token,
glyph, length and layout QA is future work; the editing code is not a production
translation pipeline. Importers for other resources are not validated.

# Blockers

None for unchanged text.flx baseline. CJK glyph availability is UNKNOWN; there
is no Japanese oracle. P3 requires explicit authorization before any real edit.

# Deviations From Master Plan

Retained template bytes instead of using the upstream generic repacker, justified
by reproducible unknown-byte loss. Runtime was delayed by the user's pause and
completed after resumption. Used a private full copy instead of replacing a live
installation resource. Exact patch label remains unknown and is recorded as such.

# Recommendation

Recommend authorizing a separate P3 batch for one visible, safe string only,
starting with an ASCII control edit before a CJK test. This batch stops at P2;
Chinese display, glyph mapping, fonts and wrapping have not been tested.
