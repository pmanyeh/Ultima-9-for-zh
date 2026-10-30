# Phase

P5-0D–J — English/Japanese executable differential, 2026-10-30 (Asia/Taipei).

# Scope

Static comparison of the exact accepted English basis and hash-verified Japanese
target. No same-address assumption, renderer implementation, runtime comparison
or Japanese game/font asset acquisition. See the
[reconstruction report](P5_JP_PATCH_RECONSTRUCTION.md) for authorization/preflight.

# Status

**PASS WITH LIMITATIONS — JP CJK PATH CONFIRMED (static).**
Reuse class **J2 — structurally reusable**, with hardcoded Shift-JIS mapping,
Japanese font defaults and byte-oriented APIs. CP950 readiness is not established.

# Environment

Python 3.12.10, Capstone distribution 5.0.9/module 5.0.7, PE32 metadata inspector;
Windows 11 build 26300. Project commit and dependency pins are in the
reconstruction report. Capstone is optional; ordinary tests use synthetic inputs.

# Inputs

English SHA-256:
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Japanese SHA-256:
`7ba58dfe974adfa78e25d49e58fa066669e40ac9448e325c93f27147856b8282`.
Both files remain private. The Japanese target passes the original delta's hash
check. This is not comparison against a guessed executable version.

# Work Performed

Compared PE metadata, section-relative data, imports, resource leaf hashes,
positional changed ranges/clusters and normalized instruction anchors. Then
reviewed control flow and import-call relationships around the requested P4
functions and their Japanese callers/helpers. Reports contain metadata and small
human-written algorithm summaries, not full disassembly or binary payloads.

# Findings

## PE and section layout — CONFIRMED

Both images are x86 PE32 at base `0x400000`, with five sections. English entry RVA
`0x314920` becomes `0x316950`; image size `0xF38000` becomes `0xF3B000`.
File size falls from 4,593,152 to 4,432,896 bytes. English has 170,496 bytes after
the last section's raw end; Japanese has none. Their purpose is UNKNOWN; our tools
did not strip or normalize them—the official delta determines its target.

| Section | English RVA → Japanese RVA | Raw size English → Japanese | Section-relative changed bytes / clusters |
| --- | --- | --- | --- |
| `.text` | `0x1000` → `0x1000` | 3,402,752 → 3,410,944 | 3,178,469 / 934 |
| `.rdata` | `0x340000` → `0x342000` | 255,488 → 255,488 | 111,765 / 18 |
| `.data` | `0x37F000` → `0x381000` | 756,736 → 759,296 | 670,395 / 38 |
| `_ADATA` / `_adata` | `0xF36000` → `0xF39000` | 3,584 → 3,584 | 519 / 2 |
| `.rsrc` | `0xF37000` → `0xF3A000` | 3,072 → 2,560 | 2,113 / 3 |

Clustering joins positional ranges separated by at most 32 unchanged bytes;
changed-byte counts exclude the intervening equal bytes. Whole-file comparison:
4,209,680 differing/missing byte positions, 185,236 ranges, 1,052 clusters.
These figures include code/data movement, addresses, padding and the unequal tail.
**They are not counts of meaningful changed functions.** At least **four
CJK-relevant functional regions** are identified: construction, layout, draw
routing, and the Japanese font/cache/index helper group. The whole executable's
semantic-change count remains UNKNOWN; it would require broader function matching.

## Imports and resources — CONFIRMED

Ordinary imports: **256 → 268**. Added 15 identities, removed 3; three are COM
functions moving from `dshow.dll` to `ole32.dll`. New identities include
DirectDrawCreateEx, CreateBrushIndirect, GetCharABCWidthsA, GetTextMetricsA,
SetBkColor, SetBrushOrgEx, SetStretchBltMode, SetTextColor, GlobalAlloc/GlobalFree,
lstrcatA and lstrcmpA. Exact lists and IAT locations are in JSON.

