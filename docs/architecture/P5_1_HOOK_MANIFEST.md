# P5.1 runtime hook manifest

Current stage:Gate A inert bootstrap. **No game hooks are installed yet.**
P5 debugger evidence addresses are retained as anchors, not automatic JMP sites.
The game file on disk is never patched. Later gates must document each selected
persistent boundary here before enabling it, including full original-byte spans,
ABI, preservation, failure behavior and deterministic restoration verification.

## Pinned compatibility

| Module | Image base | SHA-256 |
| --- | --- | --- |
| English u9.exe | `0x00400000` | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| Existing ddraw.dll | `0x18000000` when mapped | `f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502` |

## Bootstrap operations (not game-code patches)

Purpose:initialize the OS loader without entering the suspended game primary,
load the x86 runtime, obtain explicit READY/FAIL, and verify initialization rollback.

- Owning module:project-owned launcher/runtime and an own-allocation worker page.
- VA/RVA:worker allocated dynamically; system exports resolved against actual
  remote owning-module path/base; initializer/shutdown use the built DLL export RVA.
- Original bytes:none replaced. No game instruction or IAT/vtable pointer is written.
- Worker bytes:`33 C0 C2 04 00`, `xor eax,eax; ret4`, complete instructions.
- Calling convention:Win32 stdcall thread procedure, one unused pointer argument,
  DWORD0 return. Nonvolatile registers/stack follow the ordinary thread ABI.
- Inputs:versioned config, pinned files and explicit CLI paths. Outputs:READY/FAIL,
  error code, process/image/wrapper identity and private structured diagnostics.
- Reentrancy:one launcher-owned initialization sequence before primary resume;
  runtime rejects repeated initialization. No per-frame work.
- Failure:never resume the game primary; shutdown/unload, release own storage,
  abort only the newly created child. Do not free an executing worker on timeout.
- Rollback:worker page freed after its thread exits; explicit DLL shutdown and
  FreeLibrary verified by a fresh module snapshot; remaining child teardown closes
  OS resources. Inert diagnostic unload is supported before primary resume.
- Evidence:approved P5 pinned inputs; native loader-isolation test and private
  `.local/p5-1/evidence/` bootstrap logs. No debugger APIs or debug registers.
