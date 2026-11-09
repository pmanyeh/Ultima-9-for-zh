# Phase

P9-2 — Journal line wrapping and Chinese spacing. Authorized by the human on 2026-11-09 ("好的，就依妳的順序").
Each game session started only after the human's 「準備好了」.

# Scope

- Make journal Chinese wrap inside the page.
- Add player settings for journal letter spacing and line spacing.
- Fix overlap between Chinese and the game's italic ASCII glyphs.

Out of scope: line-start punctuation rules (kinsoku), anti-aliased edges, books.

# Status

PASS WITH LIMITATIONS. The human accepted the result in game ("OK，我覺得先這樣"). Known limitations are listed under Risks.

# Environment

- Runtime `U9ChtRuntime/0.2.14-p9-2b`, built into `.local/p9-2/build` (LOCAL ONLY).
- DLL SHA-256 `e177a6df93d0ce66b91301a271bdea6a941af7cb6a3259aa0c33f7fd0b2ed719`.
- Launcher SHA-256 `0f72f5f753c238fcd5154e2501fc210fd7f9c571afba86d02663760454137c5a`.
- An intermediate 0.2.13 build (wrapping only) was tested in session `session-journal`.
- Pack: P8-1 build, unchanged. Font: jf-openhuninn-2.1 through the settings INI.
- Rollback: 0.2.12 (`.local/p9-1/build`).

# Inputs

The test-only diary fixture `.local/p9-2/diary-fixture.txt` holds six markers over two days:
4078, 4165, 12, 28, 4300 (223 characters, 7 authored breaks) and 1583.

# Work Performed

**Static finding (CONFIRMED by disassembly).** Line breaking for the paged text flow is `0x5C6B10`, called
from the flow initializer at `0x5C76BC`.

| VA | Role |
| --- | --- |
| `0x5C62C0` | Word measure up to a byte ≤ 0x20; width lookup at `0x5C6378`, text in ESI. |
| `0x5C6A70` | Line extent `[left, right]` for a y range, minus the page's exclusion shapes. |
| `0x5C6CF7` → `0x5C6D0B` | A word that does not fit the remaining line goes to the next line (`0x5C6EDE`). |
| `0x5C6ED4` → `0x5C6EF6` | A word wider than the whole line is trimmed character by character from its end; width lookup at `0x5C6F5A`, text in EBX. |
| `0x5C6C24`… | Line height = font blob `+4` (word) + font record `+8` (extra line spacing). Records are 12 bytes at `[0x1325A60]`, count `[0x1325A64]`; `+4` is letter spacing. |

Because the native flow already breaks over-long words by character, a run of Chinese with no spaces wraps
correctly once its glyph widths are right.

**Runtime changes**

- Two new in-memory width hooks, `journal_word_width` (`0x5C6378`) and `journal_trim_width` (`0x5C6F5A`), so 19 hooks in total.
  - They override a width only when the text pointer lies inside a verified journal segment and the slot is CJK.
  - Every other text keeps native widths.
- Journal expansion drops authored line breaks.
  - English journal sources contain none (381 workset records, 0 with a newline), so every break was authored for the dialogue width.
  - A break between two ASCII words becomes a space, which restores phrases such as `Sanct Vas` and `Mani In`.
- Journal buffers now hold any number of entries.
  - The previous fixed limit of 64 per diary would have left later entries as raw `U9J` markers.
  - Segments are sorted and found by binary search.
- Letter spacing:
  - Chinese advance = 16 + `letter_spacing`, with the glyph centred in the cell.
  - After a visible ASCII glyph, 3 more units are added, so italic overhang (for example `)`) no longer touches the next Chinese glyph.
- Line spacing: only while the journal page is laid out (inside the `0x5C7620` call for caller `0x426648`), every font record's `+8` is raised by `line_spacing`. It is restored immediately after the call.

**Settings.** New INI section `[journal]`:

| Key | Range | Default |
| --- | --- | --- |
| `letter_spacing` | 0..8 | 2 |
| `line_spacing` | 0..16 | 3 |

Both values are validated by the launcher, by `valid_protocol` and by the runtime. The protocol version is now 2 and `Config` is 8,248 bytes.

# Findings

- CONFIRMED (human screenshots): Chinese wraps at the right edge of each page, and long entries continue onto the following pages.
- CONFIRMED: `Day 1:` and the following Chinese share one line.
- CONFIRMED: the layout is computed once, at flow initialization. Spacing applied during that call holds on every page the human turned to.
- CONFIRMED: closing via the in-game menu exits with code 0 and runtime cleanup completes (two sessions).
  - The P9-1 session closed with the window's ✕ exited with `0xC000041D` and no cleanup log.
  - HYPOTHESIS: the window-close path terminates the game inside a window callback before `ExitProcess`. Not yet compared with an unhooked game.

# Evidence

| Session | Result |
| --- | --- |
| `session-journal` (0.2.13) | exit 0, 19 hooks, 0 errors; 3 expansions, 18 entries, 11,187 width overrides, 48 breaks dropped, 4,840 texture glyphs, 0 faults |
| `session-spacing` (0.2.14) | exit 0, 19 hooks, 0 errors; 1 expansion, 6 entries, 4,092 width overrides, 16 breaks dropped, 2 spaces kept, leading applied 1, 2,967 texture glyphs, 0 faults, 0 rejects |
| Restoration (both) | protected assets match P0, config restored, preserved saves restored, hooks restored, private font removed |

**Launcher validation**

| Case | Result |
| --- | --- |
| `[journal]` with `letter_spacing = 2` and `line_spacing = 3` | exit 0 |
| `line_spacing = 40` | exit 2, "must be 0..16" |
| `letter_spacing = -1` | exit 2, "must be a whole number" |

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: 153 run, OK, 3 skipped.

# Results

Journal Chinese is now readable and laid out by the game itself on the 3D page. Spacing is player-configurable.

# Files Changed

`runtime/U9ChtRuntime/engine.cpp`, `runtime/U9ChtRuntime/engine.h`, `runtime/common/protocol.h`,
`runtime/U9ChtLauncher/main.cpp`, `runtime/common/version_manifest.h`, `runtime/CMakeLists.txt`,
`u9cht/l10n/runtime_pack.py`, `config/u9cht.example.ini`, `docs/research/U9_JOURNAL_PATH.md`, this report.

# Risks

- No line-start punctuation rule: a line can begin with `，` or `」`.
- English words inside Chinese text can be split mid-word (`An C / orp`). The native trim treats the whole space-free run as one word.
- Edges are still 1-bit on the 256 px page texture.
- Raising record `+8` affects any other flow initialized during the same call. None is expected, because the call is synchronous and single-threaded.

# Blockers

None.

# Deviations From Master Plan

None. All hooks are in memory and reversible; no executable patch on disk.

# Recommendation

Keep the journal as is for now, as the human decided. A later pass can add kinsoku (adjust the trim point
at `0x5C6EF6`) and 2-level ink. Proceed to item names (TYPENAME.FLX) and books.
