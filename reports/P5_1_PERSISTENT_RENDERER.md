# Phase

P5.1 — Persistent High-Resolution Unicode Renderer Integration, 2026-10-31.

# Scope

Only the explicitly authorized P5.1 continuation from
`de789311e92f437060aef6d76ca3a6908a5b07d6`. P0–P5 findings remain established.
P6, Chinese wrapping, other resource families and translation expansion are not
authorized. This document is an active checkpoint, not a completed P5.1 claim.

# Status

**PASS WITH LIMITATIONS — Gate A bootstrap checkpoint only.**
**P5.1 overall remains INCOMPLETE.** No persistent Unicode rendering or long-run
result is claimed by the bootstrap tests. Gates B–I remain NOT EXECUTED here.

# Environment

Windows 11 x64 host / native Win32 x86 targets. MSVC19.51.36252.0,
toolset14.51.36231, Windows SDK10.0.26100.0, CMake4.3.1-msvc1, C++20/static CRT.
Python3.12.10, Git2.55.0.windows.3. Existing native tools only; no external hook
framework, font library or package dependency added. TITAN and Japanese-source
pins are unchanged from approved reports.

# Inputs

English executable SHA-256
`83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545`;
wrapper SHA-256
`f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502`;
pristine text.flx SHA-256
`378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0`.
All five protected private files match P0. Compiled binaries, configuration
backups, logs and screenshots remain in ignored local paths.

# Work Performed

Committed documentation checkpoint `5a873fe` before implementation. Added a
Win32/x86 CMake launcher/DLL, versioned8240-byte configuration ABI, independent
SHA-256/module checks, explicit READY/FAIL handshake, private JSONL diagnostics,
normal process lifetime and initialization rollback. Bootstrap installs no hooks.

The launcher creates its own child suspended, initializes the OS loader with a
normal own-allocation worker, loads the DLL, invokes its initializer outside
DllMain, validates READY and only then resumes the primary. Runtime normal launch
does not use a debugger, debug registers, breakpoints or EIP redirection.

# Findings

**CONFIRMED Gate A:** the normally loaded runtime reaches the native800×600 3D
scene with unchanged English rendering, READY before resume and debugger=false;
normal exit0. Explicit inert-runtime shutdown/unload is verified by a fresh
module snapshot before a second normal scene/exit0. Forced initialization failure
returns FAIL, unloads the DLL, releases owned configuration storage and aborts
only the newly created unresumed child.

**Integration assumption disproven:** Toolhelp module enumeration is not ready in
a freshly suspended process before loader initialization (error299). That first
attempt had not loaded the runtime or resumed the game. The five-byte own worker
and an asset-free primary-isolation subprocess test resolve this without manual
EIP changes or execution of the game's primary entry before READY.

# Evidence

Private `.local/p5-1/evidence/bootstrap-normal-01.jsonl`,
`bootstrap-unload-01.jsonl`, `forced-failure-03.jsonl`; `.local/p5-1/gate-a.json`
records the gate result and protected hashes. Private screenshots:
`.local/evidence/P5_1_A_NATIVE_800_20261031.png` and
`P5_1_A_UNLOADED_800_20261031.png`. No screenshots are published.
Architecture and exact bootstrap/rollback contract are in
[persistent runtime](../docs/architecture/P5_1_PERSISTENT_RUNTIME.md) and
[hook manifest](../docs/architecture/P5_1_HOOK_MANIFEST.md).

# Tests

`python -m unittest discover -s tests -v`, configured local assets:
**before65/65 PASS; after Gate A65/65 PASS; zero skips, exit0**.

```powershell
cmake -S runtime -B .local/p5-1/build -G "Visual Studio 18 2026" -A Win32
cmake --build .local/p5-1/build --config Release
ctest --test-dir .local/p5-1/build -C Release --output-on-failure
```

Build PASS with /W4 /WX. CTest **1/1 PASS**: eight bootstrap checks and asset-free
loader/primary-isolation integration. PE headers confirm all targets x86.
Baseline-only launcher validation creates no game. Forced failure exits2 as
expected; loaded/unloaded normal launches exit0. No original code was patched.

# Results

Gate A PASS. Pristine text export/import remains BYTE-PERFECT PASS via the local
integration test. Protected assets and private Options.ini/dxcfg.ini are unchanged.
This checkpoint does not establish persistent hooks, Unicode composition,
multi-entry lifecycle, fullscreen/device recovery or soak stability.

# Files Changed

README/Master Plan documentation checkpoint; `.gitignore`; `runtime/` native
bootstrap/common protocol/platform/native tests; P5.1 architecture/hook manifest
and this checkpoint report. Generated binaries/private evidence are excluded.

# Risks

Active-renderer hot-unload is not promised. Inert bootstrap unload and complete
initialization rollback are proven; later hooks must retain deterministic safe
rollback and avoid freeing executing gateways. DLL loading alone changes no
text/rendering behavior. No on-disk executable modification is required.

# Blockers

No remaining Gate A blocker. Persistent rendering, lifecycle and the required
multi-resolution/repetition/15-minute/approximately60-minute tests remain work
to be completed; they must not be inferred from a successful launch.

# Deviations From Master Plan

The user's P5.1 insertion and selected native architecture govern this batch.
No previous phase was redone or reclassified. P6 remains unauthorized.

# Recommendation

Continue authorized P5.1 with observe/pass-through hook equivalence, then the
remaining lifecycle/rendering gates. **DO NOT AUTHORIZE P6 on this checkpoint.**
