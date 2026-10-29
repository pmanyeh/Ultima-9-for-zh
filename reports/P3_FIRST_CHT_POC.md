# Phase

P3 — First Traditional Chinese Injection (diagnostic only), 2026-10-29,
Asia/Taipei.

# Scope

Explicitly authorized P3-A, P3-B and conditional P3-C, using entry 4164 only in
the ignored independent runtime copy. P4+ was not authorized. Read AGENTS.md,
the Master Plan, P0/P1/P2 reports and P2 runtime/structure/validation evidence.

# Status

PASS WITH LIMITATIONS for the diagnostic batch. P3-A passed. P3-B reached the
visible subtitle but did **not** render the intended Han character. Its required
classification is **ENCODING / MAPPING FAILURE**. P3-C was NOT EXECUTED because
the explicit stop condition applies to missing or incorrect glyphs.

This is not a CJK display success. The test does not prove that U+4E2D survives
unchanged inside the engine; its internal decoding/mapping remains UNKNOWN.

# Environment

Windows 11 build 26300; Python 3.12.10; Git 2.55.0.windows.3. Starting code commit
`7979318f4230131c409c4b16e1f7283f4ef20b44`. Pinned TITAN/tgwUltima commit
`2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`. No dependencies were added.
Computer Use observed/closed the private runtime copy. GOG wrapper/configuration
unchanged from P2; active backend not traced. Exact game patch label UNKNOWN.

# Inputs

