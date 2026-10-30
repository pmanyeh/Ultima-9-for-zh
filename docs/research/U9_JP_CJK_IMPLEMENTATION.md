# Japanese CJK implementation — P5-0

2026-10-30, Asia/Taipei. **JP CJK PATH CONFIRMED (static)**, reuse class **J2**.
This notebook documents the reconstructed pinned delta target, not a claim about
all official Japanese builds or which changes a particular patch author wrote.
Reports: [reconstruction](../../reports/P5_JP_PATCH_RECONSTRUCTION.md),
[differential](../../reports/P5_JP_BINARY_DIFF.md),
[machine evidence](../../reports/P5_JP_BINARY_DIFF.json).

## Confirmed processing chain

```text
retained UTF-16 object +8
  → WideCharToMultiByte(CP_OEMCP), query then allocate query+1 then convert
  → byte cache +0
  → hardcoded Shift-JIS lead detection
  → packed (lead << 8) | trail, one width, source +=2
  → glyph cache: single-byte or compact Shift-JIS slot
  → on cache miss: Windows GDI ANSI metrics/TextOutA into 64×64 DIB
  → small packed-coverage bitmap and signed-byte metrics
  → engine renderer virtual method at vtable +0x3C
```

The constructor is `0x617BE0`, query `0x617D27`, conversion `0x617D4D`.
Both calls use CodePage=1, flags=0, source length=-1. **CONFIRMED:** this is
CP_OEMCP, not a literal CP932 constant. **STRONG EVIDENCE:** the intended Japanese
locale environment supplies a matching Japanese code page; effective OEMCP and
Locale Emulator behavior were not runtime-tested. The supplied launcher is
`LEProc.exe u9.jp.exe`. GetACP/GetCPInfo import presence is not proof of selected
text behavior. No IsDBCSLeadByte/Ex import is used; a custom predicate supplies it.

## Character iteration and native fallback

**CONFIRMED static:** layout `0x5C8C10` and draw loop `0x5C6EF0` each pair bytes
after calling lead predicate `0x5CAEA0`. It recognizes 81–9F and E0–FC; packed
values >FF also return true. The layout requests the cache advance at `0x5C8E72`
and increments the source by two on the paired branch. The draw loop assembles
the pair and dispatches once at `0x5C7234`, using the returned advance.

Font IDs 17/18 still use bitmap helper `0x5C6B40` → `0x5E42D0`, corresponding to
English `0x5C5A80` → `0x5E20E0`. Other font modes use the alternative glyph path
for single-byte Latin as well as DBCS. Therefore blindly installing this executable
does **not** demonstrate preservation of the original Latin appearance.
The actual font mode for the Japanese opening subtitle was not observed.

## Glyph index and cache

**CONFIRMED static:** draw helper `0x5C6B90` requests the packed character from
`0x5CAB40`; width helper `0x5CAD80` returns its cached signed-byte advance at +4.
For characters >FF, mapper `0x5CAD00` validates:

- lead: 81–9F or E0–FC;
- trail: 40–7E or 80–FC (7F excluded).

Its flat row/column arithmetic is:

```text
row = lead - 0x81                    # first lead range
row = lead - 0xC1                    # second lead range
column = trail - 0x40                # trail <= 0x7E
column = trail - 0x41                # trail >= 0x80
flat = row * 188 + column
```

On nonzero return the caller adds `0x100`; single-byte characters use their byte
value. Zero is shared by invalid mappings and the first flattened pair; its
special/fallback semantics are not established. The cache checks index against
its stored count, initialized to `0x2D0F` (11,535), and uses a 12-byte slot stride.
Boundary/failure behavior must be reviewed before reuse; no safe whole-repertoire
claim is made. Raw slots or glyph data are not included here.

Cache misses call `0x5CA710`, which reconstructs the original one/two bytes,
calls GetTextExtentPoint32A with count 1/2 at `0x5CA754`, GetCharABCWidthsA at
`0x5CA767`, and TextOutA at `0x5CA7D7` or `0x5CAB1C`. Both bytes belong to one
logical lookup; the cache index is **not a Unicode scalar or font glyph ID**.
A six-byte metrics header plus bitmap pointer describes bearings, dimensions,
advance and packed row stride. GDI/font failure and malformed trailing-byte
handling have not been exhaustively audited.

