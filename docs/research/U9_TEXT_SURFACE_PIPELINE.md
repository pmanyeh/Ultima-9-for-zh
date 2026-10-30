# English subtitle surface pipeline — P5

2026-10-30. Entry 4164 only, pinned English executable SHA-256
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Private wrapper SHA-256
`f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502`.
This notebook records measurements, not a Unicode rendering PASS.

## Resolution gate — CONFIRMED R3

At configured 1600×1200 in a visually verified windowed 3D scene:

| Stage | Measurement |
| --- | --- |
| Native glyph dispatch `0x5C5ABB` → `0x5E20E0` | 595×37 subtitle raster, 16-bit RGB555, stride 595 pixels / 1190 bytes |
| Cache paint return `0x5CFD99` | Local widget rectangle (0,0,595,37); original position (35,393) |
| Queue call `0x5CFDB6` → `0x508D50` | Selected raster, position (35,393), three texture tiles |
| Native move `0x5CFF1C` → `0x509270` | Same raster moved to (23,8); full raster SHA-256 unchanged |
| Triangle submit `0x50913A` → virtual +0x60 / `0x589F50` | x/y scales 2.5 / 2.5000002384; first vertex (57.5,20.0000019) |
| Backend object vtable `0x74FBB8` | Width +0x44 =1600; height +0x48 =1200; bits +0x4C =32 |
| Primary surface field +0x3FC3C0 | 1600×1200, pitch 6400, 32-bit RGB, masks 00FF0000/0000FF00/000000FF, alpha mask 0 |
| Backbuffer field +0x3FC3C4 | Same dimensions, pitch and pixel masks; DDSCAPS_BACKBUFFER present |

The subtitle is rasterized into a smaller bitmap and submitted as scaled textured
geometry to a native-resolution backend. Chinese inserted into that small raster
alone would be **RESOLUTION LIMITED**. A later native-resolution surface exists;
safe locking/compositing and Unicode transport are separate gates.

Private evidence: `.local/p5-highres/surface-1600-05.json`, clean debug detach,
plus `.local/evidence/P5_1600_WINDOWED_20261030.png`. The earlier 800×600 sample
also has a 595×37 native subtitle raster. DPI-scaled window screenshots alone
were not used to infer render-target dimensions.

## Provenance correction

The first triangle sample (`surface-1600-02.json`) checked pointer equality only.
Its coordinates differ from the initial queue position. It was not accepted as
selected-subtitle evidence until the cause was investigated. A hash/geometry
guard in run 03 rejected the movement; a hardware data watch in run 04 identified
the write at `0x5092EC` (trap EIP `0x5092EF`). Static review established that
`0x509270` explicitly translates every queued tile. Its caller `0x5CFF00` reads
the widget rectangle and passes the selected raster to that method.

Run 05 observed this call with matching manager/raster, retained source prefix,
unchanged complete raster hash, no queue destruction, and the expected updated
geometry at submission. Thus the movement is now explained and checked, rather
than silently ignored. This establishes the **English raster** chain; the future
UTF-16 bridge must independently establish its source/copy lifetimes.

## Surface descriptors — CONFIRMED metadata, not a lock

For this pinned wrapper, the game-visible surface vtable is `0x18153838`.
GetSurfaceDesc (+0x58) forwards via wrapper +8 to root +0xC (inner vtable
`0x18152DF4`). Its implementation copies 31 DWORDs from inner interface +0x3C,
that is root +0x48. Both descriptor sizes are 124 and pixel-format sizes 32.
Only bounded descriptors were read; no surface image was exported.

