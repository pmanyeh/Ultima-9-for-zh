# Phase

P7 — Localization Data Pipeline, 2026-11-03.

# Scope

Explicitly authorized: a deterministic, auditable pipeline from canonical
translation data to Ultima IX resources and the runtime glyph pack. P8 broad
translation is **not** authorized. No timed soak. No new translations were
written. P5.1, P6, P6-S and P6-S2 classifications are unchanged.

# Status

**PASS WITH LIMITATIONS.**

The pipeline is ready for dialogue and item-name production. Resource families
that are not supported are kept out of runtime builds. The main limit before
broad P8 is the current native runtime pack capacity (64 plans). The build
enforces this limit rather than raising it. The existing corpus already uses
60 of the 64 plans.

The combined 60-plan pack generated from canonical data passed the native
parser, prewarm and cleanup offline. It has **not** been run in the game.

# Environment

- Starting HEAD `bb310b424285d9d44ad65eb193abbe57933cfa0e`, `main`; committed on
  branch `p7-localization-pipeline` (the commit containing this report is the
  ending HEAD).
- Windows 11 x64, Python 3.12.10, Git 2.55.0.windows.3. Existing MSVC
  19.51.36252.0 / CMake 4.3.1 build cache for native tests.
- TITAN 0.7.8 / tgwUltima pin `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`
  (unchanged).
- No new dependency. Standard library only (`json`, `csv`, `hashlib`,
  `unicodedata`).
- Native runtime unchanged: `U9ChtRuntime/0.2.3-p6s2`, DLL SHA-256
  `532ef1c916ceac215eb98cc03c5f2ada0b5ca4411cd4f9bb2a8a9e9f715a839f`.

# Inputs

All protected inputs match `reports/P0_HASHES.json`.

| Input | SHA-256 |
| --- | --- |
| English executable | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| text.flx | `378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0` |
| TYPENAME.FLX | `26c9042d2e8f0f55559c84c22113ae62348ed0694375ad02b4fe65fea9e3f4ca` |
| BOOKS-EN.FLX | `a0653ef3608537575e707faa56aca6f24efc2eddaab554d49279d6c1c1a8858b` |
| misctext.flx | `3c5bb8845ff101bfba87f38dcb253d81eb9bee6580d18c22a1649179e5e9b570` |
| Noto Sans CJK TC 2.004 | `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4` |

# Work Performed

1. Verified HEAD, the clean tracked tree, ignored assets, the five P0 hashes
   and the font hash. Baseline: Python 102/102, native 6/6.
2. Rebuilt the historical P6-S and P6-S2 artifacts with the legacy builders.
   All five recorded hashes reproduced. This gives a byte-exact regression
   target.
3. Built the `u9cht/l10n/` package:
   - `store`: schema, keys, JSONL.
   - `glossary`: terminology QA.
   - `adapters`: one adapter per FLX family, plus the mutation audit.
   - `qa`: drift, layout, kinsoku and font checks.
   - `runtime_pack`: the existing U9CTP51 v2/v3 format, the contract and
     capacity limits.
   - `pipeline`: validation, selection and the build.
   - `workset`: export and import.
   - `migrate`: the one-way showcase migration.
   - `cli`.
4. Added five scripts:
   - `validate_translation.py`
   - `build_localization.py`
   - `export_translation_workset.py`
   - `import_translation_workset.py`
   - `migrate_showcase_store.py`
5. Created the canonical store, schema, glossary, capability matrix, source
   baseline, QA guide and frozen-snapshot notice.
6. Migrated 61 showcase records. Rebuilt the historical artifacts from the
   canonical store, built the full development corpus twice, and ran the
   native offline checker on the new pack.
7. Demonstrated on real local data: source drift, resource drift, the
   approved profile and workset conflicts. All demonstration outputs are under
   `.local/`.

# Findings

1. **Canonical schema** (CONFIRMED by tests): one JSONL record per line,
   sorted by (resource, entry_id), with a fixed field order, UTF-8 and LF.
   - Fields: `key`, `resource`, `entry_id`, `status`, `category`, `speaker`,
     `context`, `notes`, `terms`, `target`, `source_sha256`, `source_units`,
     `review{terminology,language,runtime}`, `runtime_supported`,
     `runtime_evidence`, `migrated_from`.
   - Keys are `resource:entry_id` and are validated against the
     `resource`/`entry_id` fields.
   - Writing any order other than the canonical serialization is a
     validation error.
