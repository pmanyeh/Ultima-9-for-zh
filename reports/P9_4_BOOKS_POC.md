# Phase

P9-4 — Chinese books (BOOKS-EN.FLX): find the runtime path and prove it with two books. Authorized
as part of the human's order on 2026-11-09 ("好的，請開始吧~謝謝", followed by "已正常離開遊戲，就繼續下一步吧").
Each game session started only after the human's 「準備好了」.

# Scope

- Find how books reach the screen.
- Choose a storage format for Chinese book bodies.
- Make books 182 and 233 render in Chinese with correct wrapping and colour.

Out of scope: translating the remaining books, book titles, and line-start punctuation.

# Status

PASS. The human confirmed Chinese books in game with the correct ink colour ("OK了").

# Environment

- Runtime `U9ChtRuntime/0.2.18-p9-4c`, built into `.local/p9-4/build` (LOCAL ONLY).
- DLL SHA-256 `4c39b4482a2bf82256d6f15dc4712823a90ab504b6933d18e2d3817e45e02de6`.
- Build `.local/p9-books/out` (LOCAL ONLY):
  - pack v4 `8cbb57cf23d0ef510314ea7baa30ae5ee00733c3a3a240b4a612c8bc683292cc`;
  - BOOKS-EN.FLX `0457477f1b0a118ea45bea2b6d46cd1f725b09df0dbbf41583803cc640f25075`.
- Font: jf-openhuninn-2.1, loaded through the settings INI.

# Inputs

- Original BOOKS-EN.FLX `a0653ef3…858b`: 460 used slots, of which 451 are text records exported to the workset.
- Book 182 ("On the Reading of Books"): the existing P6-S2 draft.
- Book 233 ("Equipping Items"): a new draft.

# Work Performed

**1. Observe session (0.2.16).**
- A new log event `flow_text` recorded the caller, length, hash and first 48 bytes of each flow text. Output was unchanged.
- The human opened several books.
- Result: books use flow caller `0x42687A`.
- The caller `0x4260C6` (P8-2 called it a "book page") reads `0x42E560(2)` and is part of the journal book. The caller `0x42771F` copies a fixed string.

**2. Static analysis of the book reader `0x42E560` (CONFIRMED by disassembly).**
- It reads entry `id−1` through the FLX object.
- If the body starts with `FF FE`, it treats the body as UTF-16LE:
  - it copies the body without the BOM;
  - it **overwrites the last UTF-16 unit with NUL**;
  - it converts with `WideCharToMultiByte(CP_ACP, …, -1, …)`, which returns to `0x42E64A`.
- Then it compacts markup in place:

  | Source | Result |
  | --- | --- |
  | CRLF or lone CR | LF |
  | `` `p `` or `` `P `` | `0x0B` |
  | `` `f1``–`` `f5`` (either case) | `0x0C` followed by the font code `0x0B` / `0x0A` / `0x0C` / `0x0F` / `0x10` |

  The compaction only removes bytes, so the order of the remaining bytes is preserved.
- Cross-check: the observed flow hashes of books 182 and 233 reproduce exactly from their bodies under this rule.

**3. Storage format.**
- A Chinese book body is `FF FE` + UTF-16LE text + one NUL unit. The NUL unit absorbs the reader's overwrite.
- `BookArchive` gains `body_text` and `encode_body`, and the token sequence (`` `f ``, `` `p ``, CRLF, NUL) must still match the source.
- ASCII bodies keep their original single-byte form.
- `BooksAdapter` now edits `body_text`.
- The store accepts tabs in book targets, because sources indent paragraphs with tabs.

**4. Runtime pack v4.**
- Header: text hash, TYPENAME hash (64 zeros when no names are included), then the BOOKS-EN hash.
- Book plans use entry `0x20000000 | id` and may hold up to 8,192 UTF-16 units. They may contain CR and tab.
- Book plans have their own hash index and never join constructor matching.
- The engine verifies the installed BOOKS-EN hash before READY.

**5. Runtime path.**
1. At `0x42E64A`, an exactly matching book plan is written as its slot string, with CJK becoming `0x7F`. That plan is held until the next flow initializer.
2. When `0x5C7620` is called next, the k-th `0x7F` in the flow text is bound to the k-th non-ASCII scalar of the plan. If the counts differ, nothing is bound.
3. Books then use the journal machinery: width hooks (stages 6 and 7, plus fallback in the layout and bounds hooks, which book pages use), the texture writer, letter spacing, the ASCII gap and line spacing.

**6. Ink fix (0.2.18).**
- Problem: book fonts are anti-aliased, and each glyph carries several shades. The old probe chose the most frequent shade, which was a light edge tone (`0xEAB1`), so the Chinese came out pale red.
- Fix: the probe now chooses the darkest shade that occurs at least twice. A single-shade font, such as the journal font, gives the same result as before.

# Findings

- CONFIRMED (human): both books render in Chinese. Wrapping, page turns and spacing are correct, and the colour now matches the native English text.
- CONFIRMED: the journal history tab reads the same reader (`0x42E560(2)` → entry 1), so translating book entry 1 covers it.

# Evidence

| Session | Result |
| --- | --- |
| `p9-4/session-books-observe` (0.2.16) | exit 0, 0 errors; book caller identified |
| `p9-books/session-poc` (0.2.17) | exit 0; 2 converts, 2 bound, 0 mismatches, 1,104 width overrides, 979 glyphs, 0 faults; ink `0xEAB1` (pale) |
| `p9-books/session-ink` (0.2.18) | exit 0; 3 converts, 3 bound, 0 mismatches, 1,658 width overrides, 1,756 glyphs, 0 faults; ink `0x80A8` (human: correct) |
| Restoration (all) | protected assets match P0, config restored, preserved saves restored, hooks restored |

**Offline check:** PASS, pack v4 with 9,122 plans.

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: 156 run, OK, 3 skipped.
  - New tests cover UTF-16 book bodies: BOM, terminal NUL unit, round-trip, and rejection of token changes, embedded NUL and double edits.
  - Updated tests reflect the new book capability.

# Results

Books can be translated through the normal pipeline and appear in Chinese on the native book pages.

# Files Changed

- Pipeline: `u9cht/books.py`, `u9cht/l10n/adapters.py`, `u9cht/l10n/runtime_pack.py`, `u9cht/l10n/pipeline.py`, `u9cht/l10n/store.py`.
- Runtime: `runtime/U9ChtRuntime/identity.h`, `runtime/U9ChtRuntime/identity.cpp`, `runtime/U9ChtRuntime/engine.cpp`, `runtime/U9ChtRuntime/engine.h`, `runtime/common/version_manifest.h`, `runtime/CMakeLists.txt`.
- Tests: `tests/test_books.py`, `tests/test_p7_pipeline.py`.
- Translation data: `translation/resource-capabilities.json`, `translation/zh-TW/books.jsonl`.
- This report.

# Risks

- Without the runtime, a Chinese book shows code-page conversion garbage. Saves are unaffected.
- Book titles (the separate title field) are still English. Where they appear is not yet established.
- There is no line-start punctuation rule, so a line can begin with `，`.
- Book bodies with an embedded binary document (book 161) or non-ASCII bytes remain opaque and untranslatable.

# Blockers

None.

# Deviations From Master Plan

None. All hooks are in memory. Modified resources exist only in the private game copy during sessions.

# Recommendation

Translate the remaining 449 books in batches through the workset, then run one in-game spot check.
