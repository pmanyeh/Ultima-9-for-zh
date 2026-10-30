# Phase

P5 — High-Resolution Traditional Chinese Unicode Renderer PoC, 2026-10-30.

# Scope

Explicitly authorized P5-A–F, **text.flx entry 4164 only**. Investigate native
resolution, retain UTF-16 identity, preserve native Latin, then test 中, 中文 and
`Avatar 中文 TEST`. No P6, translation expansion or replacement graphics pipeline.

# Status

**PASS WITH LIMITATIONS.**

**HIGH-RES UNICODE POC PASS — bounded presented-frame experiment.**
Resolution classification: **R3, CONFIRMED**. The required glyphs and mixed line
were visibly rendered into the actual 1600×1200 game target, with a matching
800×600 comparison. This is a reproducible debugger-driven single-frame PoC,
**not a persistent renderer or playable Chinese build**. Its capture hold lasts
at most 40 seconds, then normal execution resumes. All private game resources
and starting window configuration have been restored after testing.

# Environment

- Windows 11, x64 host / x86 WOW64 game; windowed existing DirectDraw wrapper.
- Python 3.12.10, Git 2.55.0.windows.3; .NET SDK 10.0.302 present, unused by the PoC.
- Existing optional Capstone distribution 5.0.9 (module reports 5.0.7), static
  disassembly only. No new package/native-library dependency.
- English GOG installation: product 1207659093, build 59198760502252807. Precise
  historical patch label UNKNOWN; executable SHA-256 is the compatibility lock.
- TITAN/tgwUltima pin `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`;
  prior Japanese-oracle tooling pin `c5db7b77b93a3b99b27556c3e5d8654d1679ced5`.
- Starting repository HEAD `36d03ce6d33ed09e60db569a96344d686493e868`, branch main.

# Inputs

| Input | SHA-256 |
| --- | --- |
| English u9.exe | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| Pristine text.flx | `378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0` |
| Existing private ddraw.dll | `f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502` |
| Development font | `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4` |

