# Phase

P8-1 — Runtime punctuation support (ellipsis, dash). Authorized by the human on 2026-11-08
("需要你授權的 runtime 改進<==可以").

# Scope

1. Let the runtime carry `…` (U+2026) and a full-width dash.
2. Restore the ellipses that earlier waves had to drop.

Out of scope here: the journal draw path. It is investigated separately; see
`docs/research/U9_JOURNAL_PATH.md` when present.

# Status

PASS WITH LIMITATIONS. Everything was verified offline. No in-game session has been run yet
(it needs the human's 「準備好了」).

# Environment

- Runtime: `U9ChtRuntime/0.2.9-p8-1`. Built with Visual Studio 18 2026, Win32, into
  `.local/p8-1/build` (LOCAL ONLY).
- DLL SHA-256: `1a973eccc0e979bc98d22fe0b3c67f5a4086da3e07aabb8e7487cbc2b1c9b7b4`.
- Launcher SHA-256: `7d23374afb1aa3c8a53972c7fb1396947ca7b996b75b817fc05ff7bd7924cf0b`.
- Font: Noto Sans CJK TC 2.004, SHA-256 `dce08bd4…88b4` (local only).
- The previous runtime, 0.2.8 (`fc22c7a6…938c7c`, `.local/p8-0/build-d`), is kept as the rollback.

# Inputs

- `translation/zh-TW/text.jsonl`: 7,368 draft records.
- GDI advances measured through `u9cht/gdi_raster.py` using the pinned font.

# Work Performed

**Font measurement (CONFIRMED).** GDI cell advances at 20 px / 40 px:

| Scalar | 20 px | 40 px | Logical (16/em) | Representable |
| --- | --- | --- | --- | --- |
| U+2026 `…` | 20 | 40 | 16 | yes |
| U+2015 `―` | 20 | 40 | 16 | yes |
| U+2014 `—` | 18 | 36 | 72/5 | no |

The engine needs `advance*16/em` to be an integer, and equal at both sizes, so U+2014 cannot be carried
without changing the metric model. U+2015 is the full-width horizontal bar and gives a correct
`――` dash.

**Runtime and contract changes.**

- `runtime/U9ChtRuntime/identity.cpp`: the glyph allowlist now accepts U+2015 and U+2026.
- `u9cht/l10n/runtime_pack.py`: `RUNTIME_CONTRACT.custom_scalar_ranges` mirrors the runtime change, and
  `scalar_class` treats both as punctuation.
- The version is bumped to 0.2.9 in `runtime/CMakeLists.txt`, `runtime/common/version_manifest.h` and the contract.

**QA rule change.** `u9cht/l10n/qa.py` adds `…` and `―` to the set that may not start a wrapped line.
They may open line 1, because a sentence can legitimately continue from the previous one
(`……而且`). This makes the rule stricter, not weaker.

**Translation.** For 192 records the English source contains `...` but the target had dropped the
pause. Each was revised by hand to `……` and rewrapped with the font-measured wrapper. Only the
targets changed: terms, annotations and notes are preserved, and runtime evidence was cleared on change.

# Findings

- CONFIRMED: U+2026 and U+2015 have exact full-width advances in the pinned font.
- CONFIRMED: U+2014 has a 0.9 em advance and stays unsupported. `validate` still reports it.
- CONFIRMED: no English source in the translated corpus contains `--` or `—`, so no dash was needed yet.

# Evidence

| Check | Result |
| --- | --- |
| Offline check (`U9ChtShowcaseCheck`, full pack) | PASS: 7,095 plans, 2,291 glyphs, 4,582 cache entries / 16,384; prewarm 2,172 ms |
| U+2026 offline raster | advance 20 / 40, coverage `26f9099b…` (20 px), `d83037b4…` (40 px) |
| Runtime vs Python GDI raster hashes | 4,582 = 4,582, identical |
| Build | pack `.local/p8-1/out/runtime/allowlist.u9ct`, text.flx `852adf9b…ab0a`, mutation audit PASS |

The glyph count is unchanged at 2,291: U+2026 was added and `～` (U+FF5E, only used in 1037) was removed.

# Tests

- `ctest` (Release): 6/6 passed. `identity_tests` now loads a pack with U+2015 and U+2026 and rejects one with U+2014.
- `python -m unittest discover -s tests`: 153 run, OK, 3 skipped. New assertions cover:
  - `runtime_scalar_issues` accepts `……` and `――` and rejects `—`;
  - an ellipsis may open the text but not a wrapped line.
- `validate` (development): PASS, 0 errors, 69 warnings (unchanged: 3–4 line records), 274 info, 374 unknown-layout journal lines.

# Results

Ellipses now read naturally in 192 lines. The runtime change is two scalars wide.

# Files Changed

`runtime/U9ChtRuntime/identity.cpp`, `runtime/common/version_manifest.h`, `runtime/CMakeLists.txt`,
`runtime/tests/identity_tests.cpp`, `u9cht/l10n/runtime_pack.py`, `u9cht/l10n/qa.py`,
`tests/test_p7_pipeline.py`, `translation/zh-TW/text.jsonl`, `translation/TRANSLATION_GUIDE.md`, this report.

# Risks

- In-game rendering of `…` is unconfirmed. The offline raster identity is strong evidence but not a runtime pass.
- Ellipsis lines are 2 characters longer. None crossed into OVERFLOW, and the 3-line count did not change.

# Blockers

None.

# Deviations From Master Plan

None. This is a minimal widening of the allowlist; no executable patch.

# Recommendation

Run an in-game check of a few ellipsis lines when convenient, for example the Britain bard
(987, 989) or Evidious (810, 812).
