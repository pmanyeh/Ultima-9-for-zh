# P5 Unicode renderer architecture options

Decision date: 2026-10-30 (Asia/Taipei). Scope: entry 4164 only, P5-A–D.
The current task overrides the Master Plan's larger glyph-subset example.
P6, translation expansion and a general overlay are excluded.

## Transport decision

**PREFERRED: Strategy B — retain UTF-16 identity.**
**FALLBACK: Strategy A — validated CP950 pairs, decoded to Unicode.**
These are architecture selections, not claims that an engine bridge exists.

| Criterion | A: CP950 transport | B: retained UTF-16 |
| --- | --- | --- |
| Hook surface | Conversion allocation/capacity, byte layout, byte draw loop | Wide-object bridge, selective layout/draw routing |
| Original Latin | Can retain native calls, but pair handling touches both loops | Delegate unchanged Latin runs to native calls |
| Coverage | CP950 repertoire; reject unrepresentable scalars | Unicode scalars; renderer/font coverage remains separate |
| Scalable raster | Decode complete pairs before glyph lookup | Pass actual Unicode identity directly |
| Layout | Pair-aware widths and source advancement required | Scalar-aware metrics; P5 single line only |
| Reversibility | Baseline-locked runtime changes, remove on exit | Same; sidecar lifetime must follow source object |
| Version robustness | Three existing defective boundaries need validation | Fewer encoding assumptions; object/copy ABI still version-specific |
| Binary intervention | Capacity fix unavoidable before trusting conversion | Bypass CJK conversion; leave unrelated capacity defect untouched |

B is preferred because A's apparently smaller byte interface still needs three
coordinated corrections and permanently limits coverage. B must not infer a
Unicode value from a single ANSI byte. A is usable only after a sizing-query
conversion, lossless round-trip check and pair-aware width/draw implementation.

## Interception candidates and gates

| Boundary | Known context | Missing context / decision |
| --- | --- | --- |
| Dual string at `0x615BDC`, wide pointer +8 | Actual UTF-16 and ANSI-cache association (P4 CONFIRMED) | Source lifetime/copy mapping and line destination need bridging |
| Layout `0x5C7870`, width `0x5C7BB3` | Selected copied byte source, native widths | No intrinsic Unicode; needs verified wide sidecar |
| Glyph `0x5C5A80` | Native font, byte, x/y, caller source pointer | No intrinsic Unicode; never use byte as Chinese identity |
| Dispatch `0x5C5ABB` → `0x5E20E0` | Bitmap, x/y, renderer object | Surface resolution/format and wide mapping must be established first |
| Final backend surface | Potential presentation coordinates | Text identity lost; do not hook it arbitrarily |

Candidate B bridge: capture wide identity before conversion; for the selected
object alone carry scalar/run metadata through verified copies, then route Latin
to the unchanged native glyph function and CJK to a measured raster/compositor.
Byte placeholders, if used for native loop compatibility, are opaque sidecar
indices, never a replacement encoding. Lifetime invalidation must fail closed.
No bridge or executable patch is approved by this document alone; the task's
small-hook authorization and stop conditions apply.

## Scalable raster decision

| Technology | Benefits | Cost / limits | License / scope |
| --- | --- | --- | --- |
| Windows GDI Unicode `GetGlyphOutlineW` | OS-provided; metrics plus DWORD-aligned grayscale raster; no framework | BMP-only direct-character PoC; explicit face/missing-glyph validation; no full shaping claim | Windows system API; no redistributed library |
| DirectWrite | Unicode glyph indices, metrics, alpha textures; suitable longer-term scalar routing | COM/font-face/glyph-run bridge more involved; choose grayscale, not unexamined RGB subpixel blending | Windows system API; no redistributed library |
| FreeType | Portable scalar cmap lookup, metrics, grayscale bitmaps | Additional native binary/build dependency on this Windows-only PoC | FTL or GPLv2; choose FTL if adopted and record version |
| Direct2D/SDL | Can draw complete text/surfaces | Larger graphics integration than the bounded raster problem needs | Not selected |

**Selected for the bounded BMP PoC: Windows GDI Unicode grayscale rasterization.**
DirectWrite is the preferred raster fallback for supplementary scalar support or
a GDI font-format limitation. This choice does not narrow Strategy B's transport
to BMP; unsupported scalars must be rejected explicitly in this PoC.
No rasterizer should be connected until surface suitability is measured.

Development font choice: Noto Sans CJK TC Regular, SIL Open Font License 1.1.
Use an explicit local font file (`U9_CHT_FONT`) and private process registration,
verify selected face and glyph availability; never silently accept Windows font
substitution. Record the file version/hash when acquired/used. No font binary is
included in the repository. Font acquisition/use status is in the phase report.

## Surface / success gate

At the chosen dispatch, measure clip rectangle, extent, stride, storage pointer,
pixel packing, and the eventual copy to the game target. Configured resolution
and DPI-scaled window dimensions are not proof of target resolution.
At 1600×1200, a glyph must be rasterized for that actual target scale, rather
than drawn into a smaller text bitmap that is magnified later. A lower-resolution
intermediate must be reported explicitly. Stop if meeting the requested output
requires broad rendering replacement or an unsuitable surface.

## Primary references

- [GDI Unicode raster and metrics](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getglyphoutlinew): gray8 output uses coverage 0–64 and DWORD-aligned rows.
- [DirectWrite alpha texture API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwriteglyphrunanalysis-createalphatexture).
- [FreeType licensing](https://freetype.org/license).
- [Noto CJK deployment formats](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md).
- [Noto font licensing](https://notofonts.github.io/noto-docs/website/use/).
