# Phase

P6-S2 - Representative Traditional Chinese Gameplay Surfaces PoC, 2026-11-01.

# Scope

Authorized: real NPC dialogue, inventory/equipment names and player-visible item
information. New families require independent inspection, exact round-trip,
single edit and runtime confirmation before a small translated set.
Target1600x1200 windowed; no timed soak, broad translation, full UI replacement,
external overlay or P7/P8 expansion. Historical P5.1/P6-S results remain separate.

# Status

**PASS WITH LIMITATIONS - human-requested checkpoint, stopped2026-11-02.**

**Representative showcase: PARTIAL.** NPC category is complete; one real inventory
name has Chinese runtime proof and human confirmation. The5-10-name inventory
category, Chinese inventory screenshots and readable-item Chinese remain incomplete.
The user explicitly requested stopping PoC work here and committing/pushing.
Initial0.2.0 formal dialogue failed with first_error10. After explicit user
continuation, diagnostic0.2.1 proved multiple response identities share one
native raster. Corrected0.2.2 completes19 selected entries (14 spoken and5
responses), save reload/replay, normal gameplay return and normal exit with
zero faults. Seven images are inspected, including four distinct NPC lines,
two response menus and cleared gameplay. Historical failures remain recorded.

# Environment

- Starting HEAD `60575850a35f44443d76d0f12271e8cc61d6d7a0`, main.
- Windows11 x64; Python3.12.10; Git2.55.0.windows.3.
- Existing MSVC19.51.36252.0/toolset14.51.36231, SDK10.0.26100.0,
  CMake4.3.1-msvc1. No new dependency. Existing Capstone: static reads only.
- TITAN0.7.8/tgwUltima pin `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`.
- Computer Use connected; human assisted sustained movement and sitting.
- NPC acceptance session closed; original private configuration restored.
- Subsequent ASCII probe04 exited normally. Chinese single-name05 is closed
  with exit1 and no runtime cleanup record; its original assets/configuration
  are restored. This is not a successful normal-exit acceptance result.

# Inputs

All five protected assets matched P0 before installation and after restoration.
Assets, screenshots, exports, fonts, builds and saves remain ignored/private.
Nothing is staged. Existing local `.vscode/` is untouched.

| Input | SHA-256 |
| --- | --- |
| English executable | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| Original text.flx | `378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0` |
| Original TYPENAME.FLX | `26c9042d2e8f0f55559c84c22113ae62348ed0694375ad02b4fe65fea9e3f4ca` |
| Original BOOKS-EN.FLX | `a0653ef3608537575e707faa56aca6f24efc2eddaab554d49279d6c1c1a8858b` |
| Original misctext.flx | `3c5bb8845ff101bfba87f38dcb253d81eb9bee6580d18c22a1649179e5e9b570` |
| Existing wrapper | `f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502` |
| Frozen runtime0.2.0-p6s | `da959ad5bfe66a9b1806f1b802479074e07b3f55afcb915647bd46adcafc056d` |
| NPC candidate resource | `1f72ff74dc3876b6cb16525381fa018535ec29d147ce33c6bbb5cef041c12191` |
| NPC allowlist | `7bd4131a96f46f93d6a198a72407ef67983fa7e283ce5cc9105e116249dca0ac` |
| Pinned Noto Sans CJK TC | `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4` |

# Work Performed

1. Read requested rules/authorization/reports/tooling; recorded hashes, versions,
   upstream pin and private backups.
2. Independently decoded TYPENAME and BOOKS. Added separate ASCII-only
   parsers/exporters/importers and tests; shared only validated FLX container
   preservation. Opaque bodies, metadata and unknown bytes remain intact.
3. Both archives pass exact export -> serialized JSON -> import round-trips.
   Actual readable-book content uniquely matched BOOKS-EN:182. A controlled
   single-entry ASCII heading subsequently appeared in that native book.
   Clock information has a separate native executable-format lead.
4. Prepared20 related Gypsy drafts,136 custom scalars/272 rasters. Native/Python
   prewarm hashes match. Launched the unchanged frozen runtime with the NPC
   resource/pack and independent book probe in the ignored runtime copy.
5. Human-assisted traversal reached the Gypsy. Player-initiated interaction
   displayed4030 in Chinese; captured and inspected it.
6. Native Ctrl+S opened the save page. Saved empty slot `p6s2` and backed up
   private files before sitting. Reload/replay subsequently passed in corrected03.
7. Human sitting triggered the introduction/response UI and sudden closure.
   Preserved logs and inspected the guard. First_error10/error_count14; exit0.
   Bounded Windows Application1000/1001 query found no matching event; absence
   alone does not establish a cause.
