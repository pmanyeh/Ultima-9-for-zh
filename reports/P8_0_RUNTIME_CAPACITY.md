# Phase

P8-0 — Runtime Capacity (scoped; no translation batch).

# Scope

Raise the native runtime pack limits so broad P8 translation can fit, and test
the combined pack in the game. Authorized by the human on 2026-11-04. P8
translation batches are not authorized. No translations were added or changed.

# Status

**PASS WITH LIMITATIONS.** Capacity, load, prewarm, memory, rollback and clean
exit are verified in the real process at the new limits. The 60-plan combined pack
rendered in human playthroughs with no runtime faults and clean exits. Three
renderer display defects predating P8-0 were found and, on the human's authorization,
fixed in runtime 0.2.8; the human confirmed the fix in game. 27 translated subtitles
remain unobserved.

# Environment

- Starting HEAD `3a351750ff3d5228084917919c4f6f716bc06273`, branch
  `p7-localization-pipeline`; P8-0 work is uncommitted at report time.
- Windows 11 x64, Python 3.12.10, Visual Studio 18 2026 (Win32, Release, /W4 /WX).
- Capacity runs: runtime `U9ChtRuntime/0.2.4-p8-0`, DLL SHA-256 `d0e40368…76b3`, launcher `ffe72d97…c15c`.
- Final: runtime `U9ChtRuntime/0.2.8-p8-0a`, DLL SHA-256 `fc22c7a6c81f59d136e7a82fe9cf9a630f3bb00f7f66c5993523cda15e938c7c`.
- Noto Sans CJK TC 2.004 `dce08bd4…88b4`. P0 baseline assets unchanged.

# Inputs

Canonical store from P7 (unchanged). Private game copy under `.local/`. P6 session
logs for live-buffer and lifecycle peaks. Historical packs under `.local/`.

# Work Performed

| Area | Before | After |
| --- | --- | --- |
| Plans | 64 | 16,384 |
| Glyph scalars | 512 | 8,192 |
| Glyph cache | 1,024 rasters | 16,384 rasters |
| Lifecycle events per snapshot | 4,096 | 16,384 |
| Plan storage | fixed 2.6 KB per plan | sized to each string |
| Text and name lookup | linear scan | sorted hash index |
| Glyph lookup | linear scan | open-addressed table |
| Pack validation | quadratic | sort-based, same rejections |
| Snapshot `entries` | every plan | plans with activity, plus `plans` total |

Unchanged on purpose: pack format (v1/v2/v3), `MaxText` 512, the 512 live-buffer
registry, the 64 raster and 128 queue tables, all hook sites and bytes. `u9.exe`
is not patched.

Pipeline: identical `text.flx` targets now share one plan, keeping the lowest entry
ID, and are reported as `runtime-shared-target` (info). The native loader still
rejects identical text, so the rule lives only in the pack generator. Added
`decode_pack`, `capacity_stress_pack`, `scripts/build_capacity_stress_pack.py`,
`scripts/run_p8_0_session.py`.

# Findings

- CONFIRMED: full-corpus need is 9,422 plans at most: 7,390 editable `text.flx`
  entries (7,212 unique English sources) and 2,032 TYPENAME entries.
- CONFIRMED: the game builds strings on demand. Across six P6 logs live buffers
  peaked at 10 of 512, none at the first snapshot, so the registry does not scale
  with pack size in those scenes.
- CONFIRMED: lifecycle events already peaked at 2,560 of 4,096 in one snapshot
  during one conversation. Overflow quits the game (`fail(27)`), hence the larger buffer.
- STRONG EVIDENCE: writing every plan into each snapshot would log megabytes every
  5 s at full capacity. Sparse snapshots stayed under 1 KB in the idle session.
- CONFIRMED: dynamic plans made the rollback path able to read an empty list. Guarded
  in `snapshot` and exercised with a truncated pack.
- HYPOTHESIS: 8,192 scalars covers the finished translation (not measurable until
  translated). The build refuses a pack that exceeds it.
- UNKNOWN: drawing cost and lifecycle peaks in crowded late-game scenes.

# Evidence

