# AGENTS.md — Ultima IX CHT Project Rules

> Project: Ultima IX: Ascension Traditional Chinese Localization  
> Project Code: `U9-CHT`  
> Applies to: all AI coding agents, automation agents, local assistants, and scripted research workflows operating in this repository.

---

# 1. Purpose

This file defines the operating rules for AI Agents working on the Ultima IX Traditional Chinese localization project.

The authoritative project plan is:

```text
ULTIMA_IX_CHT_MASTER_PLAN.md
```

Agents MUST read this file and the Master Plan before making changes.

Priority order:

```text
1. Human instruction in the current task
2. AGENTS.md
3. ULTIMA_IX_CHT_MASTER_PLAN.md
4. Phase reports already approved by the human
5. Existing source code / tests
```

If these conflict, stop and report the conflict.

---

# 2. Current Project Strategy

The project strategy is:

```text
Original Ultima IX
+ TITAN / tgwUltima-derived tooling
+ Japanese Ultima IX as a local research Oracle
+ minimal binary intervention
+ reproducible localization pipeline
```

The project is NOT currently pursuing:

```text
- full engine rewrite
- game remake
- large renderer replacement
- mass translation before technical PoC
- unrestricted executable patching
```

---

# 3. Phase Authorization Model

The Master Plan is divided into phases.

Agents MUST NOT assume that later phases are authorized.

The human must explicitly authorize each execution batch.

Example:

```text
Authorized:
P0
P1
P2 limited to text.flx

Not authorized:
P3+
```

If a task says:

```text
Execute P0-P2 only
```

then the Agent MUST stop after P2 even if P2 passes.

Do not continue automatically.

---

# 4. Mandatory Startup Procedure

Before modifying files, the Agent MUST:

1. Read `AGENTS.md`.
2. Read `ULTIMA_IX_CHT_MASTER_PLAN.md`.
3. Inspect repository status.
4. Identify the currently authorized Phase(s).
5. Confirm local game assets are outside tracked Git paths.
6. Confirm no copyrighted Ultima IX assets are staged.
7. Record relevant tool / dependency versions.
8. Record the exact upstream commit if using TITAN / tgwUltima.

Recommended startup checks:

```bash
git status
git remote -v
git branch --show-current
git rev-parse HEAD
```

If this repository includes a tgwUltima fork/submodule/vendor tree, also record its exact commit.

---

# 5. Copyright / Asset Rules

The Agent MUST NOT commit, publish, or package copyrighted game assets unless the human explicitly provides proof that redistribution is permitted.

Examples that MUST remain local/private:

```text
u9.exe
text.flx
misctext.flx
typename.flx
books-*.flx
speech files
music
videos
textures
models
official fonts
Japanese language-pack assets
full extracted English text dumps
full extracted Japanese text dumps
```

Local research copies should be placed under ignored paths such as:

```text
.local/
game/
oracle/
research-private/
private-data/
```

These paths MUST be covered by `.gitignore`.

Before any commit, inspect:

```bash
git status --short
git diff --cached --name-only
```

If a copyrighted asset is staged accidentally:

STOP.

Do not commit.

---

# 6. Local Path Rules

Never commit machine-specific absolute paths such as:

```text
C:\Games\Ultima IX\
D:\U9\
/Users/name/Games/U9/
```

Use:

```text
environment variables
config.example.json
CLI arguments
relative paths
```

Local configuration files should be ignored.

Example:

```text
U9_GAME_DIR
U9_JP_GAME_DIR
```

Example local config:

```json
{
  "english_game_dir": "LOCAL_ONLY",
  "japanese_game_dir": "LOCAL_ONLY"
}
```

Do not commit real user paths.

---

# 7. Evidence-First Rule

Do not promote guesses into architecture.

Every reverse-engineering conclusion should be classified as:

```text
CONFIRMED
STRONG EVIDENCE
HYPOTHESIS
UNKNOWN
```

Examples:

```text
CONFIRMED:
text.flx entry 123 contains the tested runtime string.

STRONG EVIDENCE:
Japanese executable imports an API absent from the English executable and the call path reaches text rendering.

HYPOTHESIS:
Japanese glyphs may be stored in a bitmap atlas.

UNKNOWN:
Exact width calculation algorithm.
```

