# Phase

P8-A — Terminology Authority.

# Scope

Build the U9 terminology authority file and translation guide before broad translation,
modelled on the U7 `Translation_Guide.md` and the U8 `authority.tsv`. Authorized by the
human on 2026-11-08. Decisions recorded at authorization:

- Series name conflicts: U8 wins over U7.
- No U9 Taiwan Chinese manual has been found yet; add it later with top priority.
- Guide at `translation/TRANSLATION_GUIDE.md`; names stay in `translation/glossary/U9_TERMS.csv`.

Not in scope: translating text, approving terms (human decision), game or runtime changes.

# Status

**PASS WITH LIMITATIONS.** Tooling, guide and authority file are complete and tested; the human
approved 768 terms. 669 candidates are still `todo` and the Taiwan manual is not yet compared.

# Environment

- HEAD `3a351750ff3d5228084917919c4f6f716bc06273`, branch `p7-localization-pipeline`, with
  uncommitted P8-0 work. Python 3.12.10, standard library only (no new dependency).
- Local inputs: `text.flx`, `TYPENAME.FLX`, `BOOKS-EN.FLX` matching the P0 baseline hashes in
  `translation/sources.json`.
- U8 authority file (local, other project): SHA-256 `c2a06112…a430`, U8 repository HEAD `b34b70a`,
  last changed in `beec818`. 800 rows read.

# Inputs

U7 `Translation_Guide.md` (223 lines), U8 Master Plan §29, §32 and `localization/README.md`,
U8 `authority.tsv` (815 lines: 17 approved, 764 proposed, 19 ignore), the 14-row P7 `U9_TERMS.csv`.

# Work Performed

| Item | Result |
| --- | --- |
| `u9cht/l10n/terms.py` | Candidate scan adapted from U8 `u8catalog.py terms`, U9 sources, U8 prefill, plural propagation, local review file |
| `u9cht/l10n/cli.py`, `scripts/update_terms.py` | New `terms` command; `--check` reports a stale file without writing |
| `u9cht/l10n/glossary.py` | Columns add `count`, `example`, `annotate`; annotation checks; statuses match U8 (`todo`, `proposed`, `approved`, `keep`, `ignore`, `blocked`); category `title`; `keep` requires target == source |
| `translation/glossary/U9_TERMS.csv` | 14 rows migrated (draft → proposed; retained-English review → todo, target cleared); refreshed to 1,456 rows |
| `translation/TRANSLATION_GUIDE.md` | New guide |
| `translation/resource-capabilities.json` | Stale runtime limits (64 plans) corrected to the P8-0 values |
| Tests | P7 glossary tests updated; `tests/test_p8a_terms.py` added |

English annotation (decided by the human on 2026-11-08, after the first draft):

- Format `譯名(English)` with half-width parentheses.
- `annotate` column: `always` (default for persons), `first` (default for places, organizations,
  titles, spells, monsters, other), `never` (virtues, items, UI). Avatar, Lord British and Guardian
  are set to `first`, and so are the companions Iolo, Shamino, Dupre, Geoffrey, Jaana, Julia,
  Katrina and Mariah.
- U8 annotated at run time in the ScummVM engine; the U9 runtime has no equivalent, so the
  annotation is written into each translation. "First" means the lowest `text.flx` entry ID in
  each conversation file (`ConvoLib\<Region>\<File>`) whose source contains the term; each
  book and label counts separately. HYPOTHESIS: entry order approximates conversation order;
  players taking other branches can see an unannotated line first.
- `validate` reports `annotation-missing` (level from `enforcement`) and `annotation-unexpected`.

Later human decisions (2026-11-08):

- The human revised `U9_TERMS.csv` by hand: 768 proposed, 669 todo, 20 ignore.
  A rescan changed only row order, the Ascension count (not found in game text) and 3 plurals.
- Address: 你 / 妳 (female addressee) / 您 (respect); no 汝.
- Virtues and principles follow the authority file: Truth 真理, Love 愛, Courage 勇氣.
- Taiwan manual: being located by the human.
- The human approved the authority file: all 768 `proposed` rows became `approved`.
  69 targets were shared by spelling variants of one term (case, plurals, `Scroll: X`/`X Scroll`,
  `Buc's Den`/`Buccaneer's Den`). Rather than relax the one-target rule, a row may now declare
  `variant of <source>` in `notes` (tool-written `plural of` references count too); the check
  requires the base to be approved, share the target and not itself be a variant. Two pairings
  were the human's own wording and are worth a second look: `Bell` → 勇氣之鐘 (variant of
  Bell of Courage) and `Sword` → 長劍 (variant of Longsword).
- Effect on the 61 showcase drafts: `validate` stays PASS with 0 errors and 0 warnings; 19
  `term-not-used` and 4 `annotation-missing` info items (draft records report at info level).
  These drafts predate the authority file and need revision before release.

