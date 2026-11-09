# Phase

P8-3 — Journal Chinese prototype: J2 storage plus a texture-space glyph writer. Authorized by the
human on 2026-11-09 ("1. J2 2. 好喔"). Each game session started only after the human's 「準備好了」.

# Scope

Make one or two journal entries display Chinese on the 3D journal page. Out of scope: line
wrapping, anti-aliasing, books (books-*.flx) and the history timeline.

# Status

PASS WITH LIMITATIONS. Chinese renders on the perspective page in game. Lines overflow the page
because journal width measuring is not hooked yet.

# Environment

- Runtime `U9ChtRuntime/0.2.11-p8-3`, built with Visual Studio 18 2026, Win32, into `.local/p8-3/build` (LOCAL ONLY).
- DLL SHA-256 `6ec3900d49cfdedcc09f052705e305b6d7421ec33263b36ae656f31ceacf8253`.
- Launcher SHA-256 `6a567f67af57c418a62c7beaf0c0c37d2dbe21b2288b983ef1dc62d490d61560`.
- Pack: the P8-1 build (`.local/p8-1/out`), unchanged.
- Rollback: 0.2.9 (`.local/p8-1/build`).

# Inputs

- Journal entries 4078 and 4165 (`category: journal`) from `translation/zh-TW/text.jsonl`.
- A test-only `diary.txt` holding `Day 1: U9J4078` and `U9J4165`, in the private copy only.

# Work Performed

**J2 append (in `engine.cpp`, `wide_hook`).** At return address `0x615DF7`, when the UTF-16 entry matches
an allowlisted plan, the runtime writes `U9J<entry>` instead of the native code-page conversion. The marker
always fits the native `wcslen+1` buffer. If it does not fit, the runtime counts it and leaves the
native conversion in place.

**J2 display (`flow_hook`, `Engine::expand_journal`).**
- When the journal loader (`0x426648`) initializes its text flow, each `U9J<entry>` line ending is
  replaced with the plan's slot string.
- The result goes into a new buffer from the game allocator (`0x7108F0`), and the old copy is freed with
  the game's free (`0x7108E0`).
- STRONG EVIDENCE (static): both loader branches pass `&page+0xC8`, which the game allocates and frees
  itself, so replacing it is safe.
- The span positions are recorded and verified byte by byte at draw time. They are dropped when freed.

**Texture writer (`texture_glyph`, `probe_ink`).** When the hooked glyph function `0x5C5A80` meets a CJK slot
inside a journal span, the runtime draws the Chinese into the page raster itself:

1. **Ink sample.** Once per font and raster type, reference glyphs are drawn privately twice, on two
   different backgrounds. The most common solidly written value, at its most enclosed position, is the ink sample.
2. **Writing.** For each covered pixel of the 16 px glyph (alpha ≥ 112):
   - narrow the raster clip (`+4..+0x10`) to that pixel;
   - let the native blit `0x5E20E0` copy the ink pixel there.

   Pixel format, palette and auxiliary planes stay the game's own; the runtime decodes no format.
3. **Result.** The native draw is skipped and the logical advance (16 − spacing) is returned, as for dialogue.

A failure falls back to the native glyph, is counted, and never forces a quit.

**16 px glyph size.** `TextureEm = 16` is warmed with the existing 20 and 40 px sizes, but only when
capacity allows. Texture drawing is disabled, not fatal, when the 16 px advances disagree with the
logical advances. `U9ChtShowcaseCheck` mirrors this.

**Session runner.** `--diary-fixture` (requires `--preserve-saves`).

# Findings

- CONFIRMED: Chinese drawn into the page texture follows the 3D page's perspective (human screenshot, kept locally).
- CONFIRMED: loading a save rewrites `diary.txt` together with `nonfixed.*` and `processes.dat`.
  The journal is stored in the save and extracted on load, so J2 markers persist with saves.
  A pre-placed fixture is lost on load. The test used a local watcher (scratchpad only) that re-applied
  the fixture after load.
- CONFIRMED: the journal page raster is 16-bit (type 2). The ink sample came from native `I`.
- CONFIRMED: line wrapping uses native widths for slot `0x7F`, which are narrower than 16. Lines run past
  the page clip, and a run of Chinese with no spaces is pushed to its own line after `Day 1:`.
- Visual limitations: 1-bit edges; line spacing is tight for 16 px Chinese in this font.

# Evidence

| Check | Result |
| --- | --- |
| Offline check | PASS: 7,095 plans, 2,291 glyphs, 6,873 cache entries; all 16 px advances = 16 |
| Smoke session (`.local/p8-3/session-smoke`) | exit 0, 17 hooks, 0 errors, raster hashes 6,873 = 6,873 |
| Session 1 (`session-journal`) | exit 0; fixture overwritten by save load, so no texture activity (finding above) |
| Session 2 (`session-journal-2`) | exit 0, 362,270 frames, 0 errors; 1 expansion, 2 spans, 224 texture glyphs, 9,688 pixels, 0 rejects, 0 faults |
| Restoration (all sessions) | protected assets match P0, config restored, preserved saves restored |
| Session 2 log SHA-256 | `4035cb16b4cdf67aa3ca9734b4d9d412c14acaf885f83617e3ba141b6d5748d4` |

The J2 append side (marker writing) was not exercised: no journal entry was added in play (`markers: 0`).

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: 153 run, OK, 3 skipped.

# Results

The native journal page can show Chinese without an on-disk executable patch and without an overlay.

# Files Changed

`runtime/U9ChtRuntime/engine.cpp`, `runtime/U9ChtRuntime/engine.h`, `runtime/U9ChtRuntime/glyph_cache.h`,
`runtime/tools/showcase_check.cpp`, `runtime/CMakeLists.txt`, `runtime/common/version_manifest.h`,
`u9cht/l10n/runtime_pack.py`, `scripts/run_p8_0_session.py`, `docs/research/U9_JOURNAL_PATH.md`, this report.

# Risks

- One native blit per covered pixel: about 43 calls per glyph here. Cheap at journal sizes, but unmeasured for full book pages.
- Save compatibility (accepted with J2): saves made with Chinese journal entries show markers without the runtime.
- The append marker path is untested in play.

# Blockers

None.

# Deviations From Master Plan

None. All hooks are in-memory and reversible; no executable patch on disk.

# Recommendation

1. Find and hook the journal width measuring path, so wrapping uses the 16-unit advance.
2. In a session, trigger a real journal entry to verify the marker write.
3. Then consider line spacing and 2-level ink shading, and extend the writer to books.
