# U9Cht native runtime — P5.1

MSVC Win32/x86, C++20, static CRT; no generic hook framework. Build outside
tracked paths (Visual Studio C++ desktop tools and Windows SDK required):

```powershell
cmake -S runtime -B .local/p5-1/build -A Win32
cmake --build .local/p5-1/build --config Release
ctest --test-dir .local/p5-1/build -C Release --output-on-failure
```

`bootstrap`, `observe` and explicitly allowlisted `render` are implemented.
The launcher requires
`--game-dir` and a fresh `--log` JSONL path; `--runtime` defaults to the sibling
U9ChtRuntime.dll. All paths are CLI configuration, never embedded user paths.
`--validate-only` verifies without creating a game; `--force-init-failure`
exercises abort/rollback before primary-thread resume. `--verify-unload` checks
complete inert-runtime unload before normal native execution.

No on-disk executable patch, debugger, debug registers, EIP redirection or
per-frame host memory access. One-time remote threads load the DLL and invoke
its exported initializer. A versioned fixed-width configuration returns READY
or FAIL before the launcher resumes the suspended primary thread. DllMain does
not initialize hooks, call GDI, wait or log under loader lock.

Runtime builds, logs, fonts, allowlists, test resources and gameplay evidence
remain private. Normal process exit owns final DLL lifetime; general hot-unload
is not promised. Observe requires an explicit private `--allowlist` pack bound to
the exact resource hash. It delegates original text/glyph/metrics/pixels unchanged.
Render adds `--font` with the pinned local Noto font, prewarms20/40em CPU glyphs
and composites only registered CJK at native800×600/1600×1200 output. See the hook
manifest for all14 reviewed boundaries, ABI and rollback contract. Other target
resolutions fail closed in this bounded phase. The user now authorized the
[event-driven gate](../docs/architecture/P5_1_EVENT_VALIDATION.md) in place of
time-based soak. Reassessment is in progress; P5.1 is not yet fully certified.

Version0.1.1 has bounded lifetime diagnostics. With a running private session,
`scripts/verify_p5_1_runtime.py LOG --live` gives provisional evidence only.
Closed-session verification requires normal exit and restored hooks/font/handles.
Use `--event-config PRIVATE_RECEIPT.json` for a closed event-gate cycle and
`--repeat-entry 4170` for the repeat-lifecycle case. Historical time options are
retained for analyzing old evidence; they are not the current gate.
