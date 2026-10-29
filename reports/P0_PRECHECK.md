# Phase

P0 — Preflight & Repository Bootstrap. Started 2026-10-28; resumed/completed
2026-10-29 (Asia/Taipei).

# Scope

Initial authorized batch: P0, P1, P2 limited to `text.flx`. P3+ not authorized.
Read AGENTS.md and Master Plan; reviewed their approach without modifying them.

# Status

PASS WITH LIMITATIONS. Local baseline and toolchain established. Exact patch
label and external remote hosting remain unspecified.

# Environment

Windows 11 build 26300; PowerShell 5.1.26100.9711; Git 2.55.0.windows.3;
Python 3.12.10; .NET SDK 10.0.302; ripgrep 15.2.0. Project tools use Python
standard library plus one MIT TITAN reader source module; no package installs.
Computer Use bundled skill was used only for runtime observation/cleanup.

# Inputs

User-supplied local English GOG installation, kept outside repository paths.
GOG game ID `1207659093`, build ID `59198760502252807`, metadata language English.
User confirmed no Japanese installation. Exact patch label UNKNOWN; u9.exe has
no FileVersion resource. All inspected file hashes are in `P0_HASHES.json` and
`P1_ASSET_INDEX.json`; source-document hashes are also recorded.

TITAN 0.7.8 / tgwUltima commit `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`.
UltimaPatcher reference commit `c5db7b77b93a3b99b27556c3e5d8654d1679ced5`.

# Work Performed

Initialized the previously non-Git folder on `main`; added private-path/asset
ignore rules, portable configuration example, hash capture/check tooling, tests,
MIT attribution and reference pins. No remote was supplied. Staging was empty at
startup; phase-scoped local commits and clean-clone verification form the local
baseline. Full private game copies/exports stay under `.local/` and are ignored.

# Findings

- CONFIRMED: no tracked or staged official game files at startup.
- CONFIRMED: pinned upstream needs validation/preservation wrapping; four synthetic
  behaviors are detailed in `P0_UPSTREAM_AUDIT.json` and reference-projects.md.
- CONFIRMED: original executable/resource hashes remained unchanged on resume.
- UNKNOWN: installed patch lineage beyond the observed GOG metadata and hashes.

# Evidence

`P0_HASHES.json`, `P0_UPSTREAM_AUDIT.json`, `THIRD_PARTY_NOTICES.md`,
`docs/research/reference-projects.md`, `docs/research/PLAN_REVIEW.md`.

# Tests

`python scripts/audit_upstream.py`: 4/4 synthetic audit probes reproduced.
Preflight tests cover missing installation, correct hash capture, unchanged
source, relative-only output, invalid baseline, matching hashes and changed-input
stop. Full suite results are recorded in P2's report.

`python scripts/preflight.py --game-dir $env:U9_GAME_DIR --baseline reports/P0_HASHES.json --output .local/preflight-resumed.json`:
exit 0, PASS WITH LIMITATIONS, for this exact recorded local baseline; any change must block.
Without a baseline the tool intentionally reports BLOCKED, not certification of
an unknown edition.

Clean clone of code commit `5e84a3b` succeeded. Without game assets or the private
upstream clone, `python -m unittest discover -s tests -v` ran 23 tests: 22 passed,
1 LOCAL-ONLY test skipped, exit 0. The clone remained clean and retained identical
instruction/vendor bytes. Exact final check results are in `VALIDATION.json`.

# Results

Environment, upstream version, local game hashes and private/public boundary are
recorded. No executable patch, renderer change or game-content download occurred.
Git staging/commit checks exclude copyrighted assets, private paths and dumps.

# Files Changed

`.gitignore`, `README.md`, `config.example.json`, `THIRD_PARTY_NOTICES.md`,
`scripts/preflight.py`, `scripts/audit_upstream.py`, `tests/test_preflight.py`,
P0 reports, `docs/research/`. Supplied AGENTS.md/Master Plan remain byte-identical.

# Risks

A local hash baseline does not certify official patch provenance or compatibility
with other editions. Vendored reader updates must be reviewed against the pin.

# Blockers

None for local English inventory/unchanged text validation. No Japanese oracle
is available for future P4. No remote/fork destination has been configured.

# Deviations From Master Plan

Python was selected instead of the suggested C# directory structure to reuse the
existing MIT Python reader without unrelated dependencies. Only that reader is
vendored; source inspection clone remains private. The initial runtime attempt
was stopped by the user, then resumed after explicit instruction to continue.

# Recommendation

Use this exact observed baseline for P1/P2. Keep patch label UNKNOWN rather than
guess 1.19f/1.19h; require hash review before any future different installation.
