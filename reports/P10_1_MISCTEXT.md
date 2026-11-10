# Phase

P10-1 — System and UI text (misctext.flx), in game. Includes the misctext UI bridge M1, runtime
`0.2.20`–`0.2.27-p10-1`. The order and the new hook sites were authorized by the human on 2026-11-10.

# Scope

- Make misctext.flx translations reach the screens that show them.
- Fix every in-game defect found while doing so.
- In scope: the options page, table of contents, main-menu buttons, message box, bestiary, sign messages,
  and save-slot texts.
- Out of scope: the clock message (an executable string) and shop lists.

# Status

PASS WITH LIMITATIONS.

- In game, the human confirmed Chinese, without visual defects, on: the options page, table of contents,
  main-menu buttons, message box, bestiary pages and sign messages.
- Not individually confirmed in this phase: the save/load page labels, the spellbook (102–158) and the stats page.
- Remaining limits are listed under Risks.

# Environment

All paths below are LOCAL ONLY.

- Pinned English `u9.exe`, SHA-256 `83915175…b545`.
- Runtime `U9ChtRuntime/0.2.27-p10-1`.
  - Build: `.local/p10-misc/build/Release`.
  - DLL SHA-256 `558b33ab0d1aeb9fb34e5fa20d79befd1bc8323f47f45ca266ab5c2bd4b1e604`. This matches the hash session-9 loaded.
- Output `.local/p10-misc/out-m8`:
  - pack v4 `d9c01d81…1a283`, with 10,027 plans and 2,724 scalars (0 missing);
  - misctext.flx `544dcf5e…3dd5`;
  - BOOKS-EN.FLX `8cf03253…def8`.
- Font: jf-openhuninn-2.1 (`.local/p9-2/u9cht.ini`). Offline check PASS.
- Static analysis: capstone 5.0.7 through local helpers (not tracked).

# Inputs

- misctext.flx store: 242 drafts. 243 before the review removed entry 255.
- BOOKS-EN store, with one heading revised.
- Two private saves, continued through `--seed-saves`.

# Work Performed

Ten in-game sessions in total, session-1 to session-9 (session-1 used the pre-M1 runtime 0.2.19).
Each session ran start → human play → finish (restore and verify). Every finish restored the protected
assets, saves, configuration and `Default.kmp`.

| Session | Runtime | Result | Action |
| --- | --- | --- | --- |
| 1 | 0.2.19 | Every misctext surface showed magenta `0x7F` dots | Research: UI copies the text inline, so the constructor binding is lost |
| 2 | 0.2.20 (M1) | Crash on Ctrl+O | Marker lead `0x1E` < `0x20` → native "Invalid character encountered in print." |
| 3 | 0.2.21 | Options, table of contents, buttons and message box Chinese | Problems found: buttons off-centre, bestiary drop cap, message box overflow |
| 4 | 0.2.22 | Centring and bestiary title fixed | Problems found: message box overflow, signs still dots |
| 5 | 0.2.23 | Message box inset | Signs traced to the message area |
| 6 | 0.2.24 | Signs Chinese, but black | Problem found: inset lost on re-flow |
| 7 | 0.2.25 | Re-flow inset fixed; signs still dark | — |
| 8 | 0.2.26 | Signs still dark | Pixel classes logged; aux-plane hypothesis disproven |
| 9 | 0.2.27 | **Signs: light fill with dark outline** | Other fonts' inks unchanged |

Translation review by the human:
- misctext 255 "Bestiary of Britannia" stays in English, because the decorative drop-cap title is preferred.
- BOOKS-EN 1, heading "Beasts" → 怪獸／敵人, because the list includes human foes.

# Findings

All addresses are VAs in the pinned executable. Full evidence: `docs/research/U9_MISCTEXT_UI_PATH.md`.