| Measure | 60-plan pack | Full capacity |
| --- | --- | --- |
| Plans / scalars / rasters | 60 / 347 / 694 | 16,384 / 8,192 / 16,384 |
| Load + prewarm in game | 516 ms | 7,047 ms (launcher limit 30 s) |
| Glyph coverage bytes | 582,351 | 14,244,886 |
| Private bytes at 30 s | 515 MiB | 540 MiB |
| Flips in first 30 s | 2,000 | 1,944 |
| Exit via window close | 0 | 0 |
| Hooks restored, font removed | yes | yes |
| Fault counters | 0 | 0 |
| Longest snapshot line | 941 bytes | 951 bytes |
| Runtime vs offline raster hashes | 694 equal | 16,384 equal |

The full-capacity pack is the 60 real plans plus synthetic filler that uses unused
entry IDs and text found in no game resource. It tests capacity only and is not
committed. One 30 s no-input run per pack: the flip difference is not a measured
performance result.

- Combined pack `043795b2…a0ed`, `text.flx` `d4544907…6893`, TYPENAME `7a765bf7…e432`:
  identical to P7, 0 shared targets, mutation audit PASS.
- Python and native rasters: 694 compared, 0 mismatches.
- Six historical pack copies (four distinct, including v1) pass the offline check.
- Truncated pack and text-hash mismatch: `initialization_rollback_verified`, game
  never resumed, launcher exit 2.
- Protected assets match P0 after every session. Saves unchanged.

## Human playthroughs (60-plan pack, 1600x1200, windowed)

| Session | Route | Flips | Composite frames | Newly drawn entries |
| --- | --- | --- | --- | --- |
| `session-play` | existing save | 12,813 | 4,494 | 4030, 4032–4046, 4048, 4050–4052, TYPENAME:5290 |
| `session-opening` | Journal `New Game` | 33,047 | 3,681 | 4170–4173, 4176 |
| `session-fresh` | empty save directory | 18,447 | 1,867 | 4164, 4166–4169, 4175, 4189 |

All three: exit 0, hooks restored, private font removed, 0 fault counters, 0 raster
faults, 0 cache misses, 694 raster hashes equal to offline, assets match P0, saves
unchanged afterwards. Peaks: 10 live buffers, 1 raster, 1 queue, 2,560 lifecycle
events per snapshot, 723,550,208 private bytes. The human reported the `New Game` test
as OK after the empty-save session.

Coverage: 33 of 60 plans drawn (32 `text.flx`, 1 TYPENAME). Never drawn: 4174,
4177–4188, 4190–4203. Entries 4175, 4176 and 4189 were drawn for the first time.

The Journal `New Game` route skipped the tutorial per the human's report, so the
empty-save route is the valid way to test the opening. `--fresh-start` moves saves aside
and restores them with hash verification.

## Renderer defects found (not caused by P8-0), then fixed

`compositor.*` is unchanged since `bb310b4`, and a P6-S2 screenshot shows the same
behaviour.

1. CONFIRMED: Chinese covers the cursor. `compose` runs in the pre-flip hook, after the
   whole frame, so anything drawn later in that frame is painted over. Other UI drawn
   over text should behave the same (HYPOTHESIS, not observed).
2. STRONG EVIDENCE: Chinese has no hover highlight. Chinese skips native glyph drawing,
   so the native style does not reach it. UNKNOWN: whether hover changes font or colour.
3. STRONG EVIDENCE: Chinese option colour is unstable. One colour per raster comes from
   the most frequent bright pixel, falling back to a default. The same menu was purple
   in P6-S2 and orange in P8-0, when an English option shared the raster.

### Fix (authorized by the human; no new hook sites, `u9.exe` not patched)

- Colour and hover: each Chinese glyph takes the colour of the font in use when it is
  queued. The font colour is sampled once per font by running the native glyph blit
  (0x5E20E0) on reference letters into a private copy of the raster descriptor.
  CONFIRMED: hover switches between two fonts, sampled as (173,206,222) and
  (255,230,148). Chinese subtitles therefore render pale silver, not purple.
- Cursor: when a native UI triangle that is not Chinese text overlaps pending Chinese, its
  node raster is read and turned into a mask. At flip, Chinese is not painted under its
  opaque texels. CONFIRMED: the cursor raster is 128x128, 16-bit ARGB1555 (type 2);
  595 of 16,384 texels are opaque. Rasters that are tiled, too large, wrongly sized,
  unreadable or mostly opaque are rejected and counted, so Chinese stays on top of them.

### Rejected attempts (both in this phase, neither kept)

