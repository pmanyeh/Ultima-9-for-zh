# Phase

P8 wave 2a — Britain core (`Britain/LordBritish`, `Britain/Iolo`, `Britain/IoloGhost`, `Britain/ShrineCompassion`).

# Scope

Second authorized P8 batch (human, 2026-11-08: "continue with the next batch"). `text.flx` entries
1037–1078, 1454–1618 and 2042–2072: 237 entries, 235 translated, 2 left untranslated on purpose.
No runtime, executable or resource-format change.

# Status

**PASS WITH LIMITATIONS.** validate PASS, tests pass; not yet run in game.

# Environment

HEAD before this batch `79f50fb`. Runtime 0.2.8 (unchanged), font Noto Sans CJK TC 2.004 (local only).

# Work Performed

| Item | Result |
| --- | --- |
| Translation | 235 records as `draft`: Lord British main-quest lines, the Blackthorn duel, Iolo and his ghost, the Shrine of Compassion |
| Left untranslated | 2052 (`mu`) and 2069 (`vas mani corp`): single-entry typed answers. HYPOTHESIS: the game may compare them with player input. Guide §4.6 updated |
| Tool fix | A term found only inside a longer approved term no longer counts as an occurrence (`Shrine` inside `Shrine of Compassion`, `Codex` inside `Codex of Ultimate Wisdom`) for first-occurrence annotation, annotation checks and the untagged-term diagnostic. `glossary.contains_standalone`, with tests |
| Performance | The new check tests the cheap substring match first; validate stays at about 3 s |

# Findings

- CONFIRMED: without the tool fix, validate demanded `美德聖壇(Shrine)` on lines that only name
  `Shrine of Compassion`.
- Address: Avatar to Lord British uses 您 and 陛下 (`my lord`); Lord British to the Avatar uses 你.
- The guide forbids 汝; the shrine's archaic `thou` became 你.

# Tests

- `python -m unittest discover -s tests`: OK, 3 skipped.
- `validate` (development): PASS, 0 errors, 4 layout warnings (3 lines; 4164 already confirmed in
  game at 3 lines), 1 info (two identical Lord British directions share one runtime plan).

# Files Changed

`translation/zh-TW/text.jsonl`, `translation/TRANSLATION_GUIDE.md`, `u9cht/l10n/glossary.py`,
`u9cht/l10n/pipeline.py`, `tests/test_p8a_terms.py`, this report.

# Risks

- Not tested in game. 13 journal lines here will show English (journal path not supported).
- Cutscene speaker labels in the duel are inferred from the text.

# Blockers

None.

# Recommendation

Continue with the remaining Britain townsfolk in batches; run one in-game check after a few batches.