Reports MUST distinguish these levels.

---

# 8. Binary Research Rules

When examining FLX or executable formats:

DO:

```text
record hashes
record offsets
record sizes
record entry IDs
record minimal hex samples
document repeatable steps
write tests
```

DO NOT:

```text
paste large copyrighted binary dumps
store full extracted assets
normalize unexplained bytes
silently discard unknown structures
```

Unknown bytes MUST be preserved unless there is evidence they are safe to regenerate.

---

# 9. FLX Parser / Writer Rules

For every FLX resource type:

1. Inspect before modifying.
2. Establish entry count.
3. Establish header/table behavior.
4. Establish offsets.
5. Establish alignment.
6. Establish null-termination rules.
7. Establish encoding empirically.
8. Build exporter.
9. Build importer.
10. Test unchanged round-trip.
11. Only then modify actual content.

A parser that can read is NOT enough.

A writer that produces a file is NOT enough.

The required baseline is:

```text
read
→ export
→ import
→ verify
```

---

# 10. Round-Trip Policy

Preferred result:

```text
SHA256(original) == SHA256(rebuilt)
```

If exact equality is not achieved, the Agent MUST NOT simply declare success.

Instead produce a difference report containing:

```text
original SHA-256
rebuilt SHA-256
file sizes
difference count
difference ranges
changed header fields
changed offsets
changed padding
whether semantic content changed
whether runtime accepts rebuilt file
```

Possible status values:

```text
BYTE-PERFECT PASS
SEMANTIC PASS
RUNTIME PASS
FAIL
BLOCKED
```

Do not conflate them.

---

# 11. Text Encoding Rules

Do not assume all Ultima IX resources use the same encoding.

Encoding must be established per resource type.

Possible encodings may include:

```text
ASCII
Windows-1252
UCS-2LE
UTF-16LE-like data
Shift-JIS
custom indexed encoding
mixed control/text encoding
```

For each resource, record:

```text
encoding
terminator
BOM presence
control bytes
length semantics
invalid sequence behavior
```

---

# 12. Japanese Oracle Rules

The Japanese Ultima IX installation/language pack is a RESEARCH ORACLE.

It may be used locally to determine:

```text
encoding differences
font resources
glyph mapping
text rendering code paths
layout behavior
language-specific executable changes
```

It MUST NOT be copied into the repository.

Differential reports should contain:

```text
hashes
file-size differences
entry counts
API/import differences
function-level findings
small diagnostic byte samples
human-written conclusions
```

Do not include full Japanese assets.

---

# 13. Executable Patching Rules

Patching `u9.exe` is high risk.

Agents MUST NOT make broad executable modifications without explicit authorization.

Before executable patching:

1. Document why resource-only modification is insufficient.
2. Identify the specific code path.
3. Identify exact patch location(s).
4. Record original bytes.
5. Record replacement bytes.
6. Explain control-flow impact.
7. Build automated verification.
8. Provide rollback path.

No unexplained binary patches are acceptable.

Avoid:

```text
large opaque DLL injection
large hook frameworks
renderer replacement
```

unless the human explicitly authorizes them after earlier approaches fail.

---

# 14. Font / Renderer Rules

Do not implement FreeType / DirectWrite / SDL overlay merely because Chinese glyphs are missing.

First determine:

```text
Does the native Japanese path already solve CJK rendering?
Can its font resource be adapted?
Can glyph tables be extended?
Can the original width table be extended?
```

Preferred priority:

```text
A. Reuse native CJK path
B. Extend native bitmap/font resources
C. Minimal renderer hook
D. Full custom text overlay
```

C and D require explicit authorization.

---

# 15. Minimal PoC Rule

When P3 is authorized:

Only one or a very small number of strings may be modified initially.

Preferred examples:

```text
Honesty → 誠實
Britannia → 不列顛尼亞
```

Do NOT batch-translate hundreds of strings.

The goal is to isolate:

```text
archive
encoding
renderer
glyph
layout
```