8. Restored original text/book resources, Options.ini/dxcfg.ini; rechecked all
   five P0 assets, unchanged wrapper and unchanged original keymap.

# Findings

- **CONFIRMED:** independent resource layouts and byte-perfect round-trips.
  See `docs/formats/U9-TYPENAME-NOTES.md` and `U9-BOOKS-NOTES.md`.
- **CONFIRMED:** actual Chinese NPC greeting4030 uses native constructor,
  copy, both widths, raster/queue and final composition.
- **CONFIRMED:** first_error10 is the glyph-dispatch guard for an absent raster
  binding or a plan/identity mismatch. Engine::fail attempts WM_QUIT on the
  first render error.
- **STRONG EVIDENCE:** this guard accounts for the sudden closure. Exit0 is
  not evidence of a successful showcase shutdown.
- **CONFIRMED by later diagnostic:** response rendering is the failing boundary: final
  pre-shutdown lifecycle includes the first4040 response raster;4038/4039 reach
  constructors/widths without the spoken-subtitle copy/queue route.
- **UNKNOWN in initial frozen logs; resolved by diagnostic02:** responses4040,
  4039 and4038 share one161x70 raster in the same paint scope at caller0x5C4E6D.
  See the corrected NPC evidence below and the identity research note.
- **CONFIRMED:** native book182 shows `U9_BOOK_0182`; provenance passes,
  Chinese book rendering does not.
- **STRONG EVIDENCE:** clock format VA0x7A8B3C via0x6551F5/0x624680 is separate.
  Book final Unicode path remains UNKNOWN. The later inventory5290 proof is
  recorded below; it does not establish arbitrary inventory/book support.

# Evidence

| Surface | Resource source | Render path | Translation count | Runtime | Visual evidence |
| --- | --- | --- | ---: | --- | --- |
| NPC conversation | 19 selected text.flx entries reached runtime | Existing14 hooks with scoped shared text runs | 14 spoken +5 responses observed | PASS for this category | 7 inspected images, including4 NPC lines |
| Inventory/equipment | TYPENAME:5290 controlled ASCII provenance, then Chinese marker bridge | Native label copy/destructor plus existing width/raster/final-surface hooks | 1 | PARTIAL:404 composites; final exit1, cleanup unverified | Human confirmed Chinese; no saved Chinese inventory image |
| Item information | BOOKS-EN:182 controlled runtime proof; separate clock lead | Chinese path UNKNOWN | 1 uninstalled draft | ASCII provenance PASS; Chinese NOT EXECUTED | Local discovery/probe |

Private directory: `.local/p6s2/npc-01/`. Captures are1069x826 bounded window
images at configured1600x1200, not1600x1200 exports. Runtime hash: Inputs.

| Filename | Visible resource | Purpose | SHA-256 |
| --- | --- | --- | --- |
| `02-npc-welcome-4030.jpg` | text.flx:4030 | Actual NPC with readable Chinese; no visible clipping/boxes | `47c2950033e7c801dff4736015ea93b96e682b4da2c63b3c53afd220015744e3` |
| `01-book182-ascii-probe.jpg` | BOOKS-EN:182 | Native controlled ASCII heading; excluded from Chinese count | `3f5450dcac21587fb137b1bb38d822133c8af6767c83f718026935b7c66d1527` |

Runtime log SHA-256:
`7a16af623464493389599be95edecfb5ba139ddc1462a97a251e2690dca55e4c`.
Private incident receipt: `incident-01.json`; raw copies: `incident-01/`.
Counters show composites for4030/4032/4033/4037 only; the last three have no
individually inspected image and are not counted as visual evidence.
898 skipped composites remain uncorrelated to the guard.

# Tests

```powershell
$env:U9_GAME_DIR = (Resolve-Path '.local/p6s2/backup').Path
python -m unittest discover -s tests -q
```

**102/102 PASS,0 skipped** at final checkpoint, including independent resource
families, v3 pack namespaces, marker mutation scope and malformed inputs.
Frozen native CTest suite rerun: **5/5 PASS,0 failures**.
Candidate native/Python prewarm: **272/272 coverage hashes match**.
Offline tests do not certify the failed formal NPC runtime path.
Closed-session verifier: **REJECTED, exit1**, at the zero-error assertion.
Its diagnostic is private under `npc-01/incident-01/closed-verifier.txt`;
the validator was not weakened to accept the guard exit.

Book182 draft preserves CRLF/page-marker sequence. Font coverage passes for85
custom scalars and the190-scalar NPC-plus-book union (380 rasters). This is not
the final combined corpus and was not installed as Chinese book text.
The ASCII-only book writer still rejects unverified Unicode storage.

# Results

