# P5 Unicode renderer architecture options

Decision date: 2026-10-30 (Asia/Taipei). Scope: entry 4164 only, P5-A–F.
The current task overrides the Master Plan's larger glyph-subset example.
P6, translation expansion and a general overlay are excluded.

## Transport decision

**PREFERRED: Strategy B — retain UTF-16 identity.**
**FALLBACK: Strategy A — validated CP950 pairs, decoded to Unicode.**
Strategy B now has a bounded, experimentally verified bridge and presented-frame
PoC. This is not a persistent playable renderer. See the
[surface notebook](../research/U9_TEXT_SURFACE_PIPELINE.md) for measured boundaries,
the initially rejected mixed-line capture, its sizing correction and rollback.

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

Implemented B bridge: capture and compare the complete selected UTF-16 string
before conversion; retain wide object +8 and associate immutable scalar metadata
with its byte cache +0. One opaque 7F slot represents one Unicode scalar; it is
never interpreted as a legacy encoding. Only a fully verified source→destination
copy inherits identity. Free notifications revoke source-buffer associations.
Native Latin calls are unchanged. Selected CJK width and draw operations use
Unicode metrics and suppress the native placeholder bitmap.

Both layout and tight-bound calculations need the custom advance. Their common
font slot is watched; the verified readers `0x5C7BBA` and `0x5C5F62` receive the
same metric header. Omitting the second reader clipped TEST in the first mixed
capture. Correcting it expanded that cache from 120 to 142 logical pixels and
produced the complete mixed line. This is selected-run sizing, not new wrapping.
The task's explicit small-hook authorization and stop conditions apply.

## Scalable raster decision

| Technology | Benefits | Cost / limits | License / scope |
| --- | --- | --- | --- |
| Windows GDI Unicode `GetGlyphOutlineW` | OS-provided; metrics plus DWORD-aligned grayscale raster; no framework | BMP-only direct-character PoC; explicit face/missing-glyph validation; no full shaping claim | Windows system API; no redistributed library |
| DirectWrite | Unicode glyph indices, metrics, alpha textures; suitable longer-term scalar routing | COM/font-face/glyph-run bridge more involved; choose grayscale, not unexamined RGB subpixel blending | Windows system API; no redistributed library |
| FreeType | Portable scalar cmap lookup, metrics, grayscale bitmaps | Additional native binary/build dependency on this Windows-only PoC | FTL or GPLv2; choose FTL if adopted and record version |
| Direct2D/SDL | Can draw complete text/surfaces | Larger graphics integration than the bounded raster problem needs | Not selected |

**Selected for the bounded BMP PoC: Windows GDI Unicode grayscale rasterization.**
DirectWrite remains preferable for a broader Unicode renderer. For this bounded
BMP experiment, GDI provides direct grayscale coverage and exact advances for the
measured CPU-lockable final target, without another graphics device or a COM font
bridge. Exact selected font bytes and glyph availability are checked. Unsupported
scalars are rejected explicitly; no silent legacy/native fallback is allowed.
The transport model supports scalar identity independently of this BMP rasterizer.

Development font choice: Noto Sans CJK TC Regular, SIL Open Font License 1.1.
Use an explicit local font file (`--font`) and private process registration,
verify selected face and glyph availability; never silently accept Windows font
substitution. Record the file version/hash when acquired/used. No font binary is
included in the repository. Acquired/used privately: Regular OTF version 2.004,
upstream commit `165c01b46ea533872e002e0785ff17e44f6d97d8`, SHA-256
`dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4`.
GetFontData SHA-256 equals the explicit file; U+4E2D/U+6587 map to 9544/20036.

## Surface / success gate

**CONFIRMED R3:** at 1600×1200 the native opening subtitle raster is 595×37,
RGB555, pitch 1190; the engine scales its UI geometry by 2.5 into a 1600×1200
XRGB8888 backbuffer, pitch 6400. Chinese bypasses that low-resolution raster.
After verified EndScene and before native Flip at `0x597B1A`, the existing
backbuffer is locked, bounded grayscale coverage is blended into final RGB
pixels, and it is unlocked before the original Flip executes.

Chinese em is 16 logical units: directly rasterized at 40 output pixels for 1600×1200
and 20 for 800×600, with no enlargement of the Chinese raster. Native Latin keeps
the game's existing bitmap/texture path. Surface alpha is absent; coverage is
blended against actual locked background RGB. Cache/output clipping is explicit.
Window dimensions and screenshots alone are not used as resolution evidence.

No executable instruction bytes are replaced. A 97-byte self-restoring Lock/Unlock
stub in a private allocation and selected ABI context redirections implement the
experiment. Remove debug points, finish the call, exit the private process and
restore the diagnostic text.flx to roll back. The one-frame capture/hold is
deliberate; continuous rendering, generalized lifetime handling, other resource
families, fullscreen and wrapping remain unverified. Do not begin P6 automatically.

## Primary references

- [GDI Unicode raster and metrics](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getglyphoutlinew): gray8 output uses coverage 0–64 and DWORD-aligned rows.
- [DirectWrite alpha texture API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwriteglyphrunanalysis-createalphatexture).
- [FreeType licensing](https://freetype.org/license).
- [Noto CJK deployment formats](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md).
- [Noto font licensing](https://notofonts.github.io/noto-docs/website/use/).
