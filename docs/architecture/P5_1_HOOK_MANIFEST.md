# P5.1 runtime hook manifest

Current stage:persistent render implementation0.1.1. Gate B observe equivalence
passed before render activation. Final repetition/fullscreen/60-minute validation
is deferred at the user's request; no complete P5.1 certification is claimed.
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

## Persistent hooks: fixed English baseline

All sites belong to the pinned English executable above (base `0x400000`);
RVA = VA minus `0x400000`. No wrapper instruction is patched. Each inline
replacement is `E9 rel32` to the loaded runtime plus NOPs for the remainder of
the listed span. Actual ASLR-dependent replacement bytes and gateway addresses
are emitted in private `hook_manifest` records **before installation**.
Each gateway copies the entire listed instruction span then jumps to its end.
No copied span contains a relative/control-transfer instruction.

| Name / VA (RVA) | Original bytes; instruction lengths | ABI / inspected inputs and output |
| --- | --- | --- |
| constructor `615a10` (`215a10`) | `6aff6826467300`; 2,5 | thiscall, ECX object, three stack DWORDs, RET12; preserve original raw EAX. After return verify retained UTF-16 at object+8 and exact byte cache at object+0. |
| complete copy `41bc61` (`01bc61`) | `33ffc744242058020000`; 2,8 | interior, EAX complete byte length including NUL, ESI/EDI just past copied data, EBP holder; holder+ec must equal destination. Observe only verified complete copies. |
| layout width `5c7bb3` (`1c7bb3`) | `8b84c110ffffff`; 7 | interior MOV, EBP scalar's source pointer, ECX font, ESI font record. Execute original MOV; observe association; continuation `5c7bba`. |
| bounds width `5c5f5b` (`1c5f5b`) | `8b84c210ffffff`; 7 | interior MOV, EDI source, EDX font, ECX font record. Execute original MOV; continuation `5c5f62`. |
| glyph `5c5a80` (`1c5a80`) | `8b54240c80fa20`; 4,3 | thiscall, three stack args x/y/byte, RET12; selected caller `5c5d09`, source at entry ESP+36. Observe native raster global `133393c`; original draws/return preserved. |
| paint cache `5cfce0` (`1cfce0`) | `64a100000000`; 6 | thiscall ECX cache owner, one widget stack argument; raw original EAX retained. TLS paint generation bounds repaint/raster lifetime. |
| actual raster repaint `5cfd50` (`1cfd50`) | `891d3c393301`; 6 | interior MOV global133393c=EBX; continuation5cfd56. Retire previous cache/queue generation only after allocation and early-return branches, before actual widget draw. Also invalidates metadata when replacement text is outside the allowlist. |
| raster/queue `508d50` (`108d50`) | `8a44241053`; 4,1 | thiscall manager, five stack DWORDs: raster, float x/y bits, flags. Selected caller `5cfdbb`. Original completes raster and queue first; inspect bounded lists manager+4/+10, node+8 raster. Original EAX unchanged. |
| queue destruction `5083f0` (`1083f0`) | `6aff68a8e37200`; 2,5 | thiscall ECX node, no arguments; retire binding before original destructor, raw EAX retained. |
| native free `7108e0` (`3108e0`) | `8b44240450`; 4,1 | cdecl one pointer; retire exact buffer/raster/queue metadata before original free. |
| pre-Flip `597b00` (`197b00`) | `568bf18a8609c53f00`; 1,2,6 | thiscall ECX backend, no arguments; observe current frame before native Flip and advance frame after return. Original EAX retained. |
| conversion IAT `74010c` (`34010c`) | resolved system WideCharToMultiByte pointer | stdcall eight arguments; selected return `615b7c` plus active constructor TLS plus exact allowlist match. Observe mode delegates unchanged. |
| exit IAT `74024c` (`34024c`) | resolved system ExitProcess pointer | stdcall one exit code, non-returning. Disable work, quiesce, restore, flush, delegate original exit. |
| submission vtable `74fc18` (`34fc18`) | `509f5800` (pointer `589f50`) | native thiscall triangle slot, original stack/return/register inputs preserved by tail jump. Selected callers `50913d/50915e/50917b/509193`; EBX node, EBP manager, ECX backend. Deduplicate selected node per presentation. |

