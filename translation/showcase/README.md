# Frozen P6 showcase snapshots

These JSON files are **historical evidence** for P6-S and P6-S2. They are
frozen as of P7 (2026-11-03) and must not be edited:
`tests/test_p7_pipeline.py` checks their LF-normalized SHA-256 against
`u9cht/l10n/migrate.py:FROZEN_SHA256`.

The single editable source of truth is `translation/zh-TW/*.jsonl`. These
snapshots were migrated into it deterministically
(`python scripts/migrate_showcase_store.py --check`). The canonical pipeline
rebuilds the historical P6 resources and runtime packs byte-for-byte (see
`reports/P7_LOCALIZATION_PIPELINE.md`).

The legacy builders `scripts/build_p6s_showcase.py` and
`scripts/build_p6s2_inventory.py` still read these snapshots, so the historical
evidence stays reproducible. Production builds use
`scripts/build_localization.py`.
