# English text-path analysis — P4-C2

Updated 2026-10-30. The initial 2026-10-29 checkpoint below is retained with its
historical limits. P4-C2 now establishes the selected English subtitle's
conversion/width/glyph path; see the continuation section and
[current report](../../reports/P4_RENDER_PATH.md). Native Japanese/CJK behavior
remains untested. No executable, font or renderer patch was made.

## Baseline and tools

CONFIRMED: the English u9.exe matches P0 SHA-256
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`;
size 4,593,152 bytes. PE32, machine `0x14C`, image base `0x400000`, entry RVA
`0x314920`. Sections: `.text`, `.rdata`, `.data`, `_ADATA`, `.rsrc`.
The PE DLL-characteristics field is zero; runtime image base was checked before
using baseline-specific addresses.

Metadata comes from the new read-only `u9cht.pe.PEImage` and synthetic tests.
Reproduce with `python scripts/inspect_pe.py <local-executable> --output <new-json>`.
It emits section/import/resource metadata, not section payloads.

Disassembly used an already-installed Capstone distribution reporting 5.0.9;
the imported module reports 5.0.7. Both values are retained rather than conflated.
Capstone has a BSD-style license; it is an optional local research dependency,
not vendored and not required by the normal text tools or test suite. No package
was installed during P4. Full disassembly and extracted strings are not published.

## CONFIRMED — imports and resources

The image has 256 ordinary import entries. Selected imports:

| Present | Absent from ordinary import table |
| --- | --- |
| MultiByteToWideChar, WideCharToMultiByte | TextOutW, ExtTextOutA/W, DrawTextA/W |
| TextOutA, GetTextExtentPoint32A, CreateFontA | GetTextExtentPoint32W, CreateFontW, GetGlyphOutlineA/W |
| GetACP, GetOEMCP, GetCPInfo | No conclusion about dynamically resolved APIs |
| GetLocaleInfoA/W, EnumSystemLocalesA, IsValidLocale | No conclusion about a locale branch's use by subtitles |
| DirectDrawCreate, DirectDrawEnumerateA/ExA | Direct3D COM usage cannot be ruled out by import names |

Three PE resource leaves have types 3 (icon), 14 (group icon), and 24 (manifest).
No standard RT_FONT or RT_FONTDIR leaf was found. This does not rule out custom
glyph data elsewhere in the image or in game resources.

## Selected addresses and evidence

All VAs below refer only to the frozen image base `0x400000`; RVA = VA minus
image base. These are analysis labels, not recovered original function names.

| VA / RVA | Observation and confidence |
| --- | --- |
| `0x545580` / `0x145580` | STRONG EVIDENCE: archive/text initialization routine; references `text.flx`, later `misctext.flx`, and calls manager candidate `0x5DFEC0` |
| `0x615A10` / `0x215A10` | STRONG EVIDENCE: dual-string construction routine; observed object has ANSI pointer at +0 and wide pointer at +8 |
| `0x615B76` / `0x215B76` | CONFIRMED dynamically: selected text's WideCharToMultiByte call, through IAT VA `0x74010C` |
| `0x615B7C` / `0x215B7C` | CONFIRMED dynamically: API return value captured here |
| `0x615B86` / `0x215B86` | CONFIRMED: error-path GetLastError result captured before the following explicit terminator store |
| `0x615BDC` / `0x215BDC` | CONFIRMED dynamically: converted ANSI copy and retained wide pointer captured in the string object |
| `0x615DB0` / `0x215DB0` | STRONG EVIDENCE: related wide-to-ANSI cache refresh routine; conversion call at `0x615DF1`; not the selected entry's observed call |
| `0x41BC26`, `0x41BC44`, `0x41BC58` | CONFIRMED: verified target ANSI prefix consumed by string scans and REP copy; not established as layout/glyph consumers |

Other static GDI call candidates include TextOutA at `0x5D6333`, `0x5DD192`,
and `0x726810`, and CreateFontA at `0x43FE70`, `0x5C340A`, and `0x5D8042`.
Their connection to the opening subtitle is UNKNOWN. Import presence does not
justify treating the subtitle renderer as Windows text drawing.

## Confirmed conversion component

Static argument setup at `0x615B76` passes CodePage 0 (`CP_ACP`), flags 0,
wide length -1, and a byte capacity derived from wide length plus one. Dynamic
observations for the 4164 diagnostic were:

- Source argument and retained wide object both begin `2d 4e 76 00 61 00`.
- Output capacity is 130 bytes; API returns 0; GetLastError is 122
  (`ERROR_INSUFFICIENT_BUFFER`).
- Output and cached ANSI object begin `a4 a4 76 61 74 61 72 2c`.
- The retained wide object still begins U+4E2D after the call.

CONFIRMED: a failing wide-to-multibyte conversion component exists on the selected
path. STRONG EVIDENCE: its one-byte-per-wide-unit capacity assumption is unsuitable
for an expanding multibyte representation. The host GetACP value is 950 and the
observed `a4 a4` is consistent with Big5 for 中. At this initial checkpoint the
target's GetACP return was not captured; host ACP was not presented as a direct
target observation. C2 subsequently captured the target return directly.

The static continuation stores a terminator using the wide-length-derived index.
The complete converted tail was not captured, so truncation of a particular final
character is not asserted as a directly measured result.

Reference API semantics: [WideCharToMultiByte](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte),
[code-page identifiers](https://learn.microsoft.com/en-us/windows/win32/intl/code-page-identifiers).

## Searches that do not establish a rendering architecture

- CONFIRMED: selected resource-name and font-face strings exist, including
  text.flx, misctext.flx, bitmap16.flx, bitmapC.flx, bitmapsh.flx, Arial and Courier.
  Their presence does not identify the subtitle's font/glyph source.
- CONFIRMED: a numeric 932 search found stack/structure displacements and a
  codepage-table comparison. These are not proof of an active CP932 subtitle path.
- UNKNOWN: a meaningful SHIFTJIS_CHARSET branch for this subtitle. Generic
  `0x80` constants are not sufficient evidence.
- UNKNOWN: width tables, final character-to-glyph indexing, bitmap identity,
  fallback symbol semantics, or a usable native CJK path.

## Historical dynamic-trace limitations (2026-10-29)

Two hardware-only traces captured the conversion. In trace 1, only the first
three data events retained the target prefix; later events at the recycled heap
address are explicitly excluded from text-path conclusions. Trace 2 captured
three string scan/copy events and timed out. Neither established a provenance-safe
path into layout or final glyph lookup.

A grouped-REP destination recovery revision is unit tested, but was not runtime
validated before the user stopped Computer Use. Do not describe its anticipated
copy-following behavior as an observed result.

These limitations were resolved for the selected text in C2, below. Raw traces
and selected local source blobs remain ignored.

## CONFIRMED — C2 continuation (2026-10-30)

Windowed prerequisite was independently verified on actual 3D gameplay before
tracing. The private existing dxcfg GUI saved `display=800x600@120` and
`presentation=windowed`; private Options.ini uses 800x600 and Game Rasterizer=2.
An unsupported 60 Hz attempt had fallen back to desktop and was rejected before
tracing. The working window had a caption and logical client 533x400 at DPI 144,
on a 1920x1200 desktop. The trace launcher now requires the verification receipt
and unchanged private configuration hashes. Original installation files were not
written. Local screenshots/configuration receipts remain ignored.

Three subsequent windowed traces (03/04/05) captured target GetACP return
VA/RVA `0x71D0DB` / `0x31D0DB`: EAX=950. This is independent target evidence;
host ACP=950 remains separately recorded. CP_ACP conversion still returns zero
and error 122 with capacity 130. Static setup allocates/passes wcslen+1 bytes,
while this CP950 text needs 131 bytes including NUL. The complete output tail
was not measured, and no tail-character claim is inferred from the prefix.

Grouped-REP copy recovery now has runtime validation. Each run verifies source,
initial destination bytes and completed destination prefix before following it.
For trace 05: cache pointer 0x036B4F40 is copied at 0x41BC58 to 0x03805A70.
Every subsequent width/glyph observation rechecks the live prefix and selected
source offset. Each run stops on the first invalidating write; that write and
recycled-address activity are excluded from text attribution.

| VA / RVA | Proven selected-string consumer |
| --- | --- |
| `0x5C7870` / `0x1C7870` | Layout routine, byte reads at 0x5C78C6 and 0x5C7B89; text-pointer increment at 0x5C7C60 |
| `0x5C7BB3` / `0x1C7BB3` | Width table: both selected bytes are unsigned 0xA4, each width 11, spacing 0 |
| `0x5C5A80` / `0x1C5A80` | Custom byte-index bitmap lookup; proven caller return 0x5C5D09 and selected pointer from caller stack |
| `0x5C5ABB` / `0x1C5ABB` | Dispatches identical glyph at x=0 and x=11 (y=20) to 0x5E20E0; renderer mode field 2 |

For printable bytes, lookup is `font + u32(font + 0x10 + (byte - 0x20)*8)`.
Each 0xA4 therefore uses table index 132, slot offset 0x430 and glyph offset
0xA458. There is no DBCS pairing on this observed branch. Rendering advances the
text pointer by one byte at 0x5C5D57. This attributes the selected subtitle to a
custom bitmap path, without claiming GDI APIs are unused elsewhere or tracing
every final surface/backend call.

The bounded 76,832-byte runtime font span hashes to
`b3f3135ee84447b879d8558cea4589695c8f15be7694585906b2bd213d1af2f8`,
equal to entry 611 in both bitmap16.flx and bitmapC.flx. Hashing did not save
the font payload. The identical copies prevent deciding which disk archive was
opened from content alone; see the report for archive hashes and offsets.

The two-symbol mechanism is CONFIRMED: preserved U+4E2D -> CP950 prefix A4 A4 ->
two byte-indexed lookups -> identical bitmaps at adjacent positions. Whether the
bitmap was intended as a missing-glyph fallback remains UNKNOWN. A correct
logical U+4E2D glyph ID was not requested by this path.

Current C2 classification: **E — MULTIPLE FAILURES**, comprising confirmed
conversion-capacity and SBCS/byte-iteration failures. This supersedes the initial
checkpoint's old E=UNKNOWN label under the user's revised A–F labels. It does not
authorize any patch. Native CJK/Japanese differences remain NOT EXECUTED; P5
remains unauthorized. After all runs the private resource was restored to
pristine and original/private protected baseline files were verified unchanged.