| Runtime | Approach | Result |
| --- | --- | --- |
| 0.2.5 | Mid-frame flush: end scene, compose, restart scene | Game hung (Windows AppHang, exit 0xCFFFFFFF). HYPOTHESIS: native calls made while holding the runtime mutex re-entered a hook. |
| 0.2.6 | Same, with the mutex released around native calls | No hang (717 flushes, exit 0), but text vanished near the cursor. HYPOTHESIS: the game's `ddraw.dll` layer does not keep pixels written by a mid-frame Lock once later draws run. |
| 0.2.7 | Cursor mask with RGB555 colour key | No vanishing; mask rejected because no texel matches the key (all 16,384 counted opaque). |
| 0.2.8 | Cursor mask; first rule leaving 1/256 to 3/5 opaque: key, ARGB1555, ARGB4444, corner value | PASS. |

### Fix sessions (60-plan pack)

| Session | Runtime | Exit | Result |
| --- | --- | --- | --- |
| `session-defects-1` | 0.2.5 | 0xCFFFFFFF | hang |
| `session-defects-2` | 0.2.6 | 0 | text vanished near cursor |
| `session-defects-3` | 0.2.7 | 0 | cursor still under Chinese; hover OK; window switching OK |
| `session-defects-4` | 0.2.8 | 0 | human confirmed all normal |

`session-defects-4`: 10,007 frames, 7,041 composites, 1,349 cursor masks, 0 rejects, 0
skipped frames, 0 lock or unlock failures, 0 fault counters, 694 raster hashes equal to
offline, assets match P0, saves unchanged. After each session the game copy was restored.

New skip-reason counters showed that all 1,631 skipped frames in `session-defects-3` were
device-lost frames while the window lacked focus. That explains earlier whole windows
of skipped composites (for example 1,813 in `session-play`).

# Tests

- `python -m unittest discover -s tests`: 141 run, OK, 0 skipped with local assets set.
- `ctest -C Release`: 6/6 passed. New native cases: full-capacity load and lookup,
  length boundaries, duplicates at capacity, full-capacity glyph table, occlusion
  bounds, font colour sampling, occluder mask rules and masked blending.
- Final runtime 0.2.8: build /W4 /WX clean, ctest 6/6, Python 141/141, offline check
  PASS with all 694 coverage hashes equal to 0.2.6 and 0.2.7.

# Results

Capacity blocker removed for `text.flx` and TYPENAME. In-game rendering on this
runtime: RUNTIME PASS for 33 of 60 plans. The three display defects are fixed in 0.2.8
and confirmed by the human.
Full-capacity rendering: NOT EXECUTED (filler text is never drawn).

# Files Changed

`runtime/` (identity, glyph cache, engine, compositor, version, tests, offline check),
`u9cht/l10n/{runtime_pack,pipeline}.py`, `tests/test_p7_pipeline.py`,
`translation/qa/README.md`, two new scripts, this report and its JSON, Master Plan, README.

# Risks

- Sharing a plan merges evidence counters for those entries. Per-entry runtime
  evidence is not available for them.
- 7 s of startup at the extreme; real packs will be smaller.
- 25 MiB extra private memory at capacity. Base private bytes vary by session and
  reached 690 MiB (723,550,208 bytes) in `session-fresh`, in a 32-bit process.
- Snapshot lines reached 599,695 bytes in the conversation session because of lifecycle
  records, unrelated to plan count.
- One `text.flx` source is 535 units, over `MaxText`. A translation over 512 is refused.
- The cursor mask reads a native raster the runtime does not own, under a fault guard.
  Only the cursor has been observed as a masked occluder. Other native UI drawn over
  Chinese (panels larger than 128 texels, tiled images) still lies under the Chinese.
- English hover text has a dark halo that Chinese hover text does not get.
- Only fonts seen so far were sampled; a font whose reference letters are missing falls
  back to the default colour.

# Blockers

None for the capacity work or the renderer fix. Open before or during P8: BOOKS Unicode
path, misctext adapter, approved
terminology, 27 unobserved subtitles. The earlier TYPENAME single-name exit 1 did not
recur (TYPENAME:5290 drawn with exit 0); its cause remains UNKNOWN.

# Deviations From Master Plan

The Master Plan had no P8-0 section; one was added from the human's authorization.
The unique-target rule from P7 was replaced by plan sharing, with native rejection kept.

# Recommendation

Authorize the first P8 translation batch. The capacity limit and the three display
defects no longer block it.
