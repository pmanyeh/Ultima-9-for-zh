# P5.1 persistent runtime integration

Authorized 2026-10-31. Starting HEAD
`de789311e92f437060aef6d76ca3a6908a5b07d6`; documentation checkpoint `5a873fe`.
This continues the approved P5 result; it does not repeat earlier research.
P6, translation expansion and other resource families remain unauthorized.

## Gate A implementation

Both launcher and DLL are MSVC Win32/x86, C++20, static CRT. No added third-party
runtime library or hook framework. All generated files stay in `.local/p5-1/`.
The versioned 8240-byte protocol contains fixed-width integers and UTF-16 arrays,
with no x64 host pointer in the ABI. Paths are CLI configuration only.

1. Launcher validates pinned executable/wrapper SHA-256 and the DLL's exports.
2. Creates its own game child with CREATE_SUSPENDED, no debug creation flags.
3. A five-byte, own-allocation x86 stdcall worker (`33 C0 C2 04 00`) returns zero.
   Its normal thread startup completes process/DLL loader initialization while
   the game's primary thread remains suspended. A native asset-free subprocess
   test verifies that the fixture's primary entry is not executed before resume.
4. Enumerates actual modules; resolves forwarded system exports by their owning
   module's verified path and RVA, never by assuming identical system DLL bases.
5. Loads the runtime with a one-time LoadLibraryW remote thread, verifies the
   resulting DLL mapping, and invokes the initializer outside DllMain.
6. Runtime independently validates image base, executable/wrapper hashes/path,
   any already loaded wrapper base, protocol and mode. It reports READY or FAIL
   through the configuration and completed initializer thread.
7. Only a verified READY permits explicit primary-thread resume. Host memory
   reads/writes and remote threads are initialization/rollback operations only.
8. Initialization failure calls shutdown, unloads/verifies the DLL's absence,
   releases configuration storage, aborts the launcher's own unresumed child,
   closes owned handles. General process termination is not exposed.

DllMain performs no initialization, GDI, waits, hook installation or logging.
Inert bootstrap supports explicit shutdown/unload while the primary is suspended;
the first normally loaded runtime otherwise lives until process exit. General
hot-unload of an active renderer is not promised.

The initial pre-DLL experiment found Toolhelp error299 before loader initialization.
No runtime had loaded and no game primary thread resumed. The loader worker and
asset-free isolation test correct that integration assumption. This is not a new
P5 renderer finding. Gate A is now **PASS**: loaded-runtime and explicitly
unloaded-runtime launches both reached native 3D and exited with code0. READY
preceded primary resume, both reported no attached debugger, and forced failure
verified shutdown/unload/allocation rollback without primary resume. All five
protected files and private configurations remain unchanged. Private evidence:
`bootstrap-normal-01.jsonl`, `bootstrap-unload-01.jsonl`,
`forced-failure-03.jsonl` and `gate-a.json` under `.local/p5-1/`.

## Validation recorded so far

- Original Python baseline:65/65 PASS with local assets, zero skips.
- MSVC19.51.36252.0, toolset14.51.36231, Windows SDK10.0.26100.0;
  CMake4.3.1-msvc1, generated Release Win32 targets.
- CTest: one native executable PASS, eight bootstrap checks plus an asset-free
  loader/primary-isolation subprocess integration test.
- Executable/wrapper dry validation:PASS, no game created.
- Forced initialization rejection:FAIL handshake as intended, shutdown and
  unload verified, game primary never resumed, no remaining game process.

## Remaining integration gates

Observe/pass-through hooks precede Unicode activation. The implementation must
keep explicit subtitle allowlisting, generalized identity generations, both width
readers, reusable final-size glyphs, per-frame queue/raster bindings, short locked
compositor sections and device/surface validation. No logging, allocation or GDI
is permitted while the backbuffer is locked. Multi-entry, focus/fullscreen,
repeated launch/exit,15-minute persistence and approximately60-minute soak evidence
remain required; none is implied by the current bootstrap checks.

## Persistent implementation after observe equivalence

Gate B passed native English with13 hooks and five complete subtitle lifecycles.
Render uses14 reviewed boundaries, including actual-repaint invalidation after
native allocation/early returns. Constructor instances receive monotonic identity
IDs; verified complete copies inherit the ID with a new buffer generation.
Overlap rejects; free/overwrite/repaint retire bindings. Raster identity includes
its originating instance and repaint generation. Queue/frame records retain both
raster and queue generations. Unknown text always remains native.

Only explicit private allowlist UTF-16 matches enter the Unicode route. One7f
slot represents one supported BMP CJK scalar. Both width consumers use the same
16-unit logical metric through stable TLS headers. Latin delegates unchanged.
No legacy encoding identifies a Unicode run.

The font file is hash-verified, registered FR_PRIVATE, exact face name and
GetFontData bytes checked. GetGlyphIndicesW/GGO_GRAY8_BITMAP|GGO_GLYPH_INDEX
produce direct20/40em coverage before READY. DC/font objects are created/deleted
in that initializer thread; only CPU glyphs survive. Cache capacity64, current
corpus4 keys including full font hash/scalar/em/mode. Missing glyph/key rejects.

Each frame holds up to64 unique queue records and512 glyph commands. Submission
deduplicates within the presentation and checks raster hash/generations/backend/
dimensions/scale. Pre-Flip validates inactive scene, current backbuffer and stale
records, computes bounded clips, locks, blends grayscale into BGRX preserving X,
then unlocks before native Flip. Frame commands clear after return even on failure.
No pixel pointer survives Lock. CPU glyphs are never enlarged.

The actual locked helper is shared by native synthetic tests. It allocates
nothing and calls no GDI/logging. An I/O gate acquired before Lock excludes the
diagnostics worker's disk writes. Failed/lost Lock skips the frame and invalidates
surface generation; next valid surface is rechecked. Failed Unlock or identity/
format faults request normal quit after leaving Lock. Existing opaque slots
remain suppressed rather than interpreted as ANSI.

ExitProcess disables admission, joins diagnostics and quiesces owned calls before
full byte/pointer restoration, private-font removal and handle closure. Gateways
and the small Engine shell remain until OS teardown because late rejected callers
can still be in gateways. Live hot-unload is refused. Startup rollback restores,
verifies, frees gateways and unloads before primary resume.

Short development runs confirmed800×6002263 custom frames and1600×12001853,
all six selected subtitles, zero hook/Lock/Unlock errors and4 cache entries.
Focus/minimize and rest/awake transitions were observed. A first compositor
attempt safely quit before Lock because the integration check dereferenced the
inner interface twice; existing P5 evidence establishes root+0xC is the interface
itself. Corrected validation passed. These runs do not establish15/60-minute
stability or the final repetition matrix.

Primary API references:
[process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags),
[LoadLibraryW](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryw),
[DllMain constraints](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-best-practices).