Observed GOG English installation: game ID `1207659093`, build ID
`59198760502252807`. User has no Japanese installation. Runtime executable
SHA-256: `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.

Pristine text.flx SHA-256:
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.

Target entry: 4164; baseline offset 676832; raw size 260 bytes, including the
two-byte terminator. Its original opening is `Avatar, arise from your slumber!`.
The complete original/replacement entry text is recorded as a small diagnostic
sample in `P3_RUNTIME.json`; no other strings were publicly exported.

# Work Performed

Verified original and private-copy hashes against P0. Copied the pristine text
archive to `.local/p3/pristine/text.flx`. Built each variant independently from
that same template through the existing source-locked importer. Added a separate
diagnostic validator; existing importer and archive guards were not weakened.

The validator requires exactly the selected payload to change, expected text,
predictable offsets/sizes, identical unrelated payloads and preserved unknown
header/padding bytes. Its synthetic tests include both size modes; this does not
constitute P3-C runtime execution.

## P3-A — Same-length ASCII control

Replaced the first six code units `Avatar` with `TEST!!`, preserving the entire
remaining entry text, including punctuation and terminator.

| Check | Result |
| --- | --- |
| Entry ID | 4164 |
| Before prefix | `Avatar, arise from your slumber!` |
| After prefix | `TEST!!, arise from your slumber!` |
| Entry size before / after | 260 / 260 bytes |
| File size before / after | 1,200,660 / 1,200,660 bytes |
| Changed payload IDs | `[4164]` |
| Changed offsets / lengths | 0 / 0 |
| Header / padding changes | none / none |
| Unrelated payloads | all byte-identical |
| Runtime | PASS: `TEST!!` visibly rendered at the opening subtitle start |
| Crash | none observed |

Rebuilt SHA-256:
`530007ebf1634488ef2da78d0e921cb5e81e8f7024d2204b035b00c59601d1d5`.

Exactly six differing bytes. Half-open decimal ranges:
`[676832,676833)`, `[676834,676835)`, `[676836,676837)`,
`[676838,676839)`, `[676840,676841)`, `[676842,676843)`.
Local screenshot: `.local/evidence/P3_A_20261029.png`.

## P3-B — Same-length CJK BMP control

Rebuilt again from the pristine template, never from A. Changed only the first
code unit from `A` (U+0041, UTF-16LE `41 00`) to `中` (U+4E2D, `2d 4e`).
The expected opening is `中vatar, arise from your slumber!`.

| Check | Result |
| --- | --- |
| Entry ID | 4164 |
| Tested code point / exact bytes | U+4E2D / `2d 4e` |
| Entry size before / after | 260 / 260 bytes |
| File size before / after | 1,200,660 / 1,200,660 bytes |
| Changed payload IDs | `[4164]` |
| Changed offsets / lengths | 0 / 0 |
| Header / padding changes | none / none |
| Unrelated payloads | all byte-identical |
| Visible result | two repeated crossed/box-like symbols before `vatar`, not `中`; remaining subtitle renders |
| Runtime classification | **ENCODING / MAPPING FAILURE** |
| Crash | none observed |

Rebuilt SHA-256:
`68548b8a78092c85a70267303c6077553b7ff32257368942c5937bc8765d0e04`.

Exactly two differing bytes, half-open range `[676832,676834)`.
Local screenshot: `.local/evidence/P3_B_20261029.png`.

The visual classification is conservative: whether those symbols are missing-glyph
fallback markers or incorrectly mapped glyphs remains UNKNOWN. No decode/glyph
trace, font change or further code-point experiment was attempted.

## P3-C — Changed-length runtime test

NOT EXECUTED. Although A passed and B did not visibly destabilize the game, the
request explicitly requires stopping when B produces missing or incorrect glyphs.
That narrower stop instruction takes precedence over the broader C eligibility
condition. No C archive was built or launched. Runtime relocation remains untested;
size delta and relocated-entry count for C are not applicable.

## Cleanup

Closed the test game through its quit UI. Restoration was deferred until its
process had exited, then the private runtime text.flx was restored to the pristine
SHA-256 above. Verified original baseline assets and the private executable,
misctext.flx, BOOKS-EN.FLX and TYPENAME.FLX remained unchanged. No original
installation resource, font, executable or other text archive was patched.

# Findings

- CONFIRMED: entry 4164 mutations are genuinely consumed by the tested subtitle
  path. A's visible `TEST!!` provides direct mutation evidence beyond P2's
  unchanged-startup observation.
- CONFIRMED: B's archive contains U+4E2D as `2d 4e` at the expected offset and no
  unrelated payload/layout changes; its visible result is incorrect.
- STRONG EVIDENCE: the B failure lies beyond archive placement/unchanged-size
  preservation, in the downstream decode, mapping or glyph path. The archive
  should not be called corrupt solely because the Han glyph failed.
- UNKNOWN: internal code point preservation, codepage conversion, glyph index,
  fallback semantics, exact font resource and native CJK support.
- Assumption disproven: UTF-16LE-like archive storage plus ASCII mutation success
  does not imply a BMP Han code point will render directly in this installation.

# Evidence

`P3_RUNTIME.json` records both source/rebuilt hashes, full single-entry text,
exact byte-difference ranges, sizes, offset counts, local screenshot paths and
screenshot SHA-256 values. Screenshots, templates, JSON exports and modified FLX
remain under ignored `.local/` paths. No screenshots/game archives are committed.

# Tests

Before P3: `python -m unittest discover -s tests -v` with U9_GAME_DIR configured:
**23 run, 23 passed, 0 skipped, exit 0**.

Focused new helper tests:
`python -m unittest discover -s tests -p test_diagnostic.py -v`:
**6 run, 6 passed, exit 0**. Tests cover ASCII/BMP same-length mutation, predictable
synthetic relocation, unrelated payload rejection, unknown-header rejection,
wrong replacement and length-mode rejection.

After P3: `python -m unittest discover -s tests -v` with the same original assets:
**29 run, 29 passed, 0 skipped, exit 0**. All original 23 tests remain green.

Both variant imports exited 0:

```powershell
python -m u9cht text import .local/p3/pristine/text.flx --input .local/p3/A.json --output .local/p3/A.flx
python -m u9cht text import .local/p3/pristine/text.flx --input .local/p3/B.json --output .local/p3/B.flx
```

Inputs were generated from independent pristine exports, changing only row 4164's
text. The pure validator `u9cht.diagnostic.analyze_mutation` independently checked
each variant before deployment. Its intentional-mutation result is separate from
the unchanged-round-trip comparator; semantic equality is not expected here.

# Results

P3-A PASS; P3-B **ENCODING / MAPPING FAILURE**; P3-C NOT EXECUTED. Diagnostic
objective narrowed the uncertainty but did not establish correct CJK rendering or
the internal decoded value. Both observed runs were stable through the subtitle.
All test artifacts were confined to the private runtime copy and then restored.

# Files Changed

`u9cht/diagnostic.py`, `tests/test_diagnostic.py`, `reports/P3_RUNTIME.json`,
this report and README. Original parser/importer, instructions and prior phase
reports are unchanged. Local-only artifacts: `.local/p3/`, two evidence PNGs,
and the temporarily modified/restored private runtime resource.

# Risks

One BMP character and one startup entry cannot establish behavior across fonts,
dialogue types, locales or other resource families. Incorrect symbols alone do
not identify the root cause or prove that only a missing font is involved.
Changed-length runtime behavior remains UNKNOWN.

# Blockers

Correct Han display is blocked by unresolved downstream decode/mapping/glyph
behavior. Japanese oracle is unavailable. Explicit authorization is required for
P4 research; executable/font patching and renderer work remain unauthorized.

# Deviations From Master Plan

Used the user's prescribed `中vatar` one-unit diagnostic rather than a translated
word. P3-C was skipped under the user-specified incorrect-glyph stop condition.
No attempt was made to solve the font or rendering issue inside P3.

# Recommendation

Recommend a separately authorized, read-only P4 research batch to distinguish
decode/mapping behavior from missing-glyph fallback and locate the native text/font
path. The planned Japanese differential comparison cannot run until a lawful local
oracle is available; its absence must be recorded rather than worked around with
unauthorized assets. Do not begin P4 or apply any font/executable/renderer changes
under this P3 authorization.