one layer at a time.

---

# 16. Translation Data Rules

The canonical translation database must NOT be raw FLX files.

Use structured translation records.

Example:

```json
{
  "key": "text.flx:00123",
  "source": "Honesty",
  "target": "誠實",
  "status": "approved",
  "context": "",
  "notes": ""
}
```

Recommended statuses:

```text
untranslated
draft
review
approved
blocked
```

Do not overwrite approved translations without explaining why.

---

# 17. Terminology Authority

Translation terminology should follow the project's authority hierarchy.

Recommended order:

```text
1. Official Taiwan localization terminology, if legally available
2. Established Taiwan Ultima-series terminology
3. Project glossary
4. English source meaning
5. Community references
```

If the human supplies an official Taiwan manual locally:

The Agent may use it as a local authority source.

Do NOT commit:

```text
scans
full OCR text
full manual reproduction
```

The repository may contain:

```text
approved terminology
source location notes
short factual references
```

---

# 18. Automated QA Rules

All translation build steps should eventually validate:

```text
missing translation
duplicate key
invalid Unicode
unsupported glyph
placeholder mismatch
control-token mismatch
newline mismatch
oversized text
unexpected null
resource ID mismatch
```

Never silently drop control markers.

If a source string contains formatting tokens:

```text
%s
%d
\n
special control bytes
script markers
```

their semantics must be preserved.

---

# 19. Testing Requirements

For parser/writer work, tests are mandatory.

At minimum:

```text
unit tests
synthetic fixtures
round-trip tests
malformed-input tests
```

Public fixtures MUST be synthetic or legally redistributable.

Do not include original U9 assets as test fixtures.

If local integration tests require original game files:

Mark them clearly:

```text
LOCAL-ONLY
SKIPPED WHEN ASSETS ABSENT
```

---

# 20. Runtime Verification

When the phase authorizes runtime testing, record:

```text
game version
exe SHA-256
resource SHA-256
modified entry ID
before text
after text
launch result
crash/no-crash
visual result
screenshot path
notes
```

Screenshots containing ordinary gameplay evidence may be kept locally unless the human explicitly requests publishing them.

Avoid committing large screenshot collections by default.

---

# 21. Report Requirements

Every completed Phase must create a report.

Naming:

```text
reports/P0_PRECHECK.md
reports/P1_ASSET_INVENTORY.md
reports/P2_ROUNDTRIP_DIFF.md
reports/P3_FIRST_CHT_POC.md
...
```

Each report MUST contain:

```text
# Phase
# Scope
# Status
# Environment
# Inputs
# Work Performed
# Findings
# Evidence
# Tests
# Results
# Files Changed
# Risks
# Blockers
# Deviations From Master Plan
# Recommendation
```

Status must be one of:

```text
PASS
PASS WITH LIMITATIONS
BLOCKED
FAIL
NOT EXECUTED
```

---

# 22. Final Agent Response Format

When finishing an authorized batch, the Agent should return:

```text
Overall status:
PASS / PASS WITH LIMITATIONS / BLOCKED / FAIL

Authorized phases executed:
P0, P1, P2...

Files created/changed:
- ...

Tests:
- command
- exact result

Key findings:
- ...

Round-trip result:
- ...

Runtime result:
- ...

Assumptions disproven:
- ...

Blockers:
- ...

Recommendation:
- authorize / do not authorize next phase
```

Keep the summary concise but evidence-based.

---

# 23. Stop Conditions

STOP and report immediately if:

```text
1. A copyrighted game asset is about to be committed.
2. A local absolute path is about to be committed.
3. The local U9 version/hash differs from the expected baseline.
4. A FLX structure differs materially from the assumed format.
5. Round-trip corrupts the archive.
6. A one-string modification causes unexplained crash behavior.
7. The Japanese and English versions cannot be compared reliably.
8. A renderer rewrite appears necessary before the native CJK path has been investigated.
9. Executable patching becomes necessary but is not authorized.
10. A task requires downloading or redistributing unauthorized game content.
11. Unknown bytes would need to be discarded to continue.
12. Tests fail in a way that invalidates the current approach.
```