- **CONFIRMED: misctext provenance.**
  - Entries are read only through the named-text factory `0x616120`.
  - The length and read functions (`0x545990`, `0x5459F0`) each have that single caller, and they use the archive global `0xAE7C4C`, which is loaded from `misctext.flx`.
  - The factory constructs the string object with return address `0x6161AB`.
- **CONFIRMED: why the text was lost.** UI code copies `obj+0` inline (`strlen` + `0x7108F0` + `rep movs`).
  Copies of the runtime's opaque `0x7F` slots therefore lose their plan binding.
  Slot patterns cannot be matched back to plans by content either: 207 of 243 targets share a pattern with another target.
- **CONFIRMED: the text-flow initializer `0x5C7620` keeps the caller's `char**`** (`flow+0x14`).
  Buffers must therefore be changed in place, never replaced.
- **CONFIRMED: the draw-string routine `0x5C5C00`.**
  - It dispatches bytes `0x00`–`0x0D` itself. Every other byte goes to the glyph function `0x5C5A80`.
  - That function returns NULL below `0x20`, which leads to the native fatal error.
  - Any marker byte must therefore be ≥ `0x20`.
- **CONFIRMED: options labels** are measured with `0x5C6240`, then copied into a label widget
  (`vtable 0x742D18`, text `+0x24`) and drawn by `0x41F710` → `0x5C5C00`. They never pass through a text flow.
- **CONFIRMED: the bestiary title** (`0x4260F1`) prints `text[0]` as a `"\x0C\x11%c"` drop cap and `text+1` as the title.
- **CONFIRMED: the message box** (`0x41F2C3`) builds its text rectangle `(0x1C,0x26,0x9C,0x50)` on its own stack and
  passes it to the flow initializer (return `0x41F305`).
- **CONFIRMED: signs are books.**
  - `0x5E96F0` reads the book id from object property `0x4D`, then calls the book reader `0x42E560`.
  - The result goes to the screen message routine `0x624680`, whose holder `0x41BBB0` copies it at the existing hook site `0x41BC61`.
  - The book reader compacts markup in place, in its own conversion buffer.
- **CONFIRMED: font inks** (pixel classes logged in session-8).
  - The message font (height 21) is a thick `0x8000` outline around a thin, multi-shade light core.
  - The aux plane is unused, which disproves the hypothesis from session-7.
  - Book fonts (height 18) and the height-15 UI font are single dark strokes with anti-aliased edges.

# Evidence

Implementation, runtime 0.2.27-p10-1:

| Site | Kind | Role |
| --- | --- | --- |
| `0x615A10` ctor (existing) | inline | When the return address is `0x6161AB`, write `marker + slots` (marker `0x8F` + 3 base-94 digits) into `obj+0`. Entry 255 gets a leading space for the drop cap. |
| `0x5C7620` flow init (existing) | inline | Strip markers in place and record segments. Inset the message box rectangle by 8 px per side when it holds Chinese, including re-flows. |
| `0x5C5C00` draw_string (**new**) | inline, bytes `8B 44 24 08 53` | Unbounded calls strip markers from the label's own buffer. |
| `0x5C6240` string_width (**new**) | inline, bytes `57 8B 7C 24 08 33 C0` | Width of marked text = native width of the stripped text + Σ(texture CJK advance − native `0x7F` width). |
| `0x41BC61` holder copy (existing) | inline | Bind a copy of the pending sign book like a book page. Strip markers from other unbound copies. |
| `0x5C5A80` glyph (existing) | inline | Texture glyph writer. Ink probe: enclosure rule; outlined fonts get an 8-way outline. |

Final session-9 counters: `errors=0`, texture `faults=0`, `rejects=[0,0,0,0]`, `leaks=0`, `book_messages=7`,
`message_insets=7`.

Inks per font:
- height 21: outlined, fill `0xD73B`;
- height 15: `0x98C6`;
- height 18: `0x80A8` and `0xA447`. These are unchanged since session-4.

