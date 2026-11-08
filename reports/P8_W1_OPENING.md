# Phase

P8 wave 1 — Earth opening (`MiscNPC/gypsy`, `MiscNPC/Hawkwind`).

# Scope

First authorized P8 translation batch (human, 2026-11-08): the conversation files the player meets
first, `text.flx` entries 4028–4162 (gypsy) and 4164–4300 (Hawkwind), 272 records. The 59 P6
showcase drafts in this range were revised to the approved authority file. No `u9.exe` change,
no runtime change, no new resource family.

# Status

**PASS WITH LIMITATIONS.** All 272 records are `draft`, validate PASS, in-game run clean.
Journal-surface lines were not seen in Chinese (see Findings).

# Environment

- HEAD before this batch `1bcc03f`, branch `p7-localization-pipeline`. Python 3.12.10.
- Runtime `U9ChtRuntime/0.2.8-p8-0a`, DLL SHA-256 `fc22c7a6…938c7c`, launcher `662213c6…76b2`.
- Font Noto Sans CJK TC 2.004, SHA-256 `dce08bd4…88b4` (local only).
- Game copy: private ignored copy; protected assets matched the P0 baseline after the session.

# Inputs

Approved `U9_TERMS.csv` (768 approved), `translation/TRANSLATION_GUIDE.md`, local workset exported
with `export_translation_workset.py --only text.flx:4027-4300` (LOCAL ONLY, contains English).

# Work Performed

| Item | Result |
| --- | --- |
| Translation | 272 records: subtitle 84, dialogue 71, response 63, journal 54 |
| Terms | Each record's `terms` lists the approved terms found in its source; a term inside a longer term (`Gate` in `Black Gate`) is not listed |
| Annotation | Per guide §4.7; first occurrence per conversation file from the tool |
| Line breaks | Authored with the pinned font's measured advances, budget 528, balanced lines; a term and its annotation are never split; responses stay on one line |
| Importer fix | `import_workset` now clears `runtime_evidence` when a target changes (evidence was recorded for the old text); test added |
| Tests | P7 showcase regression tests now build from the migrated P6 data in a temporary store instead of comparing it with the live store, which translation now changes |
| Guide | `…` and `—` rule (see Findings) |

# Findings

- CONFIRMED: the runtime pack rejects `…` (U+2026) and `—` (U+2014); `validate` reports
  `runtime-unsupported-scalar`. The guide's `……` rule cannot be used until the runtime scalar
  ranges are extended (a runtime change, not authorized). The guide now says to rewrite pauses.
  About 190 English lines use `...`.
- CONFIRMED (session): 57 entries composited in game, including the 3-line opening line 4164
  (the human reports it displays fully) and long virtue questions such as 4088 and 4103 with
  their responses (the human reports them complete).
- CONFIRMED (session): journal entries 4078, 4165 and 4249 were never drawn by the runtime, and the
  human saw no Chinese journal text. STRONG EVIDENCE: the journal does not draw through the hooked
  text path. The 54 `journal` records stay in the store and pack (harmless) but have no runtime
  evidence. Whether the history timeline (4216–4242) is journal text stays a HYPOTHESIS.
- English width inside annotations is still the unmeasured estimate (16 units per ASCII character).
- The human saw an English "Not yet" response in the gypsy menu. The only `text.flx` entry with that
  text is 229 (`Ambrosia/Yastar`). STRONG EVIDENCE: responses can reuse entries from other
  conversation files. Entry 229 was translated as a follow-up (not tested in game). The tools
  cannot yet list which entries a conversation uses, so such gaps surface only in play.

# Evidence

Session `.local/p8-w1/session-1` (LOCAL ONLY), log SHA-256 `d0e11488…2b5a`:

| Check | Result |
| --- | --- |
| exit code | 0 |
| failure events, fault counters, raster faults | none, none, 0 |
| plans / glyphs / rasters | 273 / 1,013 / 2,026; prewarm 1,047 ms; 0 cache misses |
| raster hashes runtime vs offline | 2,026 = 2,026, identical |
| composited / drawn entries | 57 / 58 |
| restoration | protected assets match P0, saves and config restored, keymap unchanged |

Build: pack `c8b6e98a…4c17`, rebuilt `text.flx` `f3d6c020…183e`, mutation audit PASS.

# Tests

- `python -m unittest discover -s tests`: 151 run, OK, 3 skipped.
- `validate` (development): PASS, 0 errors, 1 warning (4164: 3 lines; confirmed in game), 1 info.

# Results

The Earth opening reads in Chinese with the approved terminology. 58 records carry
`P8-W1:composited` or `P8-W1:drawn` evidence.

# Files Changed

`translation/zh-TW/text.jsonl`, `translation/TRANSLATION_GUIDE.md`, `u9cht/l10n/workset.py`,
`tests/test_p7_pipeline.py`, this report.

# Risks

- 214 of 272 records were not reached in this session (other virtue paths, Stonegate, taunts).
- Journal lines will show English until the journal path is supported.
- Annotation English width is estimated, not measured.

# Blockers

None for continuing dialogue translation. Chinese journal text needs a separate, authorized runtime investigation.

# Deviations From Master Plan

None. Master Plan §15 lists UI/system first; `misctext` has no tooling, so dialogue comes first.

# Recommendation

1. Continue P8 with the next dialogue batch (Britain, the first town).
2. Decide whether to authorize a runtime change for `…`/`—` and an investigation of the journal path.
