# Phase

P9-3 — Item and object names (TYPENAME.FLX). The human authorized this on 2026-11-09 ("好的，請開始吧~謝謝").
Each game session started only after the human said 「準備好了」.

# Scope

- Translate every player-visible TYPENAME label.
- Run the labels in game.
- Fix any defects found while doing so.

Out of scope: changing how labels are triggered. Hold-X versus hover is recorded as `docs/IMPROVEMENT_BACKLOG.md` IB-1.

# Status

PASS WITH LIMITATIONS.
- The human confirmed Chinese labels in game, including a fix for clipped glyph bottoms.
- All translations are `draft`. Only a few labels were viewed in game.

# Environment

- Runtime `U9ChtRuntime/0.2.15-p9-3`, built into `.local/p9-3/build` (LOCAL ONLY).
- DLL SHA-256 `db1dc990243f1f4d433a3819684c904bc0ceda3e965d467337ea753da1bf52ff`.
- Build output `.local/p9-names/out` (LOCAL ONLY):
  - pack `7e98ab05ad2d8c82009b8604595c7d12233cd033ed3b0b034054148ed1561f0f` (v3);
  - text.flx `852adf9b…ab0a`;
  - TYPENAME.FLX `d00712a7…f821`.
- Font: jf-openhuninn-2.1, set through the settings INI.

# Inputs

- Original TYPENAME.FLX `26c9042d…f4ca`: 8,192 slots, of which 2,032 hold labels (1,154 distinct English strings).
- Glossary `translation/glossary/U9_TERMS.csv`: 529 approved targets cover existing labels.
- Person and place names: harvested from the `譯名(English)` annotations in the 7,368 dialogue drafts, so labels match dialogue (for example 烏鴉, 月光城, 龍衛).

# Work Performed

**Translation**
- 2,026 of 2,032 labels are imported as `draft`. The remaining 6 are developer labels, kept untranslated: `Unused`, `UnusedBow`, `Dont use me use gringolet`, `Minoc Generic Gypsy Female Final`, `Game Controls` and `Stones Music`.
- Every target passed three checks: no Latin letters, at most 12 characters, and only runtime-supported scalars.
- The work files contain the English source and stay in `.local/translation-work/p9-names/`.

**Glossary fixes.** 26 approved item targets had been derived automatically and still contained English, for example `Copper鑰匙`, `Dupre的幽靈` and `來自Raven的字條`. Each was replaced with Chinese and given a note explaining why.

**QA rule.** `annotation_issues` now skips `TYPENAME.FLX`.
- A one-line label (192-unit budget) cannot hold `譯名(English)`, and the convention applies to running text.
- A test covers both the exemption and the unchanged text rule.
- Effect: warnings dropped from 275 to 71. All 71 remaining are the pre-existing dialogue line-count warnings.

**Runtime clip fix (0.2.15).**
- Problem: composited glyphs were clipped to the native raster rectangle. Label rasters are sized for the English font, and CJK glyphs descend further, so the bottom rows were cut (human screenshot of 營火).
- Fix: the clip's bottom edge may now extend by em/4 (10 px at 1600×1200). The left, right and top edges are unchanged.

# Findings

- CONFIRMED (human): world-object labels show Chinese, for example 營火. After the fix the glyph bottoms are complete.
- CONFIRMED: 2,026 name plans load together with the text plans: 9,120 runtime plans and 2,471 glyph scalars, with 7,413 of 16,384 cache entries used.
- Not yet observed: inventory labels beyond the earlier 急救箱, and labels longer than 4 characters.

# Evidence

| Check | Result |
| --- | --- |
| validate | PASS, 0 errors, 71 warnings; layout 0 overflow |
| build | PASS, mutation audit PASS |
| Offline check (jf-openhuninn) | PASS: 9,120 plans, 2,471 glyphs, 7,413 cache entries, prewarm 3,688 ms |
| `session-names` (0.2.14) | exit 0, 19 hooks, 0 errors, 606 composite frames; clipping observed |
| `session-names-2` (0.2.15) | exit 0, 19 hooks, 0 errors, 524 composite frames; clipping fixed (human) |
| Restoration (both) | protected assets match P0, config restored, preserved saves restored, hooks restored |

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: all pass, including the new label-exemption test.

# Results

Item and object names are translated and display in Chinese in game.

# Files Changed

`translation/zh-TW/typename.jsonl`, `translation/glossary/U9_TERMS.csv`, `u9cht/l10n/glossary.py`,
`tests/test_p8a_terms.py`, `runtime/U9ChtRuntime/engine.cpp`, `runtime/common/version_manifest.h`,
`runtime/CMakeLists.txt`, `u9cht/l10n/runtime_pack.py`, `docs/IMPROVEMENT_BACKLOG.md`, this report.

# Risks

- New person names that do not appear in the glossary or dialogue (for example 莫爾丁, 尼科迪莫斯) are first-time transliterations and need human review.
- A few English labels are ambiguous out of context, for example `Amande`, `Ugh` and `Screech`.
- The em/4 extension could let a glyph's descender draw slightly below a box. No such case has been seen.

# Blockers

None.

# Deviations From Master Plan

None. No executable patch on disk. Modified resources exist only in the private game copy during sessions.

# Recommendation

Proceed to books (BOOKS-EN.FLX), reusing the journal texture writer and wrapping.