Session logs (LOCAL ONLY, `.local/p10-misc/session-N/runtime.jsonl`), SHA-256 prefixes:
- session-2 `c66ab8a9`
- session-3 `083698e3`
- session-4 `27dc21be`
- session-5 `5a7c4f94`
- session-6 `fc0da18b`
- session-7 `f133b72e`
- session-8 `6d670301`
- session-9 `8ca78dc9`

Screenshots were provided by the human in chat. They are not stored in the repository.

# Tests

- `ctest` (runtime): 7/7 PASS. New: `U9ChtMiscMarkerTests`, which covers encode/decode, printable bytes, concatenation, digits after a plan, truncation, malformed markers and re-flow.
- `python -m unittest discover -s tests`: 161 OK, 3 skipped (LOCAL-ONLY asset tests).
- `scripts/build_localization.py`: PASS, 0 errors, 71 warnings. The warnings are pre-existing and identical in kind and count across builds.
- Offline pack/font check (`U9ChtShowcaseCheck`, jf-openhuninn): PASS.
- Integrity note: the first 0.2.27 build failed (C4456 treated as error). It was committed as `29db2fb` before the failure was noticed, and tests had run against the previous binaries.
  It was fixed in `819552c`, rebuilt, and verified by the DLL version string, the hash match, and a re-run of tests and the offline check.

# Results

- misctext is now usable in game on the confirmed surfaces.
- Sign messages, which are BOOKS-EN, now render readable Chinese.
- `translation/resource-capabilities.json` raises misctext `translate_build` and `unicode_runtime` to CONFIRMED.
  - `unicode_runtime` stays `bounded`: only the surfaces listed in its notes are confirmed.

# Files Changed

- `runtime/U9ChtRuntime/misc_marker.h` (new) and `runtime/tests/misc_marker_tests.cpp` (new).
- `runtime/U9ChtRuntime/engine.cpp`, `engine.h`, `runtime/CMakeLists.txt`, `runtime/common/version_manifest.h`.
- `u9cht/l10n/runtime_pack.py`: runtime contract `misc_ui_marker`.
- `translation/zh-TW/misctext.jsonl` (entry 255 removed) and `translation/zh-TW/books.jsonl` (BOOKS 1 heading).
- `translation/resource-capabilities.json`.
- `docs/research/U9_MISCTEXT_UI_PATH.md` (new), `docs/HANDOFF.md`, and this report.

# Risks

- **Marker visibility.** A misctext string drawn through a path not covered above would show `0x8F` plus three ASCII digits.
  - The `leaks` counter detects this; it stayed 0 in sessions 3–9.
  - Bounded `0x5C5C00` calls are not stripped (`bounded` stayed 0).
- **Marker length.** Marked caches are up to 4 bytes longer than English for 34 strings. The observed copies are heap `strlen`-sized; a fixed stack copy elsewhere would be a risk.
- **Sign book binding.** It relies on the holder copy immediately following the conversion (a `pending_book_buffer` address match).
- **Message area resolution.** Sign text is drawn into a low-resolution message raster, so it is softer than dialogue subtitles.
- **Glyph size.** CJK glyphs are a fixed 16 px. They are large in small fonts. Font heights are now logged for future scaling.
- **Ink rule regression.** Inks were unchanged for the fonts seen. Fonts not yet seen use the new rule untested.
- **Review.** All misctext drafts are still `draft`.

# Blockers

None.

# Deviations From Master Plan

- Two new in-memory hook sites were added (`0x5C5C00`, `0x5C6240`), both authorized by the human. The executable on disk is unchanged.
- The work ran in iterative test-fix rounds within the one authorized phase.

# Recommendation

1. Run one short session to confirm the save/load labels, the spellbook (Ctrl+Shift+1 cheat key) and the stats page.
2. Then pick the next item:
   - font-relative CJK sizing for small fonts;
   - shop lists (55 BOOKS-EN files);
   - the clock message, which is an executable string and needs its own authorization.
