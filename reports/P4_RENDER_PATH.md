# Phase

P4 — Text Decode / Mapping / Renderer Path Investigation.
P4-C2 continuation completed 2026-10-30 (Asia/Taipei), following the partial
2026-10-29 checkpoint. P4-A/B findings are retained; they were not restarted.

# Scope

Authorized English-only diagnosis of entry 4164 in the private runtime copy,
with independently verified windowed execution before tracing. No P5, executable
patch, buffer/iteration patch, font installation, renderer modification, DLL
injection, Japanese patch application or Japanese asset acquisition.

# Status

**PASS WITH LIMITATIONS** for the authorized P4-C2 diagnosis on the frozen English
build. The conversion-to-width-to-bitmap chain is established. This does not mean
Chinese renders correctly, that a native CJK path has been proved, or that P5 is
authorized. Japanese differential remains NOT EXECUTED.

# Environment

Python 3.12.10, Git 2.55.0.windows.3, 64-bit Windows Python / WOW64 game.
Continuation begins at commit `879b721f381978461dd5d367ab9c1d2e8cc5483f`.
Optional, already-installed Capstone: distribution 5.0.9 / module 5.0.7,
BSD-style license. No dependencies installed. TITAN pin
`2b6ee659cb153254ea8e3d2787d601a6fa79f3d2` remains unchanged.

# Inputs

GOG English game ID 1207659093 / build 59198760502252807; patch label UNKNOWN.
Executable SHA-256:
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Pristine text.flx:
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.
Controlled P3-B text.flx:
`68548b8a78092c85a70267303c6077553b7ff32257368942c5937bc8765d0e04`.
Entry 4164 changes only the first UTF-16 unit to U+4E2D; file size, entry size,
header, offsets and every other payload remain unchanged.

Read the master plan, project rules, P4 JSON/Markdown and both research notebooks.
Original assets stay outside tracked paths; all runtime assets/evidence stay in
ignored `.local/`. No copyrighted asset is staged.

# Work Performed

## Retained P4-A/B checkpoint

The source-only Japanese mechanism audit remains pinned to UltimaPatcher commit
`c5db7b77b93a3b99b27556c3e5d8654d1679ced5`: static-tree copy, delta-generated
u9.jp.exe and Locale Emulator launcher. Exact compatible Japanese basis and
native CJK internals remain UNKNOWN. No patch payload was acquired/applied.
See [Japanese source audit](../docs/research/U9_JAPANESE_PATCH_PATH.md).

The English PE/import/resource findings remain valid. Import presence alone was
not used to select a subtitle architecture. See
[English notebook](../docs/research/U9_ENGLISH_TEXT_STATIC.md).

## Windowed prerequisite

CONFIRMED: only the private copy was configured. An initial 800x600@60 attempt
failed: the existing configuration GUI did not retain that unsupported mode and
the game measured as a 1920x1200 popup. No trace ran in that failed launch.

Using the existing private dxcfg.exe GUI, selected **800x600, 120 Hz** and
**Presentation: Windowed**, then saved. Exact settings:

```ini
; dxcfg.ini [general]
display=800x600@120
presentation=windowed
```

Private Options.ini: GameScreenWidth=800, GameScreenHeight=600, Game Rasterizer=2.
Verified on an unmodified-text launch after entering the actual 3D bedroom:
caption present, outer rectangle [691,363,1228,790], logical client 533x400,
desktop 1920x1200, window DPI 144. The logical dimensions reflect DPI scaling;
requiring them to equal configured 800x600 would incorrectly reject this window.
All three subsequent traced launches were also observed as titled small windows.

Private configuration SHA-256 after verification:

- dxcfg.ini: `8d8205706681446766de9530d7b895baae9ffa5f72b4202090d0acbab50f4f1b`
- Options.ini: `a27aae90f71379577eaa453eb742bfb02e94a13aeca94c45946770ad08f461fa`

The trace launcher now rejects missing/unverified receipts, desktop-sized clients
and changed configuration hashes. The original installation's display setting
independently differed from its P0 snapshot; it was preserved, never written or
reverted by these actions. Its executable and protected resources still match P0.

## Hardware-only C2 tracing

Three bounded runs, each rebuilding the same P3-B mutation from pristine data.
Only CPU hardware debug registers and bounded read-only memory inspection were
used. No game-memory writes, software breakpoint insertion or injected calls.