2. **Migration**: 61 records in total.
   - 39 opening subtitles (P6-S).
   - 20 Gypsy records: 15 dialogue and 5 responses (P6-S2).
   - 1 `TYPENAME.FLX:5290` (`急救箱`).
   - 1 `BOOKS-EN.FLX:182` draft.

   Targets, keys, source hashes, speaker, context, notes and the
   `showcase-draft` status are preserved. `runtime_evidence` is copied from
   the report JSON:
   - 9 P6-S records are composited; 6 have screenshots.
   - 20 Gypsy records are composited; 9 of them appear in the 7 P6-S2
     screenshots.
   - The item name is composited.

   `review.runtime` stays false and no status was promoted. Migration is
   deterministic: `--check` reports "matches".
3. **Single source of truth**: `translation/zh-TW/*.jsonl`. The four
   `translation/showcase/*.json` files are frozen evidence, protected by
   LF-normalized SHA-256. The legacy builders still read them, so P6 stays
   reproducible.
4. **Resource capability matrix** (`translation/resource-capabilities.json`;
   every value cites evidence):

| Resource | Decode | Round-trip | Translate build | Unicode runtime |
| --- | --- | --- | --- | --- |
| text.flx | CONFIRMED | byte-perfect (P2) | CONFIRMED | **bounded**, CONFIRMED (subtitles, NPC dialogue, responses) |
| TYPENAME.FLX | CONFIRMED | byte-perfect (P6-S2) | ASCII-marker bridge | **bounded**, one item CONFIRMED; last session exit 1, cause UNKNOWN |
| BOOKS-EN.FLX | CONFIRMED | byte-perfect (P6-S2) | ASCII only | **false / UNKNOWN** |
| misctext.flx | UNKNOWN | UNKNOWN | none | UNKNOWN |

5. **Source drift** (CONFIRMED):
   - Every build compares each resource's SHA-256 with
     `translation/sources.json`.
   - It also compares each record's `source_sha256` and `source_units` with
     the local entry.
   - A resource-hash mismatch fails unless `--allow-resource-drift` is
     passed. Even then, per-entry drift is still a hard `SOURCE DRIFT` error,
     reporting the resource, entry ID and expected/observed SHA.
   - Real-data demonstration (one character changed in entry 4164 of a
     private copy): the strict run reported `resource-drift`. The relaxed run
     reported `source-drift` 4164 with expected `88507320…` and observed
     `85b4381c…`. The build was refused and no output directory was created.
6. **Terminology**: `translation/glossary/U9_TERMS.csv` has 14 rows: 5
   English-retained names (`review`), 8 virtues and First Aid Kit (`draft`).
   - The virtues come from the Master Plan render sample; First Aid Kit comes
     from TYPENAME 5290.
   - No row is `approved` and none claims to be official.
   - The QA checks: one source with multiple approved targets; one approved
     target used for several sources; blocked terms appearing in targets;
     tagged terms not using the approved target (mandatory → error,
     recommended → warning, informational → info).
   - Untagged-term detection runs only when local source text is available
     and is diagnostic only.
7. **English stays out of Git**: canonical records hold only hashes and unit
   counts. Worksets and reports are refused inside the repository unless they
   are in an ignored directory. A test fails if a tracked record contains a
   `source`/`text` field or an English sentence.
8. **Local workset**: `export_translation_workset.py --output
   .local/translation-work [--only ...]` merges each local English source
   with the canonical target, status, context, hash and `base_revision`.
   Real-data run: 50 text, 5 TYPENAME and 1 book row.
9. **Safe import**: all-or-nothing. Any of the following aborts the import
   and the store is left unchanged:
   - duplicate key;
   - source hash mismatch with the canonical record or local source;
   - stale `base_revision`, so newer canonical data is never overwritten;
   - unknown key without `--create`;
   - status regression without `--allow-status-regression`;
   - an approved target overwritten without `--force`;
   - an invalid result record.

   Real data: an unchanged import makes 0 changes. One edit makes 1 change
   (dry run). Stale-base and unknown-key imports conflict. The canonical
   store was byte-identical afterwards.
10. **Layout preflight**:
    - Measured profiles: text.flx subtitle/dialogue/response use a 528-unit
      budget and have been observed with up to 2 lines. TYPENAME item names
      use a 192-unit budget, single line.
    - CJK widths come from pinned-font advances, which must agree at 20 and
      40 px. ASCII uses a disclosed, unmeasured 16-unit estimate.
    - Results are PASS, WARNING, OVERFLOW or UNKNOWN-LAYOUT. Journal, UI and
      books have no geometry and report UNKNOWN-LAYOUT.
    - Text is never rewritten. Authored `\n` stays explicit.
