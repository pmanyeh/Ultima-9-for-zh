# Phase

P6-S — Traditional Chinese Showcase PoC, 2026-11-01.

# Scope

Explicit authorization permits a windowed showcase despite P5.1 limitations.
Only Hawkwind's Earth-home/outdoor tutorial in `text.flx` is selected. No books,
inventory names, journals, menus, other archives, full P6/P7/P8, installer or
timed soak. P5.1 is not retrospectively passed.

# Status

**PASS WITH LIMITATIONS — runtime/cleanup pass for the opening subset.**

**Showcase classification: PARTIAL. Full selected-scene coverage remains incomplete.**
Computer Use connected successfully in this continuation. The unchanged frozen
0.2.0-p6s build ran with the audited resource at configured1600x1200 windowed.
Native diagnostics prove9 different entries composited;6 have individually
inspected screenshots. Normal exit and all cleanup/restoration checks PASS.
Entries4174–4203 were not triggered. This is no longer an offline-only checkpoint,
but9/39 coverage does not complete the substantial selected-scene objective.

# Environment

- Starting HEAD `3a2c8b874882d33bf9091cda9c390f29175c8f3e`, main.
- Windows11 x64 / Win32 runtime; MSVC19.51.36252.0/toolset14.51.36231,
  SDK10.0.26100.0, CMake4.3.1-msvc1; C++20, static CRT, `/W4 /WX`.
- Python3.12.10, Git2.55.0.windows.3. No new dependencies.
- TITAN0.7.8/tgwUltima pin `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`.
- Existing optional Capstone used for bounded static inspection only.

# Inputs

All five protected game files match `reports/P0_HASHES.json`.

| Input | SHA-256 |
| --- | --- |
| English executable | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| Pristine text.flx | `378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0` |
| Existing wrapper | `f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502` |
| Noto Sans CJK TC Regular | `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4` |
| Showcase resource | `71eea15597f45a1cfb280a5bab1239665cf1f14cc53f7968a6327e02f7de4d47` |
| Showcase allowlist | `3163a669749dc94ad7573bf3b2dd7cdedbac9648c64e9c374a0412bd3ff4d1dd` |
| Runtime0.2.0-p6s | `da959ad5bfe66a9b1806f1b802479074e07b3f55afcb915647bd46adcafc056d` |
| Matching launcher | `932faf079916633243f27620c85056db0f6332e86a5172502d9832451c5ed25a` |

Font version2.004, upstream `165c01b46ea533872e002e0785ff17e44f6d97d8`,
SIL OFL1.1, unchanged from P5. Font/binaries remain private; prior P5.1 binaries
and evidence remain separate.

# Work Performed

1. Read the seven requested documents and rechecked Git, ignored assets,
   dependency versions, upstream pin and baseline hashes.
2. Selected **4164 and4166–4203 inclusive:39 entries** from the private source.
   This covers the bedroom, preparation and outdoor movement/combat/swimming
   tutorial.4165 is a journal summary;4204 starts Stonegate;4216 starts historical
   narration. Those are excluded. Ordering establishes candidate grouping, not
   runtime execution order: some tutorials are conditional or alternate reminders.
3. Wrote Taiwan Traditional Chinese targets with `showcase-draft`, source UTF-16
   hashes/lengths, speaker/context and explicit unobserved-runtime flags. Avatar,
   Guardian, Britannia, Lord British and Ankh retain English pending terminology
   review. No official translation claim; full English source stays private.
4. Collected **288 custom scalars:283 Han plus five punctuation characters**.
   All have actual glyphs in the pinned font. The version-2 pack contains an exact
   sorted glyph list, maximum64 plans/512 BMP scalars/512 UTF-16 units per plan.
   Historical v1 retains16 plans and its original two-glyph restrictions.
5. Expanded the fixed CPU cache to1024 entries; the scene uses576, one direct
   20px/40px raster per scalar. Prewarm occurs before hooks/READY. No GDI/file I/O
   was added inside Lock. Font bytes/selected face remain hash-checked.