GetACP was observed through the resolved target IAT after executable entry;
target return VA 0x71D0DB yielded EAX=950 in all three runs. The host ACP=950 is a
separate observation.

Grouped-REP following was runtime validated: source prefix, initial copied bytes,
REP completion and complete destination prefix were checked before switching the
watch. Width/glyph probes require that destination's live prefix and a source
pointer at offset 0 or 1. The render entry additionally requires caller return
0x5C5D09 and the selected pointer recovered from the caller stack. These are
specific call-site checks, not a claimed complete stack unwind.

Every run stopped on the first later prefix-invalidating write. That event and
all subsequent recycled-address activity are excluded. All runs detached/restored
debug registers without cleanup errors, and the game continued without an
observed crash before being closed normally.

# Findings

All VA/RVA pairs use image base 0x400000. Heap addresses below are from trace 05
only and vary between runs.

| Required question | Answer and evidence |
| --- | --- |
| 1. Target process ACP? | CONFIRMED: GetACP returns 950, independently of host ACP=950. |
| 2. Exact post-cache ANSI buffer? | CONFIRMED: cache object +0 points to 0x036B4F40, prefix `a4 a4 76 61 74 61 72 2c`. Verified REP copy at VA/RVA 0x41BC58/0x1BC58 produces the same prefix at 0x03805A70. |
| 3. One DBCS character or two bytes? | CONFIRMED: two independent unsigned 0xA4 values, from source+0 and source+1. Layout increments one byte at 0x5C7C60; rendering increments one byte at 0x5C5D57. No lead-byte pairing on this observed path. |
| 4. Width/layout representation? | CONFIRMED: ANSI bytes. Layout function 0x5C7870/0x1C7870, width lookup 0x5C7BB3/0x1C7BB3. Both bytes independently produce width 11, spacing 0. |
| 5. Glyph lookup representation? | CONFIRMED: byte 0xA4, table index 132 (0xA4 minus 0x20), slot offset 0x430; both select font-relative glyph offset 0xA458. Glyph function 0x5C5A80/0x1C5A80. |
| 6. Renderer/font path? | CONFIRMED: custom indexed bitmap font, dispatch call 0x5C5ABB/0x1C5ABB to 0x5E20E0/0x1E20E0, renderer mode field 2. Runtime font content matches both bitmap archives' entry 611; details below. Final surface/backend calls were not separately traced. |
| 7. Why two symbols in P3? | CONFIRMED mechanism: U+4E2D survives in wide storage, CP950 emits observed A4 A4, and two byte lookups draw the identical bitmap at (0,20) and (11,20). Whether that bitmap is intentionally a missing-glyph fallback is UNKNOWN. |
| 8. 130-byte sizing assumption? | CONFIRMED for this constructor: wcslen+1 bytes allocated and passed to conversion; 260 entry bytes = 130 UTF-16 units including NUL. CP950 needs 131 bytes here. Not a survey of every executable path. |
| 9. Final classification? | **E — MULTIPLE FAILURES**, comprising A conversion/capacity and D custom encoding/SBCS assumption under the current C2 labels. |
| 10. Justified P5 strategy? | Separate capacity correctness from character iteration/glyph/layout design. A capacity-only change or Windows font installation cannot fix this byte renderer. First prefer lawful native CJK-path comparison if later available; otherwise request authorization for a minimal native bitmap/encoding design investigation. No implementation is authorized now. |

The central two-symbol hypothesis is **CONFIRMED** as a processing mechanism.
A correct logical U+4E2D glyph ID never reaches the observed lookup; classification
C (correct glyph requested but absent) is therefore not established.

Minimal observed algorithm:

```text
b = unsigned byte at current text pointer
slot = font + 0x10 + (b - 0x20) * 8
glyph = font + u32(slot)
advance = low byte of u32(glyph) + spacing
draw indexed bitmap; advance text pointer by one byte
```

This summary applies to the observed printable-byte branch, not control tokens.

## Font content attribution

A bounded 76,832-byte runtime span was hashed without saving its payload:
`b3f3135ee84447b879d8558cea4589695c8f15be7694585906b2bd213d1af2f8`.
This equals the entire entry 611 in both:

- bitmap16.flx, offset 35,067,710; archive SHA-256 `3ec4ece8540c64ac7717d431267d2ab85a8612ccf119b78c36a299021ad1adcb`
- bitmapC.flx, offset 22,583,458; archive SHA-256 `fc968e348918239ac4a0a8d1694bcf9e6f6b58f3ddcbe8bc7e2d2ae7084d6ad2`