11. **Punctuation**: minimal kinsoku. A line starting with
    `，。、！？；：）》」』】〕〉`, or ending with `（《「『【〔〈`, is a WARNING. So
    are empty lines, padded lines and more lines than observed. WARNING fails
    the `approved` profile.
12. **Font coverage**: every custom scalar in active runtime records is
    measured with the hash-checked font through the existing GDI rasterizer.
    Missing or inconsistent glyphs report `U+XXXX`, the character and every
    key that uses it.
13. **Glyph manifest**: derived from active targets only; there is no
    hand-written allowlist. Current development corpus:
    - 347 unique scalars: 340 Han, 7 punctuation.
    - 22 Latin/native characters.
    - 0 missing.
    - 694 of 1,024 cache entries needed.
    - Pack `043795b2ba245cd2182c891d39d4ca76c362bb87def28076b6de6854dc39a0ed`.

    Capacity overflow is rejected, never raised. Characters the native pack
    cannot carry (for example U+2014) and identical text-plan targets are
    errors.
14. **Profiles**: `development` allows draft, showcase-draft, review and
    approved. `approved` allows approved only, and also fails on WARNING and
    UNKNOWN-LAYOUT. `blocked` and `untranslated` are never applied. The
    approved profile currently selects 0 records, because no approval was
    invented.
15. **Determinism** (CONFIRMED): two full development builds produced
    identical directory trees. A synthetic test also builds twice and
    compares every output byte.
16. **Mutation audit** (CONFIRMED): for each resource the audit records the
    original and output SHA, changed entries, unchanged count, relocated
    offsets, changed header fields (only the 0x58/0x5C size fields are
    allowed) and unexpected differences. The build fails on any unexpected
    difference. Tests inject an unselected entry change, an unknown header
    byte flip and a missing intended change; all three FAIL. TYPENAME opaque
    and trailing bytes are preserved.
17. **Showcase regression** (CONFIRMED, byte-exact): built from canonical data
    alone with `--only` selections.

| Artifact | Historical SHA-256 | Canonical pipeline |
| --- | --- | --- |
| P6-S text.flx | `71eea155…7de4d47` | identical |
| P6-S pack (v2) | `3163a669…4ff4d1dd` | identical |
| P6-S2 text.flx | `1f72ff74…f041c12191` | identical |
| P6-S2 TYPENAME | `7a765bf7…64aab606e432` | identical |
| P6-S2 pack (v3) | `54b07a81…b9f49c` | identical |

   The new combined development pack (60 plans: 59 text plus 1 name, v3)
   passed the unchanged native `Pack::load`, prewarm, reuse and cleanup in
   `U9ChtShowcaseCheck` with 694/694 native/Python raster hashes equal.

# Evidence

Private and ignored:

- `.local/p7/build/legacy-*`, `final-a`, `final-b`: builds.
- `.local/p7/native-prewarm-dev.jsonl`: native offline log.
- `.local/p7/qa-drift*`: drift reports.
- `.local/translation-work/`: workset.

No asset, English text, font, binary or screenshot is tracked.

Final development build:

- Canonical store `4388434575d63a5c6e564647a93f8552ba0763b7583e4ffa63e64f763d1d9a3f`
- Glossary `578100bb1b3e8deb627aea3043b8b1d737a36682f255c4db456a198918ec65b3`
- Runtime contract `614c1798d62d4cffe4e0fcf1258ff62a2e44f78cd60b8978a4afb0c73cabe734`
- text.flx output `d45449077dedc19b37beaf5dd0b86075cf5adf3bd34b008d5cffcd8918726893`
  (59 changed, 7,597 unchanged)
- TYPENAME output `7a765bf78a8dd6c9fd7812bb2c347208a5ae1e04d8eea8e6152b64aab606e432`
  (1 changed, 8,191 unchanged)
- Mutation audit PASS. Layout: PASS 60, WARNING 0, OVERFLOW 0, UNKNOWN 0.

# Tests

```powershell
$env:U9_GAME_DIR = "<private game copy>"
python -m unittest discover -s tests
& "<cmake cache CTEST>" --test-dir .local/p6s2/build-names -C Release
python scripts/validate_translation.py --game-dir $env:U9_GAME_DIR --font $env:U9_CJK_FONT
python scripts/migrate_showcase_store.py --check
```

- **Python 138/138 PASS**: 102 existing plus 36 new, including 2 LOCAL-ONLY
  tests that run when assets are present and skip when they are absent.