- TYPENAME: BYTE-PERFECT PASS,134200 bytes,0 differences.
- BOOKS-EN: BYTE-PERFECT PASS,221316 bytes,0 differences.
- Book182 ASCII single edit: RUNTIME PASS,221305 bytes; hash
  `3dfb9e1ade6211f3fbf46e15f6edd71d38c74b33f85faf1f4e537bfdc1f5b073`.
- Clock2607 ASCII probe prepared privately; not installed/runtime-tested.
- Initial formal NPC runtime: FAIL. Guard exit0 does not satisfy normal successful exit.
- Corrected0.2.2 NPC runtime: PASS, zero errors; native quit/exit0 and cleanup verified.
- That NPC session reports14 hooks restored, active_calls0, font removed, worker handles
  closed and empty live buffer/raster/queue domains.
- All five assets match P0 after restoration. Options.ini/dxcfg.ini restored
  byte for byte; Default.kmp/wrapper unchanged. Savepoint preserved.
- Single-name0.2.3: actual5290 Chinese reached final composition404 times and
  all four label/raster/queue lifetimes retired naturally. Exit1 has no cleanup
  record; this separate session does not pass normal-exit acceptance.

# Files Changed

Separate typename/books parsers, shared container helper, tests, format/cursor
notes, Gypsy/inventory/readable-book draft stores, v3 combined NPC/name builder,
scoped runtime extensions, this report/JSON and master checkpoint.
No game archive, font, screenshot, binary, dump or absolute local path is staged
or published. The original frozen binary is unchanged. Native source now contains the scoped
0.2.2 shared-run correction, bounded diagnostics and0.2.3 optional name routing.

# Risks

The earlier subtitle/greeting route could not be generalized to response objects
without the measured shared-raster correction.
Removing identity checks could conceal stale glyph placement. ASCII provenance
does not prove inventory/book Unicode support. The savepoint reload is verified
for the corrected NPC session.
The final single-name session ended with exit1 for an unknown reason despite
zero recorded hook errors; shutdown hook/font/worker cleanup is not established.

# Blockers

The complete inventory corpus/screenshots, readable-item Unicode path and full
three-category prewarm remain unexecuted. The selected NPC-plus-one-name union
was prewarmed, but excludes the uninstalled book draft. NPC first_error10 is
resolved by0.2.2; this does not establish arbitrary UI/book support. Native cursor
confinement remains unresolved; see `docs/research/U9_WINDOWED_CURSOR.md`.

# Deviations From Master Plan

Explicit P6-S2 authorization permits representative surfaces before full P6/P7.
The runtime failure activated mandatory stop conditions. Work stopped and was
reported; explicit user continuation then permitted bounded diagnosis and the
measured correction. No broader phase or blind guard bypass followed.

# Recommendation

Stop at this checkpoint as explicitly requested2026-11-02. Preserve the source,
tests and evidence metadata for review; do not resume inventory expansion,
book routing or P7/P8 without a subsequent request. Before claiming a complete
inventory category, resolve/verify the latest exit and obtain its missing evidence.

## Corrected NPC evidence and verification

See `docs/research/P6S2_DIALOGUE_IDENTITY.md` for the measured shared-raster
contract. No new hook site or on-disk executable patch. Native6/6 and Python98/98
pass. The corrected run reloaded the private save and replayed the introduction;
all selected spoken lines complete their natural visible raster lifetimes.

Runtime0.2.2 SHA-256:
`f844f26b513ac5504ccf4067e33f2cd2f88829b3e4c7621fcef0c609331566e4`.
Closed log SHA-256:
`a7c600b55a88c374f5b909dd3d92e6c10536a5be23c62a44311157b45e2e49be`.
Private session: `.local/p6s2/npc-fixed-03/`; configured1600x1200,
bounded1069x826 captures. Native direct screenshot shortcut was attempted but
no TGA was found beneath the private game tree; no full-resolution export claim.

| Filename | Visible entries | SHA-256 |
| --- | --- | --- |
| `01-response-menu-4038-4040.jpg` | 4040,4039,4038 | `717e3ae7545a2340f7c43bb829d490ad08b6da0c23daf91384bf8727242ad12a` |
| `02-gypsy-4041.jpg` | 4041 | `99fcd6927652bb702f9bdb62077e2ab9ae18a97e3e004f23af0f6e2878a797cc` |
| `03-gypsy-4042.jpg` | 4042 | `f085cfb48415e50ba3f150c11ab99efd2e5123caa9d61a37aadd53541b5e855f` |
| `04-gypsy-4044.jpg` | 4044 | `d71fdc0cd4a457da8a442919cb34c61d2b5e0ed9b82949b43995b64c4d13509d` |
| `05-second-menu-4046-4048.jpg` | 4048,4046 | `688d13d9d834d38b2eb969ec7db756358a7aafc226a1f038a98833630b494510` |
| `06-return-to-gameplay.jpg` | normal gameplay; no subtitle | `c6672a24266434ead1d23a872b31d64c6d7a84b8b23392cff7f54c486ce0ad63` |
| `07-gypsy-multiline-4052.jpg` | 4052 | `8452d45f80e8ab8ea141ea6b0a133f7abe7821611f8cb1e8bb8072a016153dee` |