6. Both width consumers and suppressed CJK draw use per-character advances from
   scalable-font measurements. All selected glyphs empirically have20/40px
   advances, exactly16 engine logical units at both scales. That equality is not
   assumed for arbitrary characters. Latin remains native.
7. Authored one LF in each of15 entries, preferring clause boundaries. CJK widths
   are measured; ASCII has a conservative16-unit per-character authoring budget,
   **not measured native metrics**. Maximum line budget528 logical units is below
   the previously observed595-unit raster width. Wrapping/clipping is now visually confirmed only for
   the captured subset; remaining lines need runtime confirmation. No full Unicode line-breaking implementation.
8. Rebuilt from pristine data. Exactly39 selected payloads change; all unselected
   payloads, unknown padding/header bytes and slot count are preserved. Known
   size fields and offsets relocate as required. The resource was not installed at the offline checkpoint; this continuation
   installed it only in the ignored private runtime copy, then restored it.
9. Built runtime0.2.0-p6s using the same14 reviewed hook sites. The offline checker
   exercises actual native font/cache initialization, reuse and font removal
   without launching or attaching to the game.
10. Current continuation: verified Computer Use inventory, baseline/build/font/pack
    hashes and private backups; reran86 Python and5 native tests. No rebuild or
    translation/renderer changes. Ran the normal launcher, observed the opening,
    clicked the Ankh and exercised native clock/door/UI/jump interactions.
11. Captured6 subtitle images; attempted later traversal with discrete input but
    did not reach the remaining triggers. Exited through native Ctrl+X/OKAY;
    verified cleanup, exit0, natural subtitle retirement and byte-for-byte restore.

# Findings

- **CONFIRMED:** source grouping,39 drafts,288 custom scalars, font coverage,
  exact advances, scoped mutation,576 CPU rasters/cache reuse/offline font cleanup.
- **CONFIRMED:** all576 native coverage hashes equal Python GDI output.
- **STRONG EVIDENCE:** static painter LF dispatch through0x5C5D9A reaches
  0x5C5C43, resetting x/advancing y; bounds LF dispatch through0x5C5FD2 reaches
  skip branch0x5C5E99. This supports LF transport, not visual subtitle geometry.
- **CONFIRMED:** log-based composition of4164,4166–4173, totaling2560 frames;
  all9 completed copy/both-width/raster/queue routes and natural retirement.
- **CONFIRMED:** captures4164/4166/4167/4170/4172/4173 show readable Traditional
  Chinese, correct authored LF, punctuation and intact native Latin. No visible
  clipping, boxes, duplicates or stale prior subtitles in those captures.
- **CONFIRMED:** fixed576 cache entries,75110 hits,576 warm-up misses and no
  in-session misses; all576 prewarmed hashes match the offline reference.
- **CONFIRMED:** native normal exit0, active_calls0, restored14 hooks/pointers,
  private font removal, closed worker handles and empty live metadata.
- **UNKNOWN:** actual trigger order/visual layout for4174–4203. Log composition
  for4168/4169/4171 is not individual screenshot inspection. No actual layout
  defect was found, and no speculative layout change was made.

# Evidence

Private `.local/p6s/` retains the frozen build/pack/offline evidence. Current
session receipts, raw JSONL, repeatable private verifier and restoration hashes
are under `.local/p6s/session-01/`. No game image or asset is tracked.

Runtime JSONL SHA-256: `7bd768e23207e1ab7e2ee00ed528b4766d49b15a9b5e8d565d0db03eb802749b`.

Screenshot index: **6 captured and visually inspected**. Every row uses runtime
`da959ad5bfe66a9b1806f1b802479074e07b3f55afcb915647bd46adcafc056d`.
Configured game output is1600x1200 windowed; Computer Use bounded captures are
**1069x826**, including window chrome. These PNGs are not1600x1200 pixel exports.
The runtime independently validates supported backend/surface dimensions.