- **Native 6/6 PASS** (unchanged sources).
- New coverage:
  - schema/field parity, key parsing and JSONL determinism/strictness;
  - duplicate keys;
  - record language/control checks;
  - source and resource drift;
  - locked, alias and placeholder checks, and book control tokens;
  - workset export, no-op, update, all conflict classes and explicit options;
  - glossary conflicts and terminology levels;
  - font coverage and glyph manifest;
  - layout overflow, warning and unknown, plus kinsoku;
  - capability evidence;
  - profiles and unsupported runtime families;
  - renderer scalar checks;
  - deterministic build, manifest and output safety;
  - mutation audit tamper detection;
  - native contract parity with `identity.h`, `glyph_cache.h` and the version
    header;
  - legacy-builder pack equivalence;
  - capacity rejection;
  - frozen snapshots;
  - lossless migration;
  - no source text in the tracked store;
  - 1,000-record throughput: validation, lookup, ordering, glyph collection,
    QA aggregation, capacity planning and a 1,000-entry resource build.
- No time-based assertions.

# Results

P7 gate items:

- **Met:**
  - canonical store;
  - migration;
  - glossary;
  - local workset;
  - drift protection;
  - validation command;
  - layout, font and glyph QA;
  - deterministic text.flx and TYPENAME builds;
  - an accurate BOOKS representation (stored, excluded, listed);
  - build manifest and mutation audit;
  - the PoC pack generated from canonical data;
  - regressions green;
  - no source dump committed.
- **Limited:** the combined pack has no in-game smoke; the runtime capacity
  ceiling.

# Files Changed

- New package: `u9cht/l10n/` (`__init__`, `store`, `glossary`, `adapters`,
  `qa`, `runtime_pack`, `pipeline`, `workset`, `migrate`, `cli`).
- New scripts: `validate_translation.py`, `build_localization.py`,
  `export_translation_workset.py`, `import_translation_workset.py`,
  `migrate_showcase_store.py`.
- Legacy builder docstrings now say "historical".
- New `translation/`:
  - `schema/translation.schema.json`
  - `zh-TW/{text,typename,books}.jsonl`
  - `glossary/U9_TERMS.csv`
  - `resource-capabilities.json`
  - `sources.json`
  - `qa/README.md`
  - `showcase/README.md`
- `tests/test_p7_pipeline.py`.
- This report and its JSON; the Master Plan P7 checkpoint; README.

# Risks

- ASCII widths are estimates, not measurements, so mixed Latin lines near the
  budget may still clip at runtime.
- Layout geometry is known only for subtitle, dialogue, response and item-name
  surfaces.
- The combined pack has not been seen in the game. The offline native parser
  accepting it is strong evidence, not runtime proof.
- The TYPENAME runtime rests on one item, and its last session ended with exit
  1 (cause UNKNOWN).

# Blockers

None for P7 itself. Before broad P8:

1. **Runtime pack capacity**: 64 plans and 512 scalars, with 60 plans already
   used. Plans are matched by exact string. This needs a bounded, measured
   runtime capacity change, which requires separate authorization.
2. BOOKS Unicode render path UNKNOWN.
3. misctext.flx has no adapter.
4. No approved terminology yet.
5. TYPENAME normal-exit question.
6. 30 P6-S entries (4174–4203) remain runtime-unobserved.

# Deviations From Master Plan

- Added the `showcase-draft` status for migrated records only, plus an
  `enforcement` column in the glossary.
- `translation/sources.json` holds resource hashes so that individual records
  stay small.
- The frozen showcase stores remain for P6 reproducibility. They are
  hash-locked, not a second editable store.
- The build writes the runtime pack under the legacy name `allowlist.u9ct` for
  launcher compatibility.
- No in-game runtime smoke was run. It was optional, and the offline native
  checker plus byte-exact legacy reproduction were used instead.

# Recommendation

Classify P7 as **PASS WITH LIMITATIONS**. Do not start broad P8 yet.

1. First authorize a scoped **runtime-capacity task** (P8-0): grow the plan
   and glyph capacity with a bounded, measured design (for example
   hash-indexed plans and a larger pinned cache). Keep the existing hooks and
   validate with the event-driven gate. Optionally include one bounded in-game
   smoke of the canonical combined pack.
2. Then run a **first P8 batch** of about 100–200 `text.flx` dialogue and
   subtitle entries from the opening/Stonegate region, going through
   workset → import → validate → build. Fill the untranslated Gypsy-range IDs
   4031, 4047 and 4049 first, and approve a core glossary (names and virtues)
   before release builds.

Books stay excluded until a Unicode book route is proven.