Noto Sans CJK TC Regular, 16,435,884-byte OTF, version
`2.004;hotconv 1.0.118;makeotfexe 2.5.65603`, upstream commit
`165c01b46ea533872e002e0785ff17e44f6d97d8`:
[pinned font](https://github.com/notofonts/noto-cjk/blob/165c01b46ea533872e002e0785ff17e44f6d97d8/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf),
[SIL OFL 1.1](https://github.com/notofonts/noto-cjk/blob/165c01b46ea533872e002e0785ff17e44f6d97d8/LICENSE).
The binary/license remain private, with process-private registration, no global
font installation. Selected face name and complete GetFontData SHA-256 match the
explicit file. U+4E2D maps to glyph 9544; U+6587 maps to glyph 20036.

# Work Performed

1. Rechecked baseline hashes, ignored asset locations and the existing 55 tests.
2. Traced the selected original English raster through cache construction,
   explicit queue movement and native-resolution triangle submission.
3. Read bounded wrapper surface descriptors, then experimentally performed a
   zero-pixel-write Lock/Unlock on the existing backbuffer before native Flip.
4. Implemented a bounded UTF-16 sidecar, verified byte-cache copy inheritance,
   scalar-specific metrics and suppression of the native CJK placeholder bitmap.
5. Rasterized licensed Unicode glyphs directly for final output pixels; blended
   grayscale coverage into the locked native backbuffer, then used original Flip.
6. Ran single-glyph, two-glyph, mixed-line and two-resolution tests. Rejected the
   first clipped mixed-line result and corrected the second native width reader.
7. Closed every test process, restored pristine text.flx and original private
   800×600 window settings, reverified all five protected assets, ran final tests.

# Findings

## High-resolution boundary and resolution — CONFIRMED

The original subtitle raster is **595×37, RGB555, pitch 1190 bytes** at both tested
configured resolutions. Its cached texture geometry scales by 2.5 at 1600×1200.
The selected queue's initial(35,393) position moves to(23,8) through native
`0x509270`; a complete unchanged raster hash plus the observed move resolves
provenance. Pointer equality alone was insufficient and was not accepted.

The later existing backbuffer is **1600×1200 / pitch 6400** or
**800×600 / pitch 3200**, XRGB8888, masks 00FF0000/0000FF00/000000FF, no alpha mask.
The best tested boundary is **after EndScene and before primary-surface Flip at
VA 0x597B1A / RVA 0x197B1A**, locking backend field +0x3FC3C4. Scene state must be
inactive. Lock/Unlock/Flip each returned 0; CPU general/stack registers matched
their saved values on return. Native executable instructions remain unchanged.

The cached descriptor's pointer is never used as permission to write. Actual
[Lock](https://learn.microsoft.com/en-us/windows/win32/api/ddraw/nf-ddraw-idirectdrawsurface7-lock)
establishes the access interval. Half-open clipping intersects the transformed
subtitle rectangle with the actual output rectangle. Coverage blends directly
against locked RGB, retaining X bytes, followed by corresponding Unlock.

## Unicode transport and native Latin — CONFIRMED for selected runs

Strategy B retains and verifies the original UTF-16 at dual-string object+8.
For the selected complete string only, conversion is bypassed with a capacity-
checked ASCII/opaque-slot cache at+0. Each Unicode scalar has one 7F slot; its
actual identity remains immutable host metadata. No CP950/Shift-JIS round-trip,
lead/trail detection or decoding of individual ANSI bytes occurs.

Only the observed complete source→destination copy at 0x41BC58→0x41BC61 inherits
that identity; free notifications revoke buffers. Every selected width/draw
checks the live registered bytes. Scalar offsets identify the glyph, never its
placeholder value. Cache content hash, queue lifetime and output scale are
checked before compositing; ambiguous provenance aborts.

Latin calls use unchanged native bitmap drawing. CJK draw at 0x5C5A80 is suppressed
and returns a private metric header; both native width consumers use the same
advance. The initially missed tight-bounds reader at 0x5C5F62 clipped TEST. A watch
on the common opaque font slot now covers both it and layout reader 0x5C7BBA.
The final mixed cache is 142×22 instead of 120×22, with complete native TEST.
This is selected-run measurement, not implementation of P6 wrapping.

Assumptions disproven: the original glyph dispatch is a final-resolution target;
initial queue coordinates remain fixed; pointer equality alone proves lifetime;
and changing only the layout width site is sufficient for mixed-line sizing.

## Japanese architecture reuse

Reused concepts: alternative Unicode routing, one logical-character advance,
separate scalar/glyph metrics, native bitmap fallback, and cached run metadata.
Rejected mechanisms: CP932/OEMCP/Shift-JIS pairing, 188-column slots,
SHIFTJIS_CHARSET/MS P Gothic assumptions and fixed32/64-pixel packed rasters.
No Japanese executable bytes or proprietary fonts were copied into the PoC.

## Rasterizer / quality — CONFIRMED

GDI Unicode **GetGlyphIndicesW + GetGlyphOutlineW(GGO_GRAY8_BITMAP)** is selected
for this bounded BMP experiment. It provides direct final-size grayscale
coverage for the measured CPU-lockable target without another graphics device
or a COM font bridge. DirectWrite remains preferable for broader future Unicode
work; it was not implemented. Unsupported scalars/glyphs fail explicitly.

Coverage0–64 expands to0–255; actual rasters contain intermediate values.
No ClearType or glyph enlargement is used. Target em is 16 logical units times
the measured scale. The PoC composites each alpha sample to one final-target
pixel. Wrapper/desktop/capture-wide DPI transforms are outside that operation;
logical screenshot dimensions alone are not resolution evidence.

| Output | Scalar | Requested em | Raster / final-target footprint | Bearing x/y | Advance |
| --- | --- | --- | --- | --- | --- |
| 800×600 | 中 | 20px | 16×19 | 2/17 | 20px |
| 800×600 | 文 | 20px | 19×19 | 1/17 | 20px |
| 1600×1200 | 中 | 40px | 32×37 | 4/34 | 40px |
| 1600×1200 | 文 | 40px | 38×38 | 2/35 | 40px |

The selected mixed native cache has the **same SHA-256 at both resolutions**,
while Chinese rasters and final-target footprints increase separately. Chinese
therefore bypasses that low-resolution cache. Integer native advances 16 map
exactly to 20/40 final pixels. Common logical baseline y 20 produces stable
alignment; the one-pixel bearing difference is handled per glyph.

Single-glyph foreground was initially white. Later tests use RGB 181/132/239 from
the predominant bright native subtitle color. Native Latin shading stays intact;
the Chinese uses a flat tint, not an attempted reproduction of baked Latin bevels.

# Evidence

Portable metadata, exact resource hashes, metrics, destination coordinates,
rejected result, screenshot hashes and rollback verification are in
[P5_HIGHRES_UNICODE_POC.json](P5_HIGHRES_UNICODE_POC.json).
Detailed addresses/algorithm/rollback:
[U9_TEXT_SURFACE_PIPELINE.md](../docs/research/U9_TEXT_SURFACE_PIPELINE.md).

| Test | Private runtime evidence | Visual result |
| --- | --- | --- |
| 0: native English baseline | surface-1600-05.json; original source/glyph/cache→triangle; windowed 3D evidence | Native path functioning, no modifications/crash |
| 1: single 中 | single-1600-01.json | PASS: one correct glyph followed by native English |
| 2: 中文 | two-1600-01.json | PASS: two lookups/draws, no overlap/duplicate/placeholders |
| 3a: mixed, initial | mixed-1600-01.json | REJECTED: native TEST tail clipped |
| 3b: mixed, corrected | mixed-1600-02.json | PASS: complete `Avatar 中文 TEST` |
| 4: resolution comparison | mixed-800-02.json vs mixed-1600-02.json | PASS: correct complete mixed line at both outputs |

JSON files above are under`.local/p5-highres/`. Gameplay screenshots remain under
`.local/evidence/`: P5_SINGLE_1600_20261030.png, P5_TWO_1600_20261030.png,
P5_MIXED_1600_20261030.png and P5_MIXED_800_20261030.png. The failed mixed capture
is also retained locally. The first800 run measured correctly but its hold ended
before screenshot capture; the second supplies the visual evidence.

# Tests

- Before: `python -m unittest discover -s tests -v`, local assets configured:
  **55/55 PASS, 0 skipped, exit 0**.
- After: same command with restored local assets: **65/65 PASS, 0 skipped,
  exit 0**. Ordinary run without assets: 64 PASS, 1 explicitly LOCAL-ONLY skip.
- Ten new synthetic tests cover scalar segmentation/routing, scalar identity,
  exact advance/scaling, unsupported fallback rejection, copy lifetime/address
  reuse, XRGB surface/pitch validation, grayscale padding/coverage, clipping,
  blend endpoints/intermediate coverage and the call-stub failure/return path.
- GDI offline face/hash/glyph/raster tests: PASS. Zero-pixel-write surface call:
  **LOCK UNLOCK PASS**, allocation freed, clean detach.
- All completed Unicode captures: Lock/Unlock/Flip=0, registers restored,
  cleanup_errors empty; no crash or second-chance exception.
- An intermediate asset-enabled test run encountered the running game's exclusive
  file lock. Closing the process resolved it; the final 65-test run passed. No
  failing test was disabled or baseline expectation weakened.
- `git diff --check`: PASS. No game/font binaries, dumps, screenshots or local
  machine paths are staged or included in public changes.

# Results

**Resolution:** R3. **Unicode transport:** retained UTF-16 sidecar. **中:** PASS.
**中文:** PASS, exactly two logical glyphs. **Mixed line:** PASS after the documented
measurement correction. **Latin regression:** selected native appearance/call
path preserved; unrelated tutorial UI continued normally. **High resolution:**
direct 20/40px rasterization and 1:1 final-target composition, not small-raster
magnification. This establishes the requested bounded PoC, not full-game coverage.

Unchanged pristine text.flx export→import is **BYTE-PERFECT PASS**, rechecked by
the final local integration test. Intentional diagnostics are **EXPECTED
SINGLE-ENTRY MUTATION / RUNTIME PASS**, not unchanged round-trips:

| Mutation | File size | Changed payloads | Physical changes |
| --- | --- | --- | --- |
| single | 1,200,660 unchanged | 4164 only | 2 bytes, entry start 676832; no offsets/header/padding changes |
| two | 1,200,660 unchanged | 4164 only | 4 bytes; no offsets/header/padding changes |
| mixed | 1,200,660→1,200,430 | 4164 only, payload 260→30 | -230 bytes; 3491 later offsets relocate predictably; size fields update; all other payloads/unknown padding preserved |

The mixed positional difference count 250894 reflects relocation, not 250894
semantic changes. Full private diff ranges remain in the mutation audit.
After rollback all five protected files match P0, and both private configuration
files match their starting 800×600 backups. The original installation was not
written. No executable instruction bytes changed at any point.

# Files Changed

- This report and its portable JSON.
- `docs/architecture/P5_UNICODE_RENDERER_OPTIONS.md` — implemented Strategy B,
  measured R3 boundary, font choice and limits.
- `docs/research/U9_TEXT_SURFACE_PIPELINE.md` — evidence notebook and rollback.
- `scripts/probe_p5_surface.py`, `scripts/probe_p5_lock.py` — bounded surface and
  zero-pixel-write integration probes.
- `scripts/poc_p5_unicode.py` — private build/selected-run/presented-frame PoC.
- `u9cht/gdi_raster.py`, `u9cht/p5_unicode.py`, `u9cht/p5_surface.py`,
  `u9cht/p5_call.py` — raster, identity, clipping/blending and bounded native call.
- `tests/test_p5_unicode.py`, `tests/test_p5_surface.py` — synthetic tests.

# Risks

This mechanism is debugger-driven, hash/version/wrapper locked, BMP-glyph limited
and tested for one selected subtitle/frame. It is not a usable continuous game
patch. Other resource families, font changes/control-rich runs, runtime mode
changes, fullscreen, device loss, concurrent object mutation and extended Unicode
remain unverified. Global font substitution is rejected. Texture/native Latin
styling is preserved, but Chinese uses its own flat antialiased style.

An interrupted call retains its own executable allocation so it can unlock and
return after detach; a 4096-byte metric page is conservatively retained until
process exit. Every test process was subsequently closed. The experiment uses
no DLL injection or independent overlay. Code/context/heap and actual pixel
writes are distinct; the notebook lists each selected redirection and rollback.

# Blockers

No remaining blocker for this bounded P5 result. A **persistent, narrowly scoped
renderer with robust redraw/cache/device lifecycle and a normal rollback/launcher**
is still required before this can be offered as a playable implementation.
That requirement is not claimed complete by the frame captures.

# Deviations From Master Plan

The human's specific P5 high-resolution prompt replaces the larger glyph-subset
example. It explicitly authorizes the minimal runtime interception used here.
Only two Chinese glyphs and entry 4164 were tested; GDI is the accepted bounded BMP
alternative to preferred DirectWrite. No P6 typography/wrapping work occurred.

# Recommendation

Keep this as a validated technical PoC. Complete a separately scoped persistent
P5 integration and repeat its lifecycle/regression checks before authorizing P6.
**Do not begin P6 automatically.**