# Findings

- CONFIRMED: `text.flx` dialogue, subtitles and responses contain no ASCII double quotes,
  no placeholders and no control codes. Only 6 lines use `*action*` markers. So the U7
  rule of wrapping every line in 「」 does not apply.
- CONFIRMED: `text.flx` source-file markers name a region and conversation file
  (`ConvoLib\<Region>\<File>`) for each entry, which gives every term a context.
- CONFIRMED: English length median 61 UTF-16 units, 99th percentile 215, maximum 535;
  the runtime refuses translations over 512.
- CONFIRMED: about 3,010 lines use `you`, 73 use `thee/thou/thy`, 192 use `...`.
- CONFIRMED: mantra and spell words are rare (1–2 lines each).
- CONFIRMED: `BOOKS-EN.FLX` uses `` `f ``/`` `F `` (279/14), `` `p ``/`` `P `` (23/8) tokens and
  `#nnn`, `$n` sequences. UNKNOWN: what `#` and `$` mean; the guide says to keep them.
- STRONG EVIDENCE: the scan has noise (menu words such as Shop and Sell, adverbs such as
  Honestly, colour words). U8 handled the same with `ignore`.

# Evidence

Scan result (`python scripts/update_terms.py --u8-authority <U8 authority.tsv>`):

| Category | Rows | | Status | Rows |
| --- | --- | --- | --- | --- |
| item | 1,126 | | todo | 1,426 |
| person | 142 | | proposed | 30 |
| other | 142 | | approved | 0 |
| place | 32 | | | |
| virtue | 11 | | | |
| monster | 2 | | | |
| organization | 1 | | | |

Proposed sources: U8 approved (Avatar 聖者, Guardian 守護者, Lord British 不列顛王,
Britannia 不列顛尼亞, Moongate 月之門, Blackrock 黑石), U8 name proposals (for example
Pagan, Gargoyle, Pyros, Bane), the P7 virtue drafts, the P6-S2 First Aid Kit label and 2 plurals.

The committed `U9_TERMS.csv` holds terms, counts, entry IDs and annotate modes only.
Source sentences are only in `.local/p8a/U9_TERMS_REVIEW.tsv`, which `.gitignore` covers.

# Tests

- `python -m unittest discover -s tests`: 150 run, OK, 3 skipped (141 before P8-A; `test_p8a_terms.py`
  adds annotation, variant and committed-file consistency cases). The P7 assertion that no term
  is approved was removed after human approval; the no-"official" check stays.
- New cases: sentence-opener and title handling, region and file context, item detection,
  hand edits kept, U8 prefill restricted to names, plurals, deterministic and idempotent
  output, committed file holds no sentences, annotation modes and first occurrence per
  conversation file. P7 cases: new columns, `keep`, target and annotate rules,
  `keep` counts as approved in record checks.
- `scripts/update_terms.py --check`: `PASS: authority file is current`.
- `validate` (development profile): PASS, 0 errors, 0 warnings, 23 info.

# Results

The authority file now lists every candidate name with a count and a location. The guide
records U9-specific rules backed by the corpus. Terminology checks in `validate` start
enforcing as soon as terms are approved.

# Files Changed

`u9cht/l10n/{terms,cli,glossary}.py`, `scripts/update_terms.py`, `tests/test_p8a_terms.py`,
`tests/test_p7_pipeline.py`, `translation/TRANSLATION_GUIDE.md`, `translation/glossary/U9_TERMS.csv`,
`translation/resource-capabilities.json`, `translation/qa/README.md`, this report, Master Plan §15.2, README.

# Risks

- Category guesses are heuristic; about 140 rows are `other`.
- Names seen fewer than 3 times mid-sentence are missed unless they are file names or labels.
- Multi-word phrases joined by `of`/`the` can merge two names (`Belmor of the Silver Keep`).
- Variants are separate rows (Blackrock, Black Rock, Buc's Den, Buccaneer's Den).
- U8 transliterations were chosen for U8 and may not fit every U9 character.
- Annotation makes lines longer; response menus are narrow and their width limit is not measured.
- "First per conversation file" follows entry order, not the order a player sees.

# Blockers

None for this phase. Before broad translation: none. 669 `todo`
candidates can be decided as translation reaches them; compare the manual when available.

# Deviations From Master Plan

The Master Plan glossary had 6 columns and draft/review statuses. Statuses now follow U8 at the
human's request; `enforcement`, `count` and `example` are kept as extra columns.

# Recommendation

1. The human reviews `U9_TERMS.csv` with the local review file: decide the guide's open items,
   then approve or keep the persons, places and series terms, and mark noise `ignore`.
2. Then authorize the first P8 translation batch.