Neither ordinary import table contains IsDBCSLeadByte/IsDBCSLeadByteEx. The
Japanese text path uses its own range checks. GetACP/GetCPInfo are present but
their mere presence is not evidence for selected-path pairing. No explicit
numeric 932 argument is used by the identified constructor; it passes **1**.

Resources: **3 → 2** leaves. Icon and group-icon payload hashes are identical;
their RVAs move and metadata codepage changes 1252 → 0. The 440-byte manifest
leaf is absent in Japanese. No RT_FONT/RT_FONTDIR is present. Imports/resources
alone were not used to identify the font mechanism.

## Function mapping

All pairs below are VA / RVA. Interior width/draw locations are identified as
such; they are not independent function entry points.

| English VA / RVA | Japanese VA / RVA | Status / observed difference / role | Confidence |
| --- | --- | --- | --- |
| `0x615A10 / 0x215A10` | `0x617BE0 / 0x217BE0` | Dual-string constructor; retains ANSI +0 / wide +8, adds conversion sizing call | CONFIRMED static |
| `0x615B76 / 0x215B76` | `0x617D27 / 0x217D27`, `0x617D4D / 0x217D4D` | One conversion becomes sizing query plus conversion; CP_ACP 0 → CP_OEMCP 1 | CONFIRMED static |
| `0x5C7870 / 0x1C7870` | `0x5C8C10 / 0x1C8C10` | Layout state machine; pairs DBCS bytes and advances two | CONFIRMED static |
| `0x5C7BB3 / 0x1C7BB3` | `0x5C8E72 / 0x1C8E72` → `0x5CAD80 / 0x1CAD80` | Width site now calls glyph-cache advance helper; no one-to-one table instruction | CONFIRMED static |
| `0x5C5A80 / 0x1C5A80` | `0x5C6B40 / 0x1C6B40` | Retained SBCS bitmap helper; CJK bypasses it through `0x5C6B90 / 0x1C6B90` | CONFIRMED static |
| `0x5C5ABB / 0x1C5ABB` | `0x5C6B7B / 0x1C6B7B` | Retained bitmap-dispatch call; alternate CJK path draws cached coverage through renderer virtual method | CONFIRMED static |
| `0x5E20E0 / 0x1E20E0` | `0x5E42D0 / 0x1E42D0` | Retained bitmap dispatcher, not the new character decoder | CONFIRMED static |
| `0x5C5C00 / 0x1C5C00` | `0x5C6EF0 / 0x1C6EF0` | Draw-loop counterpart; font-mode selection and two-byte assembly precede alternate glyph call | CONFIRMED static |

Mapping evidence combines a unique 12-instruction constructor prefix, two unique
8-instruction layout-interior anchors (`0x5C7A98` → `0x5C8D85` and `0x5C7B5A`
→ `0x5C8E47`), consistent state fields and API/call relationships. The entire
75-byte native glyph span (27 instructions) and 1,312-byte dispatcher span
(582 instructions) have identical normalized instruction sequences, with mapped
call/global addresses. Normalization is candidate evidence, not proof that every
dependent object/state is equivalent. Five anchors are automatically rechecked
against the complete Japanese `.text`; ambiguous matches stop the analyzer.

## Conversion — CONFIRMED static

At `0x617D27`, the constructor queries WideCharToMultiByte with null destination,
zero byte capacity, source length -1, flags 0, code page 1. It allocates query
return +1 bytes, then calls again at `0x617D4D` with that capacity. The explicit
terminator uses the query-derived index. The wide buffer remains at object +8;
ANSI cache remains at +0.