Four distinct NPC images show4041/4042/4044/4052, native Britannia, punctuation,
authored LF and no visible clipping/boxes/stale subtitles. Some branch choices
and the acknowledgment remain native English; no full-dialogue/UI translation
claim. The response menus display multiple Chinese strings in one native raster.

`python .local/p6s2/verify_npc03.py` - PASS:19 composited entries,272 prewarmed
raster hashes,52850 ordered lifecycle events,4464 shared-raster groups, each
run inherited from a live source, natural retirement, empty live domains and
normal exit0. All14 hooks/font/workers cleaned; all five P0 assets/config restored.
An initial verification was invoked before asynchronous quit completed and
rejected the unfinished log. Rerunning after the exit record passed unchanged.
The earlier failed sessions remain FAIL and are not reclassified by this result.

## Inventory probe continuation

`typename-probe-04` uses the same0.2.2 binaries in inert bootstrap mode.
Only TYPENAME5290 is changed to `U9_FIRSTAID_5290`; modified archive SHA-256
`7285f08e58689c8a7907a5ca5ba24fd08099aa746cf4211310bff8b81dc0916c`.
The audit preserves all other payloads and unknown bytes. Text/books are
original and no Unicode render hooks are enabled. A real white first-aid object
was dragged from the belt into the backpack. Held-X examination then displayed
the exact marker and confirmed5290 through native label/width/raster/queue
tracing. A preceding brief X press with no hits was inconclusive.
Source probe04 exited natively with exit0 and was restored. Details and the
ASCII screenshot hash are in `docs/research/P6S2_INVENTORY_LABEL_PATH.md`.

## Final single-name checkpoint -2026-11-02

Runtime0.2.3 SHA-256
`532ef1c916ceac215eb98cc03c5f2ada0b5ca4411cd4f9bb2a8a9e9f715a839f`;
launcher `283130c7c7b8a890656dd84f28a8b2b5bbcdfd639c42e4c91e6e9674f4732414`.
Packv3 binds NPC text SHA-256 from Inputs and modified TYPENAME SHA-256
`7a765bf78a8dd6c9fd7812bb2c347208a5ae1e04d8eea8e6152b64aab606e432`.
Allowlist `54b07a817f6d2320b758bde77fcb5cc0a43ea8f35b57333039ebb86aa8b9f49c`.
Only5290 is changed in TYPENAME, to ASCII marker `U9T14AA`; Unicode target
`急救箱` remains a distinct immutable plan. Item ID namespace is0x10000000|5290.
The two optional name hook sites are reviewed in the inventory research note.

Python102/102 and native6/6 pass. NPC-plus-name coverage is138 custom scalars,
276 prewarmed20/40px rasters;276/276 native/Python coverage hashes match.
READY precedes resume;16 hooks installed, no debugger required. Name counters:
four native copies/frees,12 bounds overrides,12 CJK dispatches, four48x20
rasters/queues,8178 submissions/presentations and404 final composites. All four
name buffer/raster/queue generations retired naturally before process ending.
Recorded errors/first_error/Lock failures/Unlock failures/lifecycle drops are0;
last live domains are0 and cache remains276. The38004 skipped composites are
not fully correlated and are not promoted to a focus/device-recovery PASS.

The human confirmed seeing the Chinese first-aid label. No Chinese inventory
screenshot was saved before closure, so there is no new image hash or claimed
equipment screen. This proves one actual item name, not the5-10-name category.
The process has already ended: exit1, no runtime_hooks_restored/runtime_cleanup
records. Cause is UNKNOWN; it is not classified as normal successful exit.
The earlier NPC exit0 result remains independently valid.

Closed log SHA-256
`fd68fd3a1f8afec57d1f7d1e9dd632b8d8942b5f537439afece5019a4e5c103d`.
Private session `.local/p6s2/inventory-single-05/`; verification receipt preserves
the positive render/lifetime observations and rejects normal-exit acceptance.
After confirming the process ended, all five protected assets and original
Options.ini/dxcfg.ini/Default.kmp were restored and verified. No restart,
additional translation, screenshot request or timed-soak acceptance followed
the user's instruction to stop PoC work and commit/push.