### Preservation, reentrancy and failure

- Inline interiors save PUSHFD/PUSHAD and aligned FXSAVE/FXRSTOR state around
  callbacks. Stack is restored exactly. Whole-function wrappers use matching
  x86 thiscall/fastcall adapters, preserve nonvolatile registers under the MSVC
  ABI and return original raw EAX. Observe changes no glyph/metric/pixel output.
- Nested constructor→conversion and paint→glyph/queue calls are intentional.
  Constructor TLS is bounded to16; paint TLS is stacked by wrapper call scope.
  Shared fixed-capacity registries/counters use one SRW lock. Hook callbacks
  perform no disk logging. A separate worker takes snapshots every5 seconds.
- All originals, instruction boundaries, IAT targets and vtable pointer must
  match before installation. Mismatch rejects READY. Registry/raster mismatches
  produce explicit diagnostics; observe continues native behavior only.
- Five-byte jumps fit one aligned8-byte block at all selected sites. Atomic
  prefix swaps publish/remove detours; trailing original bytes are restored
  while the jump still bypasses them. Initial installation occurs before the
  primary resumes. Pointer slots use aligned atomic compare/exchange.
- Startup rollback restores in reverse order and verifies every full original
  span/pointer before releasing gateways. Normal exit disables admission and
  waits for active owned calls before restoration. Gateways stay allocated
  until process exit because another thread may already be past a callback.
  Explicit unload is accepted only before any engine hook has run; live
  hot-unload is refused. Native synthetic concurrent-restore tests exercise
  the offset3 prefix/tail boundary and gateway lifetime.
- Evidence basis: P5 approved routing notebook
  `docs/research/U9_TEXT_SURFACE_PIPELINE.md`, offline instruction inspection,
  pinned byte verification and upcoming normal-launch Gate B private counters.
  Gate B is not declared passed by this implementation manifest alone.

## Render activation following Gate B

Gate B13-hook observer passed normal exit with five complete native subtitle
lifecycles and zero errors. Render integration adds the actual-repaint boundary
above (14 hooks total) to reject stale cache identity even for non-allowlisted
repaint. Render mode changes only explicitly associated scalars U+4E2D/U+6587:

- Conversion returns one opaque7f slot per CJK scalar, retains UTF-16 metadata.
  Native ASCII slots are copied exactly. No legacy code page identifies CJK.
- Both width callbacks replace only EAX's font-relative metric-header offset;
  TLS stable32-byte header begins with16 minus verified native spacing. All
  saved registers/flags/FP state are otherwise restored. Native Latin unchanged.
- Glyph interception returns that header with RET12 for registered7f CJK slots;
  it captures logical placement and skips only the low-resolution native draw.
  Other glyph calls tail-jump to the original gateway. The branch occurs before
  POPFD, so no test/branch flags escape to the caller.
- Queue completion verifies expected Unicode-placement count, hashes the native
  raster and binds generation. Submission validates raster/queue generations,
  exact cache hash, selected caller, native scale, backend and current backbuffer.
- Pre-Flip accepts only the observed inactive-scene XRGB8888 target. Current
  surface is locked/unlocked on the native thread each applicable frame; no
  cached pixel pointer survives. Glyph cache is prewarmed at20/40em beforeREADY.
- Fatal association/format/Unlock errors suppress further composition and post
  a normal WM_QUIT request after leaving any Lock interval. Native unrelated
  calls remain delegated. Lost/failed Lock skips the frame, invalidates surface
  generation and permits only a freshly revalidated subsequent surface.
