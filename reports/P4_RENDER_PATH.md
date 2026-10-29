# Phase

P4 — Text Decode / Mapping / Renderer Path Investigation. Partial progress
snapshot, 2026-10-29, Asia/Taipei. Published at the user's commit/push request.

# Scope

Explicit P4 diagnosis authorization, including public Japanese-patch source audit,
read-only English executable analysis and controlled entry-4164 tracing in the
private runtime copy. The user explicitly waived the requirement for an available
Japanese oracle for this batch. No P5, executable/font/renderer patching, Japanese
patch application, asset acquisition or translation expansion was authorized.

# Status

BLOCKED — incomplete investigation paused after the user stopped Computer Use.
This commit is a progress snapshot, not a claim that P4 or its gate has passed.
Conversion observations are confirmed; layout, glyph provenance and final cause
classification remain incomplete. No new game launch/trace was performed while
preparing this snapshot for commit/push.

# Environment

Same frozen GOG English baseline as P0–P3. Python 3.12.10, Git
2.55.0.windows.3, 64-bit Windows Python observing a WOW64 process. Starting code
commit `1e3cd304322870d67518e5bb04f524c9f553246f`.
Already-installed optional Capstone research dependency: distribution 5.0.9,
module 5.0.7, BSD-style license. No package installation or core runtime dependency
was added. See THIRD_PARTY_NOTICES.md and the English static notebook.

# Inputs

English executable SHA-256:
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Pristine text.flx SHA-256:
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.
Controlled P3-B resource SHA-256 used for tracing:
`68548b8a78092c85a70267303c6077553b7ff32257368942c5937bc8765d0e04`.
Only entry 4164's initial BMP unit was changed; no archive-layout change.

UltimaPatcher source pin: `c5db7b77b93a3b99b27556c3e5d8654d1679ced5`.
TITAN source pin: `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`.
Baseline hashes and prior P0–P3 evidence were read and rechecked.

# Work Performed

## P4-A — public Japanese mechanism

CONFIRMED from source: the Jp installation branch copies the pack's static tree,
applies an Octodiff using installed u9.exe as basis, creates u9.jp.exe and installs
Locale Emulator's launcher. The accompanying script uses `LEProc.exe u9.jp.exe`.
The UI requires Japanese Windows language support. Separate speech installation
copies sound and Movies trees. The exact Japanese asset manifest is UNKNOWN.

`signatureFilePath` is declared but not read in that source block; SkipHashCheck
is explicitly false. Exact compatible basis SHA-256 remains UNKNOWN because no
delta/signature payload was inspected or applied. Details and source links are in
`docs/research/U9_JAPANESE_PATCH_PATH.md`.

## P4-B — English static analysis

CONFIRMED: PE32 image base 0x400000, five sections, 256 ordinary imports, three
resource leaves (icon/group-icon/manifest). Wide/ANSI conversion, ANSI GDI text,
locale/codepage and DirectDraw imports exist; ordinary W text drawing imports and
standard RT_FONT leaves were not found. Dynamic API resolution/custom bitmap
rendering remain possible. Selected function/call RVAs, source hashes and
resource metadata are recorded without section dumps.

## P4-C — controlled dynamic observations

Used CPU hardware execution/data points, bounded ReadProcessMemory and WOW64
context observation. No WriteProcessMemory, inserted software breakpoint,
injected DLL, game code replacement or font change was used. Each diagnostic
resource was rebuilt from the pristine baseline. Both debugger runs logged no
debug-register restoration/detachment cleanup errors.

At VA `0x615B76` (RVA `0x215B76`), the selected wide string is passed to
WideCharToMultiByte. Source argument and object wide prefix contain `2d 4e`.
Observed CodePage is 0 (CP_ACP), output capacity 130, return value 0, subsequent
GetLastError 122. Output/cached ANSI prefix is `a4 a4 76 61 74 61 72 2c`.
The object's wide copy still contains U+4E2D afterward.

Trace 1 captured 48 total data events, but only its first three retained the
verified target prefix. Recycled-allocation observations are not attributed to
the text path. Trace 2 captured three string scan/copy observations and hit its
90-second limit. A grouped-REP copy-following revision was unit tested afterward;
that final revision has not received runtime validation.

## P4-D — Japanese oracle

NOT EXECUTED. No lawful Japanese executable/install is locally available. No
language pack, delta/signature binary payload or Locale Emulator binary was
downloaded, copied into this repository, reconstructed or applied.

# Findings

