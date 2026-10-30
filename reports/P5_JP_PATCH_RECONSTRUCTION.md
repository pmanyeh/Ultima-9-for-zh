# Phase

P5-0 — Japanese Patch Reconstruction & Differential Analysis.
Completed 2026-10-30, Asia/Taipei. Starting project commit
`6efd02d96ec8eda275310da8484f91a881a891d2` on `main`.

# Scope

Explicit authorization for P5-0A–J, before renderer implementation. Download only
the specified public delta/signature and selected source/metadata, reconstruct
privately, then perform static analysis. No high-resolution renderer, P6,
translation expansion, Japanese language-pack download or game launch.

Read AGENTS.md, Master Plan, P4 Markdown/JSON, Japanese/English notebooks and P3.
The previous interrupted P5 architecture document and surface-probe script were
already untracked at startup; they are retained without changes in this batch.

# Status

**PASS WITH LIMITATIONS. Classification: JP CJK PATH CONFIRMED**, meaning static
implementation identification, not runtime verification or Traditional Chinese
support. Reconstruction succeeded with the official applier's validation enabled.

# Environment

Windows 11 build 26300; Python 3.12.10; Git 2.55.0.windows.3;
.NET SDK 10.0.302 / runtime 10.0.10; Octodiff package 1.3.23 / assembly 1.3.23.0,
Apache-2.0, optional isolated research dependency. Existing Capstone distribution
5.0.9 / module 5.0.7, BSD-style license. No dependency of the ordinary Python
toolchain was added. TITAN pin remains
`2b6ee659cb153254ea8e3d2787d601a6fa79f3d2`.

# Inputs

UltimaPatcher pinned commit:
`c5db7b77b93a3b99b27556c3e5d8654d1679ced5`.

| Input | Size, bytes | SHA-256 |
| --- | ---: | --- |
| Frozen English basis copy | 4,593,152 | `83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545` |
| Public `u9.exe.octodiff` | 3,772,022 | `ebaafd49de3dddec39b695c4fb66b29a2fb860285b6e3b09e36496e81dca8272` |
| Public `u9.exe.sig` | 58,342 | `561ebc6d39668db660b01aceb7de5af09e5e9b707dd1dede05702a628806603f` |
| Reconstructed `u9.jp.exe` | 4,432,896 | `7ba58dfe974adfa78e25d49e58fa066669e40ac9448e325c93f27147856b8282` |

The basis is the P0 GOG English executable (game ID 1207659093, build
59198760502252807); exact 1.19f/1.19h patch label remains UNKNOWN.
All game binaries and upstream payloads remain ignored under `.local/p5-jp/`.
No game asset was tracked or staged. All five protected private-runtime assets
matched P0 before this batch. Original installation files were not accessed for
writing; the private runtime was not replaced.

# Work Performed

Fetched only selected blobs from the existing pinned no-checkout source clone;
never checked out or ran UltimaPatcher. Copied the hash-verified English executable
to `.local/p5-jp/basis/u9.exe`. The new small .NET wrapper calls the real
`DeltaApplier.Apply` and `BinaryDeltaReader`, with `SkipHashCheck = False` fixed
in source. It locks basis/delta SHA-256 values, rejects linked paths, confines
paths to the private working area and refuses overwrites. A `.pending` output
is promoted to `u9.jp.exe` only after the applier returns successfully; a rejected
result would remain quarantined as `.rejected`, never a usable reconstruction.

The official run returned **ACCEPTED, exit 0**, expected output SHA-1
`e3b8703bc4245f27afc534425289a81159d4b27e`. Independent inspection rechecked
that SHA-1, target size and the SHA-256 above. No validation was disabled and no
basis byte was edited. The generated executable was never executed.

Exact initial reconstruction command (refuses to overwrite an existing result):

```powershell
dotnet run --project tools/OctodiffProbe -- .local/p5-jp/basis/u9.exe .local/p5-jp/reference/UltimaPatcher/Files/U9JPLanguagePatch/u9.exe.octodiff .local/p5-jp/u9.jp.exe
```

# Findings

**CONFIRMED: the current basis is operationally compatible with this delta.**

