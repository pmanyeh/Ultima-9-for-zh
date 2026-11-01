# Phase

P5.1 ? Persistent High-Resolution Unicode Renderer Integration,2026-10-31?2026-11-01.

# Scope

P5.1 only. Starting HEAD `de789311e92f437060aef6d76ca3a6908a5b07d6`;
implementation checkpoint `3a99b45`. P0?P5 findings remain established. P6,
wrapping/typography, other resource families and translation coverage are excluded.

# Status

**PASS WITH LIMITATIONS. P5.1 gate is NOT fully passed.**

Current continuation (2026-11-01):the user replaced time-based soak with the
event-driven gate in `docs/architecture/P5_1_EVENT_VALIDATION.md`. Reassessment
is IN PROGRESS. Frozen0.1.1 completed the800x600 short cycle with normal exit0,
2339 custom frames, full hook/font/handle cleanup and naturally retired bindings.
The1600x1200 cycle and fullscreen smoke are pending completion. Current automated
regression is78/78 Python and5/5 native PASS. The earlier interruption below is
historical and is not retrospectively promoted to a clean exit or soak PASS.

At the earlier checkpoint, the user explicitly requested skipping remaining runtime tests. The approximate
60-minute session, complete final-build repetition matrix, fullscreen and final-build
normal exit are **DEFERRED BY USER**, not PASS. Gate criteria remain unchanged.
No additional game tests were launched after that instruction. P6 is unauthorized.

# Environment

Windows11 x64 host; MSVC19.51.36252.0/toolset14.51.36231, SDK10.0.26100.0,
CMake4.3.1-msvc1; C++20 Release Win32/static CRT. Python3.12.10,
Git2.55.0.windows.3. Existing Windows SDK/tools only; no added hook/font framework.
Existing TITAN/JP pins are unchanged.

# Inputs

English executable SHA-256:
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`.
Wrapper:`f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502`.
Pristine text:`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.
Six-entry private test resource:
`138495860ff5804b19b9f413a2b6416fd5345e1adab7d8bd5dcb7f3353359842`.
Font/file/selected-face SHA-256:
`dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4`.

Frozen0.1.1 DLL:`2e893bda781860455eacc33099ca0c9a334021d59c8880b728cabc4314e89b72`;
launcher:`a5a111f679b412a0288eb3740eacb2619098630ab8a9190b9098c75d3b1e5790`.
Compiled files, fonts, resources, allowlists and screenshots stay ignored/local.

# Work Performed

Added the x86 launcher/DLL,8240-byte protocol, baseline/module validation and
READY/FAIL before primary resume. Observe equivalence passed before enabling14
reviewed persistent boundaries. No debugger, debug registers, breakpoints, manual
EIP, external per-frame memory access or on-disk executable patch is required.

Implemented multi-identity generations, verified full-copy inheritance, overwrite/
free/repaint invalidation, both width consumers, stable TLS metrics and selected
CJK glyph suppression. Native ASCII delegates unchanged. Prewarmed private GDI
gray8 cache:4 current entries, capacity64, exact20/40em keys. Frames support64
queue records/512 commands, deduplication and reset after Flip. Each applicable
frame validates/locks the current backbuffer, clips/blends while preserving X,
and unlocks before Flip. No retained pixel pointer or own heap/GDI/logging in
Lock. Worker disk I/O is excluded from that interval. Implemented surface
revalidation, bounded lifecycle diagnostics and quiescent shutdown; live hot-unload
is refused. Exact hook ABI/bytes/rollback are in the architecture documents.

# Findings

**CONFIRMED:** normal no-debugger startup; five-entry observer equivalence;
continuous800?600/1600?1200 rendering; six explicitly selected subtitle identities;
actual20/40em GDI coverage; cache reuse; full initialization rollback.

**CONFIRMED captured0.1.1 window:**1375.203 seconds,3832 custom frames, errors0,
cache4, hits7560/misses4 (warm-up), dropped events0, Lock/Unlock failures0.
Last collected live buffer/raster/queue counts all0. Conservative actual-composition
activity span1035.141 seconds exceeds15 minutes. Trace verified5 raster-address
and8 queue-address reuses. Buffer reuse was not observed here; the shared native
registry tests explicitly cover it. These are bounded observations.

**UNKNOWN/DEFERRED:** approximate60-minute stability, complete final repetition
matrix, fullscreen, genuine device-lost HRESULT and0.1.1 normal exit. Focus/
minimize/generation recovery was observed; it does not establish an actual device
reset. Native rest/awake and ankh interactions completed in development; native
UI dialogs opened/cancelled during the fixed run.

# Evidence

Private log hashes and per-entry counts/lifetimes are in the companion JSON.
Under `.local/p5-1/evidence/`:

- `bootstrap-normal-01.jsonl`, `bootstrap-unload-01.jsonl`:native scenes/exit0.
- `observe-normal-01.jsonl`:117.203s,13 hooks, five lifecycles, exit0; originals restored at active_calls0.
- `render-800-02.jsonl`, `render-800-03.jsonl`:development1774/2263 custom frames, exits0; second recovered across3 surface generations.
- `render-1600-01-soak.jsonl`:6.4-minute development run,1853 custom frames, six entries, exit0. Filename does NOT mean soak PASS.
- `final-force-01.jsonl`:0.1.1 installs14 hooks/font, forced FAIL, complete restoration/removal/unload/allocation release before primary resume.
- `final-malformed-01.jsonl`:invalid allowlist rejects before hooks, safe rollback.
- `final-1600-01-soak.jsonl`:user-interrupted0.1.1 run; NOT clean-exit/60-minute PASS.

Private screenshots include `P5_1_800_SINGLE.png`, `P5_1_800_FOCUS_RECOVER.png`,
`P5_1_1600_MIXED.png`, `P5_1_FINAL_1600_MIXED.png`. None are published.

# Tests

Completed before the runtime deferral:

```powershell
cmake -S runtime -B .local/p5-1/build -G "Visual Studio 18 2026" -A Win32
cmake --build .local/p5-1/build --config Release
ctest --test-dir .local/p5-1/build -C Release --output-on-failure
python -m unittest discover -s tests -q
```

Build PASS /W4 /WX. Native CTest **5/5 PASS,0 failed**:loader/primary isolation,
detours/gateways/concurrent restore, identities/strict malformed-input rejection,
actual pixel/Lock failure helper, clipping/X preservation/cache lookup keys and
quiescent lifecycle shutdown. Python **72/72 PASS,0 skipped**:original65 retained
plus7 synthetic verifier tests. Local integration uses a private pristine archive.
No expectations were weakened. Forced initialization/malformed-input launchers
exit1 intentionally without primary resume and with verified rollback.

# Results

| Requirement | Result |
| --- | --- |
| Launcher/no debugger/automatic hooks | PASS |
| Initialization rollback | PASS, including14 hooks/private font |
| Identity/copies/both widths | FUNCTIONAL PASS |
| Multiple entries | PASS:4164/4166/4167/4168/4169/4170 |
| 800?600 direct20em | Development PASS; final-build rerun deferred |
| 1600?1200 direct40em | FUNCTIONAL PASS, fixed0.1.1 captured window |
| Native Latin/cache reuse/frame reset | FUNCTIONAL PASS |
| Focus/minimize | Recovery observed; no actual lost HRESULT |
| Fullscreen | DEFERRED BY USER |
| 15-minute activity | Bounded PASS:1035.141s conservative span |
| Three final cycles per resolution | DEFERRED BY USER |
| Approximately60-minute session | DEFERRED; interrupted at approximately23min |
| Clean exit | Development PASS; fixed build unverified |
| Regression | Python72/72; native5/5 PASS |
| Complete P5.1 gate / P6 | NOT PASSED / NOT AUTHORIZED |

Pristine text round-trip remains BYTE-PERFECT PASS in the retained local test.
Six-entry mutation is an audited intentional test resource, not a byte-perfect
round-trip. All five protected assets now match P0, wrapper unchanged, original
Options.ini/dxcfg.ini restored byte-for-byte. No persistent executable change.

# Files Changed

`runtime/`; native/synthetic tests; test-pack builder/evidence verifier; P5.1
architecture/hook manifest/report/JSON; README/Master Plan status; native build
ignore rules. No assets/fonts/screenshots/generated binaries/local absolute paths.

# Risks

Bounded corpus supports U+4E2D/U+6587 and two output sizes. Unknown text stays
native; unsupported conditions fail closed. Multiple same-frame commands are
synthetically tested; natural subtitle observation reached one active record.
No arbitrary-Unicode release or safe live hot-unload is claimed. Process memory
also includes native game allocations and alone cannot rule out every leak.

# Blockers

Remaining validation was explicitly deferred. Desktop recovery alternated between
`window is minimized` and `user input was detected`. Only the agent-created PID
was stopped after exact executable-path verification; exit0xffffffff is intentional
termination, not an inferred game exception. This session does NOT verify0.1.1
normal hook restoration. OS teardown reclaimed process resources before file
restoration. Earlier clean development exits/startup rollback remain separate.

# Deviations From Master Plan

Explicit P5.1 authorization permits the own DLL/minimal hooks. Later user deferral
stops tests without changing gate criteria. Disproven integration assumptions:
Toolhelp before loader initialization; an extra dereference of the proven
root+0xC inner interface. Both are documented; the latter caused a controlled
pre-Lock quit before correction. No unexplained crash or earlier-phase
reclassification is concealed.

# Recommendation

Preserve this implemented but incompletely validated P5.1 checkpoint.
**DO NOT AUTHORIZE P6** until the deferred validation is completed.