A cached non-null lpSurface is **not** permission to access pixels. Microsoft's
[Lock contract](https://learn.microsoft.com/en-us/windows/win32/api/ddraw/nf-ddraw-idirectdrawsurface7-lock)
limits pointer validity to the corresponding lock interval. A compositor must
lock successfully, validate format/pitch/rectangle, blend only inside that
rectangle, and [unlock](https://learn.microsoft.com/en-us/windows/win32/api/ddraw/nf-ddraw-idirectdrawsurface7-unlock)
before presentation.

## Candidate native-resolution boundary — STRONG EVIDENCE

The engine ends its D3D scene through `0x59A0D4` (device vtable +0x18).
`0x597B1A` calls primary-surface Flip (surface vtable +0x2C). Candidate:
after verified EndScene and before this Flip, lock the existing backbuffer,
composite directly in final pixel coordinates, then unlock. No independent
window, replacement graphics pipeline or low-resolution Chinese atlas is needed
if this bounded integration succeeds. Actual lock/write behavior is not yet
verified. Surface alpha is absent; grayscale coverage must be blended into RGB.

### Bounded call experiment / rollback

`scripts/probe_p5_lock.py` is explicitly different from the read-only probe. It
allocates 8192 private bytes in the game (RW data page + RX code page), redirects
the render thread's EIP at `0x597B1A` / RVA `0x197B1A`, then returns there. Original
instruction bytes `FF 51 2C` remain untouched; there are no replacement bytes in
the executable. The generated call bytes and runtime addresses are logged.

The generated 97-byte stub saves flags/general registers and FXSAVE state, calls
the existing backbuffer's stdcall Lock (+0x64) with a bounded rectangle and
DDLOCK_WAIT|DDLOCK_NOSYSLOCK, then conditionally calls Unlock (+0x80), restores
state, and jumps to the original Flip call. Two NOPs are hardware execution
markers, not software breakpoints. Its error branch skips Unlock on failed Lock.
The host first verifies EndScene's backend state flag is clear. This experiment
only reads a four-byte sample while locked; it performs **zero pixel writes**.

Normal rollback: return outside the allocation, verify registers, free it,
restore debug registers, detach. Interrupted rollback: retain any executing
allocation, restore debug registers and continue; the stub unlocks/restores/
returns without a live debugger. The OS releases retained memory on game exit.
No archive is changed. This narrowly scoped existing-surface call does not
replace the game's renderer. Runtime result will be recorded after execution.

**CONFIRMED runtime:** `.local/p5-highres/lock-1600-01.json` records Lock=0,
Unlock=0, 1600×1200/pitch6400 while locked, zero pixel writes, all eight saved
general/stack registers restored, temporary allocation freed, clean detach.
The game subsequently continued into the ordinary bedroom scene without a crash.

## Selected UTF-16 bridge experiment / scope

`scripts/poc_p5_unicode.py` builds only entry 4164 from the pristine template,
validates the independent single-entry diff, and requires that exact private
archive to be present before launch. Modes are single, two, mixed; they must be
run in that order with visual review between them. No other resource changes.

Runtime control redirections (original code bytes are **not** overwritten):

| VA / RVA | Operation |
| --- | --- |
| `0x615B76 / 0x215B76` | Match complete authoritative UTF-16; fill its allocated byte cache with native ASCII plus one opaque 7F slot per Unicode scalar; return the equivalent stdcall result, retain original wide buffer |
| `0x615BDC / 0x215BDC` | Verify object +8 still has identical wide data and object +0 has exact opaque-slot cache |
| `0x41BC58` → `0x41BC61` | Verify full source/destination copy and holder +0xEC association; inherit immutable Unicode metadata only along this observed edge |
| `0x5C7BB3 / 0x1C7BB3` | For verified Unicode slots only, redirect the table-offset result to a private one-byte metric header; require exact physical-to-logical advance including native spacing |
| `0x5C5A80 / 0x1C5A80` | For verified Unicode slots only, suppress native bitmap drawing and return that metric header; record scalar and local baseline; delegate every Latin call unchanged |
| `0x597B1A / 0x197B1A` | After validated cache→queue→native-resolution submission, use the tested bounded Lock/Unlock stub and blend only the final-size glyph rectangle |

Entry-4164 wide content, scalar offsets, verified copies and free notifications
establish identity; individual ANSI bytes are never decoded back to Unicode.
The placeholder has no character-encoding meaning. Unsupported glyphs, malformed
Unicode, unexpected copies, changed cache hash, queue destruction, mismatched
dimensions or non-integral metric representation abort the experiment.

Chinese requested em =16 logical units times measured output scale: 20 physical
pixels at 800×600, 40 at 1600×1200. Glyphs are rasterized directly at that size.
Coverage is blended into locked BGRX rows, preserving X bytes, bounded by both
the transformed subtitle cache rectangle and output rectangle. The experiment
captures one presented frame and holds it for at most 40 seconds for local
screenshot evidence, then detaches. This is a bounded PoC, not a persistent
playable renderer. One 4096-byte metric page is conservatively retained until
game exit to prevent a dangling return value if interrupted mid-glyph.

Rollback: exit the private process, restore its pristine text.flx, verify all
protected hashes. The original game installation and u9.exe bytes stay intact.
Runtime and visual results are recorded below and in the phase report.

### Single and two-glyph results — CONFIRMED runtime + visual

- `.local/p5-highres/single-1600-01.json`: U+4E2D, one logical draw, native
  advance16 →40 output pixels; final raster32×37, bearing4/34, placed(69,36).
  127 Latin/space calls were delegated to native U9. Lock/Unlock/Flip all 0,
  register restoration true, clean detach. White initial custom foreground.
- `.local/p5-highres/two-1600-01.json`: U+4E2D and U+6587, exactly two logical
  draws, local x0/16 and common baseline y20. Rasters32×37 and38×38, bearings
  4/34 and2/35, advance40 each; final placements(74,36) and(112,35).
  Custom foreground RGB181/132/239 derives from the predominant bright native
  RGB555 subtitle color; this preserves the general tint, not its baked shading.
- Local screenshots `P5_SINGLE_1600_20261030.png` and
  `P5_TWO_1600_20261030.png` visibly show one/two correct Chinese glyphs with
  readable native Latin, no duplicate byte glyphs or underlying placeholders.
  Two glyphs have a common baseline and do not overlap. Screenshots are private.
- Both captures are one deliberately presented frame, followed by normal game
  continuation. This is not a claim about continuous custom-text rendering.

Font name-table version: `Version 2.004;hotconv 1.0.118;makeotfexe 2.5.65603`.
At the actual selected target sizes (separate direct rasterizations):

| Scalar | Requested em | Raster | Bearing x/y | Advance |
| --- | --- | --- | --- | --- |
| U+4E2D | 20 | 16×19 | 2/17 | 20 |
| U+6587 | 20 | 19×19 | 1/17 | 20 |
| U+4E2D | 40 | 32×37 | 4/34 | 40 |
| U+6587 | 40 | 38×38 | 2/35 | 40 |

All have intermediate grayscale coverage.

### Mixed-line correction and resolution comparison — CONFIRMED

The first mixed capture correctly drew both Unicode glyphs but clipped native
TEST. Its cache was 120×22 because tight-bounds calculation independently read the
opaque glyph's old width at `0x5C5F5B`. The result was rejected, not counted as PASS.
The corrected hardware data watch on the shared font slot covers both layout's
post-load `0x5C7BBA` and tight-bounds post-load `0x5C5F62`, applying the same exact
Unicode advance. Latin and wrapping code remain native. The resulting cache is
142×22, and `.local/p5-highres/mixed-1600-02.json` plus its local screenshot show
the complete `Avatar 中文 TEST`, with no clipping/overlap/underlying placeholders.

The 800×600 runs use an 800×600 XRGB8888 target, pitch 3200, direct 20px rasterization
and 1:1 blending. The second run supplies a visibly complete local mixed screenshot;
the first run's hold ended before visual capture. The native mixed cache hash is
identical at 800 and 1600:
`c237a4bb68c5f6d2a475b62d5b843f80fb6f6efb3ad2675c0ca73500a0b9b8cb`.
Chinese rasters independently increase from 16×19/19×19 to 32×37/38×38.

All accepted captures have Lock/Unlock/Flip HRESULT 0, register restoration true
and empty debug cleanup errors. All test processes were closed. Pristine
text.flx and the starting 800×600 configurations were restored; all five protected
assets again match P0. Final asset-enabled suite: 65/65 PASS, zero skips.
See [P5_HIGHRES_UNICODE_POC.md](../../reports/P5_HIGHRES_UNICODE_POC.md) and its
portable JSON for hashes, precise destinations, test classifications and limits.

## Development font / offline raster — CONFIRMED

Noto Sans CJK TC Regular OTF, upstream commit
`165c01b46ea533872e002e0785ff17e44f6d97d8`, 16,435,884 bytes, SHA-256
`dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4`.
[Pinned font](https://github.com/notofonts/noto-cjk/blob/165c01b46ea533872e002e0785ff17e44f6d97d8/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf),
[SIL OFL 1.1](https://github.com/notofonts/noto-cjk/blob/165c01b46ea533872e002e0785ff17e44f6d97d8/LICENSE).
Font and license remain private; no system-wide installation.

Private-process GDI registration, exact GetTextFaceW match and SHA-256 of the
selected GetFontData bytes all passed. GetGlyphIndicesW maps U+4E2D →9544,
U+6587 →20036. GetGlyphOutlineW GGO_GRAY8_BITMAP produces coverage 0–64,
expanded to alpha 0–255, without ClearType or post-raster enlargement.

| Scalar | Requested em | Raster | Bearing x/y | Advance |
| --- | --- | --- | --- | --- |
| U+4E2D | 16 | 12×15 | 2/13 | 16 |
| U+6587 | 16 | 15×15 | 1/14 | 16 |
| U+4E2D | 32 | 26×30 | 3/27 | 32 |
| U+6587 | 32 | 30×30 | 1/27 | 32 |

All four rasters have intermediate grayscale coverage. This is an **offline
raster test**, not evidence that Chinese is visible in the game.
