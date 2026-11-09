# Phase

P9-5 — Book translation (BOOKS-EN.FLX), following the P9-4 runtime route. This work belongs to the order the human approved on 2026-11-09.

# Scope

Translate every player-readable book, note and sign as a `draft`, without changing gameplay data.

# Status

PASS WITH LIMITATIONS.
- All translatable text records are drafted and validated.
- An in-game spot check of the full set has not been run yet. Only books 182 and 233 have been confirmed in game (P9-4).
- All records are `draft`. None has had human language review.

# Environment

- Runtime `U9ChtRuntime/0.2.19-p9-5` (adds U+30FB to the runtime scalar list).
  - Build `.local/p9-5/build`, DLL SHA-256 `99613334ce1e348865eb8727e0dff7fed439dea189c27f108b90b58aea5aceb1` (LOCAL ONLY).
- Build `.local/p9-5/out` (LOCAL ONLY):
  - pack v4 `6c7da4242bbd717b4477558f8c085d0619f10de1043dcbff6e00d1f09b7caf46`;
  - BOOKS-EN.FLX `aec100af…ed03`.

# Inputs

- BOOKS-EN.FLX: 451 text records exported to a local workset (`.local/translation-work/p9-books/`).
- The glossary, and the dialogue annotations for names.

# Work Performed

- 26 batches. Each batch: export → apply → import → validate.
- Each target was checked against its source for:
  - identical `` `f ``/`` `p ``/CRLF/NUL token order;
  - runtime-supported scalars only;
  - no bare CR and no U+3000;
  - glossary annotations (`譯名(English)`).
- Where a glossary name is a different thing in context (for example a grave for an unrelated Jim, or Grey as a colour), the record notes declare `not a term: X`.
- Gargish passages (font `` `f5 ``) are left as written. Only their English "(Translation)" sections are translated.
- Mantras, incantations and passwords (`BEH`, `SUMM`, `Sanct Vas Grav In Mani An Corp`, `Vas Kal An Mani In Corp Hur Tym`) stay in English, as they do in dialogue.
- Glossary corrections:
  - `Iolo Fitzowen` now uses the full-width middle dot U+30FB, because U+00B7 and U+2027 are proportional in jf-openhuninn.
  - `Chest of the Troll` is an enchanted chestpiece. It is now 巨魔胸甲 in the glossary and in the item names.

# Findings

- 391 of 451 records are translated.
- 60 records are deliberately left untranslated:

  | Records | Reason |
  | --- | --- |
  | 55 shop data files (`#id "name" $price` lists, for example 186–225) | Read by the shop interface, not the book page. Needs its own research. |
  | 161 | An embedded binary document; opaque. |
  | 144 `INOPIA`, 459 `Keelhaul` | Passwords the player types. |
  | 155 | Intentional gibberish. |
  | 457 | A coordinate diagram with no words. |

- QA gap found: an ideographic space (U+3000) has no glyph raster, and it made `validate` stop with "incorrect grayscale raster size" instead of reporting an issue. The batch tool now rejects U+3000. The validator itself is unchanged.

# Evidence

| Check | Result |
| --- | --- |
| validate (development) | PASS, 0 errors, 71 warnings (all pre-existing dialogue line-count warnings) |
| build | PASS, mutation audit PASS; 9,785 runtime records → 9,511 plans |
| glyphs | 2,718 scalars, 0 missing |
| Offline check | PASS with jf-openhuninn-2.1 and with Noto Sans CJK TC (8,154 / 16,384 cache entries) |
| ctest | 6/6 passed |

# Tests

`python -m unittest discover -s tests`: all pass.

# Results

Books are translated and ready for an in-game spot check.

# Files Changed

`translation/zh-TW/books.jsonl`, `translation/zh-TW/typename.jsonl` (one fix), `translation/glossary/U9_TERMS.csv`,
`runtime/U9ChtRuntime/identity.cpp`, `runtime/common/version_manifest.h`, `runtime/CMakeLists.txt`,
`u9cht/l10n/runtime_pack.py`, `u9cht/gdi_raster.py`, this report.

# Risks

- Long books have not been seen in game. Wrapping and page breaks follow the native flow, which P9-4 verified on two books.
- Several new names are first-time transliterations and need human review.
- Book titles in the separate title field remain English.

# Blockers

None.

# Deviations From Master Plan

None.

# Recommendation

1. Run one in-game session that opens several long books, including the Keyboard Commands and the Earth tutorial.
2. Then decide between the shop interface (55 shop files) and misctext.flx.