## Font mechanism and resources

**CONFIRMED static:** initialization `0x5CA060`, reached by the font setup call
at `0x5C6AAD`, reads `[Font]` from `fcache.ini`. Strings/defaults include:

| Key | Default / behavior |
| --- | --- |
| `Family` | `ＭＳ Ｐゴシック` (MS P Gothic), CP932 face-name bytes |
| `Weight` | 400 |
| `CharSet` | 128, SHIFTJIS_CHARSET |
| `Use16BitFont` | 0; selects one of two raster/metric branches |

It attempts to load `fcache.dbc`, checking signature `OYOYO`, face and selected
parameters before reuse; otherwise it allocates a cache. File absence therefore
has a construction path, not just an unconditional dependency on a shipped atlas.
The initializer calls CreateCompatibleDC, creates a **64×64, 8-bpp, BI_RGB DIB**
at `0x5CA39F`, selects a CreateFontA font at `0x5CA3E4` / `0x5CA480`, and obtains
text metrics. Font heights passed are 28 / 14 logical pixels respectively.

**CONFIRMED:** the selected implementation can derive glyph pixels from a Windows
font; an extra Japanese bitmap FLX is not its sole font mechanism.
**UNKNOWN:** which font/cache files ship in the Japanese language pack, additional
FLX differences, actual font substitution, runtime selected settings and the
licensed installation state of MS P Gothic. No font or language pack was acquired.
No proprietary font should be redistributed; a future PoC should explicitly load
and verify a licensed development font rather than rely on this face default.

## Resolution and coverage limits

**CONFIRMED static:** the large-font branch halves metrics, samples 2×2 source
pixels into coverage counts and clamps measured raster bounds to 32. The other
branch clamps to 64 and maps nonzero pixels to full coverage. Both pack two
coverage nibbles per byte, use byte-sized metrics and render via the engine's
pixel/coverage virtual call. This is scalable-font-derived **small raster caching**;
the 28-pixel source branch is not automatically native-resolution presentation.

**STRONG EVIDENCE:** unchanged use of these small fixed-size caches cannot deliver
the requested generally scalable high-resolution text. **UNKNOWN:** final surface
format/resolution, mode-dependent scaling and observed glyph quality. No Japanese
executable was launched, so no 1600×1200 compositing result is claimed.
The previous interrupted English probe's small intermediate surface is consistent
with a need for further investigation, but is not evidence of the Japanese target.

## Traditional Chinese reuse assessment

**J2 — structurally reusable**, not a direct CP932→CP950 substitution.

Python's standard codec diagnostic gives 中: CP932 `92 86`, CP950 `A4 A4`;
文: CP932 `95 B6`, CP950 `A4 E5`. The Japanese lead predicate rejects A4.
Changing conversion code page alone would therefore reproduce two-byte/split-glyph
problems for these characters. Big5 also has different trail ranges, so the
188-column Shift-JIS index, slot count, charset/font defaults, break tables and
cache identity must change together. CP950 would still limit Unicode coverage.

Reusable design evidence: byte-capacity query, logical-character stepping shared
by layout/draw, one measured advance, explicit glyph-cache identity, and a separate
native-bitmap fallback. No copied executable bytes, new renderer, wrapping rules
or codepage adaptation were implemented in P5-0.

| Future option | Assessment |
| --- | --- |
| 1. Japanese DBCS path + CP950 bitmap cache | Multiple coupled changes; CP950 repertoire limit and small raster output. Not preferred. |
| 2. Japanese-derived character/layout logic + new high-resolution raster | Structurally feasible, but its SJIS tables and byte text ABI need replacement; useful reference, not a ready adapter. |
| 3. Retain UTF-16 and selectively render Unicode | **Recommended for the real P5**, preserving original Latin routing and avoiding legacy pair/index tables; use Japanese findings to define bridge/metric responsibilities. |

The earlier custom Unicode proposal remains justified as a future experiment,
not as an implemented or final architecture. Its first gate is still recovery of
Unicode identity with correct object lifetime and a suitable native-resolution
render target. Revisit renderer choice only after that evidence; do not infer that
a full overlay or graphics replacement is necessary. Stop after P5-0; P6 remains
unauthorized.