Do not work around these silently.

---

# 24. Git Discipline

Use small, phase-scoped commits.

Recommended examples:

```text
chore: bootstrap U9-CHT project
docs: add P0 preflight report
feat(flx): add text.flx reader
feat(flx): add text.flx writer
test(flx): add synthetic round-trip fixtures
docs: record P2 round-trip findings
```

Avoid giant commits containing unrelated changes.

Before commit:

```bash
git status
git diff
git diff --cached
```

Review for:

```text
game assets
local paths
secrets
large binaries
accidental dumps
```

---

# 25. Dependency Rules

Prefer:

```text
standard libraries
existing project dependencies
well-maintained libraries
```

Avoid introducing a dependency when a small internal implementation is sufficient.

If adding a dependency:

Record:

```text
name
version
license
reason
scope
```

No dependency should be added merely for convenience during a small research experiment.

---

# 26. Tooling Preference

When existing TITAN/tgwUltima code already handles a format correctly:

Prefer:

```text
reuse
extend
wrap
test
```

over:

```text
rewrite from scratch
```

If rewriting is necessary, document why the existing implementation is unsuitable.

---

# 27. Research Notebook Discipline

Reverse-engineering discoveries should be written down immediately.

Preferred location:

```text
docs/research/
docs/formats/
reports/
```

Useful topics include:

```text
FLX structure
text encoding
font format
glyph mapping
renderer call path
Japanese/English binary differences
layout rules
word-wrap rules
```

Do not leave important discoveries only inside terminal history or chat logs.

---

# 28. No Premature Generalization

Do not assume:

```text
text.flx parser == books parser
English behavior == Japanese behavior
Japanese behavior == Chinese behavior
UI strings == dialogue strings
one FLX format == all FLX formats
```

Verify each resource family separately.

---

# 29. No Premature Optimization

Do not optimize before correctness.

Priority:

```text
1. correct
2. reproducible
3. testable
4. understandable
5. fast
```

The corpus is small enough that clarity is preferred during early phases.

---

# 30. Current Recommended Initial Batch

Unless the human explicitly authorizes otherwise, the recommended first execution batch is:

```text
P0 — Preflight & Repository Bootstrap
P1 — Game Asset Inventory
P2 — FLX Text Round-Trip
     scope limited to text.flx
```

Do NOT begin:

```text
P3
P4
P5
...
```

without explicit approval.

---

# 31. Initial Agent Prompt

The following may be used verbatim:

```text
Read:

1. AGENTS.md
2. ULTIMA_IX_CHT_MASTER_PLAN.md

Execute ONLY:

- P0 — Preflight & Repository Bootstrap
- P1 — Game Asset Inventory
- P2 — FLX Text Round-Trip, limited to text.flx

Do not begin P3.

Rules:

- Never commit copyrighted Ultima IX assets.
- Never commit local absolute paths.
- Pin the exact tgwUltima/TITAN upstream commit.
- Record SHA-256 hashes of local files inspected.
- Establish text.flx encoding empirically.
- Prefer extending proven TITAN FLX code.
- Build export/import support.
- Attempt unchanged round-trip.
- If bytes differ, produce a structured binary diff report.
- Do not hide unexplained differences.
- If safe, runtime-test the rebuilt resource.
- Stop after P2.

Required output:

1. Overall status.
2. Files created/changed.
3. Tests and exact results.
4. text.flx round-trip status.
5. Runtime result if tested.
6. Format findings.
7. Assumptions disproven.
8. Blockers.
9. Recommendation on whether P3 should be authorized.

Do not proceed to P3 without explicit human approval.
```

---

# 32. Core Philosophy

This project should advance by narrowing uncertainty.

The intended sequence is:

```text
Can we parse it?
        ↓
Can we rebuild it?
        ↓
Can the game load it?
        ↓
Can Chinese code points reach the renderer?
        ↓
Can Chinese glyphs render?
        ↓
Can Chinese text wrap correctly?
        ↓
Can translation scale safely?
```

At every step:

```text
evidence first
small change
test
report
then continue
```

That rule takes priority over speed.