Both bytes select the same bitmap within that content, width 11 and height 15.
Earlier partial-header matches to entry 544 were not promoted to font identity;
its whole-entry hashes differ. Which identical entry-611 disk copy was opened
was not traced. The selected path uses custom bitmap lookup/dispatch; this does
not claim GDI text APIs are unused elsewhere or establish every backend call.

## Capacity defect

At 0x615B4D–0x615B76 the wide length determines allocation and API byte capacity:
129 wide units excluding NUL, plus one = 130 bytes. Wide storage itself is
allocated at two bytes per unit. The selected call returns zero, then error 122;
the failed output prefix is nevertheless copied into the ANSI cache and used.
The complete converted tail was not measured; no specific final-character loss
is asserted. This diagnosis changes no capacity or error handling.

# Evidence

[P4_RENDER_PATH.json](P4_RENDER_PATH.json) contains portable hashes, addresses,
trace summaries and window settings. Raw traces 03/04/05 remain ignored under
`.local/p4-c2/`; local visual evidence is
`.local/evidence/P4_C2_WINDOWED_20261030.png` (hash in JSON).
No asset payloads, full text dump, font data, stack dump or screenshots are
published. Original traces 01/02 remain historical evidence with their original
provenance limitations.

# Tests

Before C2: `python -m unittest discover -s tests -v`, U9_GAME_DIR configured:
**38 run, 38 passed, 0 skipped, exit 0**.

After C2: same command/environment:
**39 run, 39 passed, 0 skipped, exit 0**. Added synthetic window-receipt rejection
coverage; no tests launch the game. Existing P0–P4 checks were not weakened.

Runtime validation: trace 03 = 46.110 s, 12 data events / 11 valid-prefix events;
trace 04 = 49.782 s, 14 / 13; trace 05 = 59.328 s, 14 / 13. One verified copy per
run. Traces 04/05 each recorded two width, two glyph and two bitmap-dispatch
observations. Each final invalidation event is excluded from text attribution.
No cleanup errors, second-chance crash or unexplained runtime failure observed.

# Results

Windowed 3D execution works and private settings are retained. The opening
Chinese character still renders incorrectly; its two-symbol mechanism is now
attributed to two byte-indexed bitmaps, alongside a separate conversion-capacity
defect. P3 has not been retroactively marked successful.

Each intentional mutation passed the existing single-entry/layout-preservation
validator. This is not an unchanged round-trip equality claim; the prior P2
BYTE-PERFECT PASS remains unchanged. After normal game exit, private text.flx was
restored to pristine, no U9 process remained, and all five protected assets in
both original/private trees matched P0. No original installation file was written
by this batch.

# Files Changed

`scripts/trace_p4.py`, `u9cht/wintrace.py`, `tests/test_wintrace.py`, this report,
`reports/P4_RENDER_PATH.json`, `docs/research/U9_ENGLISH_TEXT_STATIC.md`.
Private configuration, receipts, traces and visual evidence remain ignored.

# Risks

Results are specific to this executable, subtitle and printable-byte path; do
not generalize to books, UI, other languages or every renderer. Hardware tracing
is experimental and baseline-locked. The font hash span is a bounded diagnostic
based on independently inspected local candidates, not a new font-format parser.
No unknown bytes were normalized or discarded.

# Blockers

No blocker remains for the authorized English C2 attribution. Native CJK support,
Japanese binary differences, intended fallback semantics, exact source archive
open and final surface/backend details remain UNKNOWN / NOT EXECUTED. They limit
future implementation choices. P5 requires explicit human authorization.

# Deviations From Master Plan

The user explicitly permitted English-only P4 without an available Japanese
oracle. Three controlled replays reused the same one-character P3-B diagnostic;
no translation expansion occurred. The initial window-mode validation failed and
was corrected before tracing. The 2026-10-29 paused checkpoint is historical;
its old E=UNKNOWN label is superseded by the user's current A–F classification.

# Recommendation

Stop after this P4 diagnosis. Review the two confirmed failure components before
selecting a P5 design. Prefer native CJK evidence when lawful local inputs become
available; otherwise define a separately authorized minimal bitmap/encoding
investigation addressing character iteration, widths and glyph capacity together.
Do not proceed with buffer patches, a Windows-font-only fix, overlay, broad
renderer rewrite or Japanese executable patch on the strength of this report.
