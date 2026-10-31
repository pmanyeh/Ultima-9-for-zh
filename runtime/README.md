# U9Cht native runtime — P5.1

MSVC Win32/x86, C++20, static CRT; no generic hook framework. Build outside
tracked paths (Visual Studio C++ desktop tools and Windows SDK required):

```powershell
cmake -S runtime -B .local/p5-1/build -A Win32
cmake --build .local/p5-1/build --config Release
ctest --test-dir .local/p5-1/build -C Release --output-on-failure
```

Gates A/B expose `bootstrap` and `observe`; `render` is not yet enabled.
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
See the hook manifest for all13 reviewed boundaries, ABI and rollback contract.