| Filename (private session directory) | Visible entry | Description | SHA-256 |
| --- | --- | --- | --- |
| `01-opening-4164.png` | 4164 | Opening: two authored lines, native Avatar/Guardian/Britannia/Lord British and Traditional Chinese. | `d39f6d11b9ce872f127e21e4e4854e7e6c3c892da52cce68aee154cd7743756e` |
| `02-movement-4166.png` | 4166 | Long single-line Chinese movement tutorial with punctuation; no clipping. | `1a9ffb4ae54fbba8bc6bc8020186fcd8a1ceed98070fb8055b9318b95dd2cfc4` |
| `03-interaction-4167.png` | 4167 | Two complete Chinese lines with authored LF and comma; continuous replacement of opening subtitle. | `459d8138ee5381c80541f0b2fc6b4109e60e3bf73b07e35b684c64c5d3ae8339` |
| `04-preparation-4170.png` | 4170 | Ankh interaction triggers new preparation subtitle; single Chinese line. | `1a2ad26919325ab5124cf86908cbda7bf1c7b3e06e9c410ff25c114aabe16434` |
| `05-light-switch-4172.png` | 4172 | Two-line light-switch instructions with punctuation and no orphaned marks. | `76f89666d741d645f6c230533c63a26cbddff0ae2fd1efcc36da6962244cb130` |
| `06-items-4173.png` | 4173 | Next distinct subtitle following light-switch instructions; room lighting changed normally. | `44698257fe99a13219d48b3c37b8bd74d6d9318430b984129702fe0b38aab237` |

The native quit dialog is retained separately as `normal-exit-dialog.png`.
Screenshot-time counter anchors are in private `screenshots.json`; actual
visible IDs were identified from inspected text, not inferred from counters.

# Tests

Original offline build/check commands (historical; binaries were reused unchanged
in this continuation):

```powershell
$env:U9_GAME_DIR = (Resolve-Path '.local/runtime-game').Path
python -m unittest discover -s tests -q
cmake -S runtime -B .local/p6s/build -A Win32
cmake --build .local/p6s/build --config Release
ctest --test-dir .local/p6s/build -C Release --output-on-failure
.local/p6s/build/Release/U9ChtShowcaseCheck.exe .local/p6s/pack-final/allowlist.u9ct .local/p5-highres/font/NotoSansCJKtc-Regular.otf .local/p6s/native-prewarm-final.jsonl
```

- **Python86/86 PASS,0 skipped**, retaining all78 earlier tests.
- **Native5/5 PASS,0 failures**, including extended v2 malformed-pack/metric cases.
- **Offline PASS:**39 plans,288 scalars,576/1024 fixed entries, stable cache reuse,
  576/576 native/Python raster hash agreement and private font removed.
- An initial capacity fixture included a Simplified character rejected before
  the intended capacity check. Changed the synthetic fixture to disjoint
  Extension-A characters; no validator was weakened. Final full suite passes. A separate synthetic test verifies exact translation-store SHA receipts with CRLF and LF authoring outputs.
- Continuation rerun: **Python86/86 PASS,0 skipped; native5/5 PASS,0 failures**.
  `ctest` was absent from this shell PATH; invoked the existing build cache's
  `CMAKE_CTEST_COMMAND` directly. The frozen binaries were not rebuilt.
- `python .local/p6s/session-01/verify-runtime.py` — PASS for the9-entry subset:
  exact hashes/protocol/READY order,576 glyph hashes,82 sequential lifecycle
  events, copy inheritance, counter agreement, natural retirement, stable cache,
  zero faults, complete cleanup and exit0. It is not a P5.1 gate reassessment.
- Restoration receipt: all5 P0 assets match; `Options.ini`, `dxcfg.ini` and
  pristine `text.flx` restored byte-for-byte; wrapper/frozen builds unchanged.
- The first private verifier run incorrectly expected the offline reference's
  event to be named `glyph_cache_warm`; it is `offline_glyph`. Corrected the
  reader to compare the reference's actual advance/hash fields. No runtime
  defect or changed acceptance threshold was involved.