**Yes: the identified Japanese constructor removes the English
one-byte-per-wide-unit sizing assumption.** Error handling is still limited:
the query result is not explicitly rejected on zero; a failed second call fetches
GetLastError and continues. This is not a general conversion-error fix.
Code page 1 is CP_OEMCP, not an explicit 932/950 selection; the effective Japanese
runtime code page was not observed. Microsoft's
[conversion API](https://learn.microsoft.com/en-us/windows/win32/api/stringapiset/nf-stringapiset-widechartomultibyte)
documents the sizing-query contract. No English capacity fix was implemented.

## Layout and glyph routing — CONFIRMED static

`0x5CAEA0` accepts lead ranges 81–9F and E0–FC (also accepts already-packed values
above FF). The layout's `0x5C8DAE` call reaches that helper, combines the following
byte as `(lead << 8) | trail`, requests one advance and commits source +=2 at
`0x5C8EA3`; the single-byte alternative increments by one. Japanese pair-list
helpers `0x5CAEE0` and `0x5CAF20` also influence break state. This is established
existing code, not new P6 implementation; its exact typography semantics are not
fully audited.

The draw loop at `0x5C6EF0` routes font IDs 17/18 to the old bitmap helper.
Other IDs reach lead detection at `0x5C71B6`, assemble the pair at
`0x5C71BF–0x5C71C8`, and call custom draw at `0x5C7234`. Its internal source
increment plus loop increment consume two bytes, while one glyph advance is
returned. Thus the old byte helper itself did **not** become DBCS-aware; a
different path was introduced around it. Runtime selection for entry 4164 is
NOT EXECUTED in Japanese.

## Glyph source / indexing / high resolution

See the [implementation notebook](../docs/research/U9_JP_CJK_IMPLEMENTATION.md)
for the bounded glyph-cache algorithm, GDI call chain and resolution limits.
CONFIRMED: a Windows-font-based cache path exists, not solely an additional FLX
bitmap atlas. STRONG EVIDENCE: native logical-pixel cache design limits this
path's output resolution. Its actual final surface and configured-mode behavior
remain UNKNOWN. A scalable font source does not establish native-resolution text.

# Evidence

[P5_JP_BINARY_DIFF.json](P5_JP_BINARY_DIFF.json) contains exact PE metadata,
resource hashes, clusters, pinned inputs, checked anchors and API call sites.
Reproduce without modifying any game file:

```powershell
python scripts/analyze_p5_jp.py --output .local/p5-jp/diff-recheck.json
```

# Tests

`python -m unittest discover -s tests -v`, local assets configured:
before **39/39 PASS**, after **55/55 PASS**, 0 skips, exit 0.
Metadata analyzer: exit 0, `JP CJK PATH CONFIRMED`; all five unique anchors passed.
No original binaries are unit-test fixtures. No game runtime was exercised.

# Results

The Japanese target supplies the missing architecture: safe byte-capacity sizing
on the selected constructor, DBCS-aware layout/draw routing, and one glyph-cache
lookup per assembled character. **J2**, not J1: lead/trail ranges, compact index,
font charset, byte APIs and break tables are Japanese-specific. Neither actual
Japanese rendering nor adaptation to Traditional Chinese was tested.

# Files Changed

This report, its JSON, metadata/diff tooling and synthetic tests. Full list and
private/public boundaries are in the reconstruction report.

# Risks

Do not interpret new imports, relocated bytes or an unchanged normalized helper
as proof of an entire runtime path. The reconstructed executable contains broader
build differences and is not a minimal patch to apply to the English baseline.
Its default alternative renderer may change Latin appearance; no such regression
was tested because it was not installed or launched.

# Blockers

No static-analysis blocker. A CP950 adaptation needs different pairing/indexing,
font/charset selection, cache capacity, error/bounds behavior and mapping-table
review. High-resolution compositing and original-Latin preservation are unresolved.

# Deviations From Master Plan

Explicitly authorized private reconstruction replaces the previously unavailable
Japanese executable oracle for static analysis only. No Japanese text/font
language-pack assets were acquired. No same-address binary patch was attempted.

# Recommendation

Proceed only after separate authorization for the real P5. Prefer future
**Option 3: retained UTF-16 identity with selective Unicode rendering**, informed
by the verified Japanese routing/metric separation. Avoid importing its CP932
index tables and low-resolution glyph packing unchanged. Keep surface/resolution
verification as a prerequisite. P6 and renderer implementation remain unexecuted.