**CONFIRMED correction to the request's basis premise:** Octodiff 1.3.23's
`SkipHashCheck = False` verifies the **reconstructed target** against the hash
stored in the delta. It does not compare a whole-basis hash. The patcher does not
read the `.sig` during application. This distinction is established in the pinned
[DeltaApplier source](https://github.com/OctopusDeploy/Octodiff/blob/bc821c41cb3a497e16229c1e81b7a51146abab7e/source/Octodiff/Core/DeltaApplier.cs)
and [U9 installation branch](https://github.com/Fenyx4/UltimaPatcher/blob/c5db7b77b93a3b99b27556c3e5d8654d1679ced5/UltimaPatcher/U9Form.vb#L815).

The separate signature inspection found 2,243 chunks describing 4,592,640 bytes:
2,145 chunks match both SHA-1 and the original Octodiff Adler32 checksum;
98 differ. Our basis is 512 bytes longer. Therefore **the current basis is not
byte-identical to the signature's original basis**, despite producing the exact
validated target. This does not trigger the rejection branch: the official
applier accepted it. No missing historical executable was acquired.

The delta contains 44 commands: 20 literal commands totaling 3,771,392 bytes and
24 basis copies totaling 661,504 bytes. The highest referenced basis end is
4,399,104. It is not a tiny collection of text-renderer patches. This explains
why whole-file positional differences cannot be equated with changed functions.
The original signed-basis SHA-256 and historical version label remain UNKNOWN;
the current legally held GOG baseline is a demonstrated accepted basis.

# Evidence

[Structured differential](P5_JP_BINARY_DIFF.json),
[binary differential report](P5_JP_BINARY_DIFF.md), and
[CJK implementation notebook](../docs/research/U9_JP_CJK_IMPLEMENTATION.md).
Private blob hashes/sizes are also recorded in
`.local/p5-jp/reference-manifest.json`. Source reference for Octodiff 1.3.23:
`bc821c41cb3a497e16229c1e81b7a51146abab7e`.

# Tests

Before tooling changes, `python -m unittest discover -s tests -v`:
39 run, 38 passed, 1 LOCAL-ONLY skip, exit 0. Repeated with
`U9_GAME_DIR` pointing at the verified private runtime after game exit:
**39 run, 39 passed, 0 skipped, exit 0**. This also clears the earlier batch's
file-lock-only integration error; no test guard was weakened.

After tooling changes, same command with local assets:
**55 run, 55 passed, 0 skipped, exit 0**. Sixteen new synthetic tests cover
metadata bounds, unsupported commands/algorithms, original checksum behavior,
signature mismatch, range clustering, PE imports/resources and ambiguous anchors.
The optional .NET probe and metadata analysis both exited 0.
Final `dotnet build tools/OctodiffProbe --nologo --verbosity quiet`:
**build succeeded, 0 warnings, 0 errors, exit 0**. `git diff --check`: exit 0.

# Results

P5-0A/B succeeded. P5-0C basis-rejection recovery was NOT REQUIRED.
P5-0D–J completed as static analysis. No runtime claim is made.
Prior P2 BYTE-PERFECT PASS remains intact; executable reconstruction is a
different operation and is not an FLX round-trip result.

# Files Changed

New: this report, `P5_JP_BINARY_DIFF.md/.json`,
`docs/research/U9_JP_CJK_IMPLEMENTATION.md`, `u9cht/octometa.py`,
`u9cht/bindiff.py`, `scripts/analyze_p5_jp.py`,
`tools/OctodiffProbe/Program.cs`, `tools/OctodiffProbe/OctodiffProbe.csproj`,
`tests/test_octometa.py`, `tests/test_bindiff.py`.
Updated: `THIRD_PARTY_NOTICES.md`, README and the Japanese source-audit notebook's
continuation link. Private reconstructed binaries/reference files are excluded.

# Risks

The delta's SHA-1 is its historical compatibility check, not certification of
game provenance. Independent SHA-256 hashes freeze the actual inspected files.
Do not redistribute generated executables, upstream delta/signature payloads or
proprietary fonts. No font was acquired or installed. Code relocation and build
differences preclude blindly copying bytes into English addresses.

# Blockers

None for authorized static reconstruction/analysis. Japanese runtime behavior,
effective OEM code page, actual selected font, cache contents and final surface
resolution remain unmeasured. These constrain future implementation, not the
static CJK architecture conclusion.

# Deviations From Master Plan

The human inserted P5-0 and explicitly authorized local public-delta acquisition
and reconstruction without Japanese language-pack assets. The correction about
target-hash versus basis-hash validation is an evidence finding, not a bypass.
No high-resolution renderer work or optional runtime comparison was performed.

# Recommendation

Review the static findings before authorizing the real P5. Do not install the
Japanese executable or change its code page as a shortcut. Prefer the Unicode
transport option described in the implementation notebook, informed by the
Japanese capacity/routing design, with native Latin preservation and an actual
resolution gate. Stop after P5-0; P6 remains unauthorized.