- Simplified-form detection is a small diagnostic list, not exhaustive detection
  or automatic conversion. No time-based acceptance tests.

# Results

**RUNTIME PASS for the observed9-entry opening subset.** Native composition
covers4164 and4166–4173;6 individual subtitles have visual evidence. The opening
and first Ankh tutorial run continuously with Chinese, native Latin and authored
multiline text. No demonstrated layout failure required a fix.

**Normal exit/cleanup PASS:** Ctrl+X → native OKAY, process exit0,14 hooks/pointers
restored at active_calls0, private font removed, worker handles closed,82 valid
lifecycle events and all binding domains empty. All9 subtitle rasters/queues
retired naturally before shutdown. No game/launcher remains open.

**Full P6-S remains PARTIAL:**30 selected entries4174–4203 were not reached;
the complete home/outdoor sequence is not certified. Short key/click actions
and native jump/door interaction did not reliably complete subsequent traversal.
This is an input/traversal limitation, not an established renderer failure.

Pristine source round-trip remains BYTE-PERFECT PASS. Showcase mutation remains
an intentional audited39-entry change; runtime loading is now demonstrated for
the observed subset. Private resources/configurations were restored from verified
backups, all5 protected assets match P0, and original installation was not written.
Session duration459078ms is diagnostic only; no timed soak was performed.

# Files Changed

- `translation/showcase/opening.zh-TW.json` — targets/IDs/source hashes.
- `u9cht/showcase.py`, `scripts/build_p6s_showcase.py`, `tests/test_showcase.py`.
- Native bounded pack/cache/advance/version expansion and extended tests;
  `runtime/tools/showcase_check.cpp` for offline checks.
- Report/JSON, Master Plan P6-S checkpoint and runtime README.
- This continuation changes only those4 documentation files. Private session
  screenshots, logs, receipts and scripts are ignored; earlier code/translation
  changes remain intact.
- No archive, English dump, font, screenshot, binary or real machine path.

# Risks

Conditional triggers mean39 translated entries need not all appear in one run.
Names need terminology review. Authored LF and native Latin are visually
confirmed in the captured subset; remaining native layout/height needs inspection.
This is bounded BMP support, not arbitrary
Unicode, complete P6 typography or release readiness.

# Blockers

The native-pipe connection blocker is **resolved** in this conversation. No
renderer/layout blocker was observed. Current incomplete requirement: traversal
and visual inspection of4174–4203. The available `sky` input surface exposes
short clicks/key presses without an explicit sustained right-button/key hold;
this run could capture/interact/jump/quit but did not reliably reach later events.
Further native gameplay traversal (potentially human-assisted) is still needed.
No new phase authorization is needed to resume this same P6-S scope.

Historical recovery evidence is preserved in the companion JSON and ignored
`.local/p6s/control-diagnosis.json`/`resume-precheck.json`. Earlier inventories
failed with native-pipe os error2, including fresh JS kernels/unified inventory.
After the desktop app setup and this fresh conversation, inventory, target-window
capture and input all worked. No pipe identifier or host configuration was edited.
P5.1 fullscreen/replay remain separate limitations and do not block this lane.

# Deviations From Master Plan

Current explicit authorization creates P6-S despite incomplete P5.1 and permits
authored breaks/bounded glyphs. No historical gate is reclassified. The requested
5–10 screenshot count and normal exit are complete, while actual full-scene
coverage is explicitly incomplete. No timed soak, P7/P8 work or renderer expansion
was performed during this continuation.

# Recommendation

Continue the existing P6-S authorization with the same frozen build and private
pack; exercise4174–4203 through normal native gameplay and inspect remaining
layout/coverage. Human-assisted sustained movement may be needed with the current
input API. Preserve the6 captured examples and verified clean exit as completed
evidence. Do not mark the full showcase PASS or advance to P7/P8 yet.
