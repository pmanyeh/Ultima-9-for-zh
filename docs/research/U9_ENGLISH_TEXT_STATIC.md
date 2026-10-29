# English text-path analysis — partial P4 snapshot

2026-10-29. This document records completed observations, not a finished P4
investigation. Layout/glyph provenance remains unresolved. No executable,
font or renderer patch was made. No Japanese executable was acquired.

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
observed `a4 a4` is consistent with Big5 for 中. The target's GetACP return was
not captured; host ACP is not presented as a direct target observation.

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

## Dynamic-trace limitations and resumption

Two hardware-only traces captured the conversion. In trace 1, only the first
three data events retained the target prefix; later events at the recycled heap
address are explicitly excluded from text-path conclusions. Trace 2 captured
three string scan/copy events and timed out. Neither established a provenance-safe
path into layout or final glyph lookup.

A grouped-REP destination recovery revision is unit tested, but was not runtime
validated before the user stopped Computer Use. Do not describe its anticipated
copy-following behavior as an observed result.

Before any next launch, configure and independently verify windowed operation,
as requested by the user. The current trace launcher does not itself configure
windowed mode. Continue from the pristine resource baseline only; P5 remains
unauthorized. Raw traces and selected local source blobs remain ignored.