| Required question | Current evidence |
| --- | --- |
| 1. Expected UTF-16LE bytes in memory? | CONFIRMED in the selected source argument after archive loading; raw ReadFile completion buffer itself was not separately watched |
| 2. U+4E2D survives archive loading? | CONFIRMED in the retained wide string copy at object +8 |
| 3. Wide-to-ANSI conversion? | CONFIRMED: CP_ACP WideCharToMultiByte call, ANSI prefix A4 A4, API failure/error 122 |
| 4. Representation reaching layout? | UNKNOWN; only proven string scan/copy consumers captured |
| 5. Representation reaching glyph/render? | UNKNOWN; no final provenance-safe lookup identified |
| 6. Two-symbol P3 result explained? | HYPOTHESIS: two A4 bytes could be processed separately downstream; that byte-to-glyph consumption is not yet observed |
| 7. Most likely font/glyph source? | UNKNOWN; GDI imports and bitmap resource names provide leads, not attribution |
| 8. Japanese executable-side localization? | STRONG EVIDENCE from the explicit generated u9.jp.exe mechanism; exact purpose UNKNOWN |
| 9. Unknown without Japanese oracle? | Binary/function changes, active CJK/DBCS path, font resources and locale behavior |
| 10. Justified P5 strategy? | UNKNOWN — complete P4 provenance tracing before selecting or implementing a strategy |

Root-cause classification for the complete chain remains **E — UNKNOWN** while
P4 is incomplete. A **CODEPAGE CONVERSION** failure component is directly
confirmed; this does not prove it is the only downstream problem. The host ACP
was 950 and A4 A4 is consistent with Big5, but no target GetACP return was captured.
Do not silently replace a target observation with the host value.

# Evidence

`P4_RENDER_PATH.json` contains sanitized PE/import/resource metadata, selected
static xrefs, small diagnostic byte samples, baseline hashes and bounded trace
summaries. Raw heap/stack traces and selected upstream source files remain in
ignored `.local/p4/` storage. No full disassembly, large string dump, screenshot,
original/modified executable, FLX or patch payload is published.

# Tests

Before P4 changes: `python -m unittest discover -s tests -v` with U9_GAME_DIR
configured: **29 run, 29 passed, exit 0**.

At this snapshot: the same command and original installation:
**38 run, 38 passed, 0 skipped, exit 0**. The nine added tests cover synthetic PE
headers/imports/resources/bounds, official WOW64 structure layout, debug-register
control encoding and conservative grouped-REP pointer recovery. No game launches
are performed by the unit suite.

# Results

Preserved an actionable conversion finding and source audit while explicitly
leaving the full renderer-path investigation unfinished. The final copy-following
revision is an experimental research tool, not a validated finished trace.

At snapshot preparation no U9 process was running. The private runtime resource
was restored to the pristine hash and all five private/original baseline assets
matched P0. Original installation resources were never replaced by these tools.

# Files Changed

`u9cht/pe.py`, `u9cht/wintrace.py`, `scripts/inspect_pe.py`, `scripts/trace_p4.py`,
`tests/test_pe.py`, `tests/test_wintrace.py`, the two P4 research notebooks,
this report, `P4_RENDER_PATH.json`, README and dependency notice.

# Risks

Import names and static candidates do not establish subtitle use. A stale heap
address is not valid string provenance; recycled-buffer events were excluded.
The hardware debugger is baseline-specific and experimental. Grouped-REP recovery
has unit coverage but still needs a controlled runtime check. Do not run the
current trace launcher until windowed operation is independently configured and
verified; the launcher does not configure it itself.

# Blockers

P4 remains paused. Width/layout/glyph consumer provenance, fallback meaning and
font identity are unresolved. The next launch must use windowed mode, as requested
by the user; this setting is not yet implemented/verified. Japanese differential
inputs remain absent. P5 has not been authorized.

# Deviations From Master Plan

The current user authorization explicitly permits P4 without a Japanese oracle.
This replaces that prerequisite for diagnosis only. Two small controlled replays
of the P3-B mutation were used for tracing; no new translation was introduced.
The user stopped Computer Use before final trace validation. This publication
request archives partial results rather than resuming experiments or marking the
phase complete.

# Recommendation

Resume P4 only when requested, first configuring/verifying a windowed private
test run. Follow verified string-copy lifetimes through width/glyph consumers,
then update the classification and P5 recommendation. Keep actual Japanese
differential NOT EXECUTED until lawful local inputs become available. No P5
implementation, font/executable patch or renderer hook is justified by this
partial snapshot.
