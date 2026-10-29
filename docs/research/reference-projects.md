# Reference projects and reuse decision

Recorded 2026-10-28; batch completed 2026-10-29 (Asia/Taipei).

| Project | Pinned commit | Use |
| --- | --- | --- |
| [theGreyWanderer-uc/tgwUltima](https://github.com/theGreyWanderer-uc/tgwUltima/tree/2b6ee659cb153254ea8e3d2787d601a6fa79f3d2) | `2b6ee659cb153254ea8e3d2787d601a6fa79f3d2` | TITAN 0.7.8, U9 archive/text format reference |
| [Fenyx4/UltimaPatcher](https://github.com/Fenyx4/UltimaPatcher/tree/c5db7b77b93a3b99b27556c3e5d8654d1679ced5) | `c5db7b77b93a3b99b27556c3e5d8654d1679ced5` | Reference pin only; no patch downloaded or applied |

Pins were obtained with `git ls-remote <repository-url> HEAD`. They describe this
batch's reference versions, not an instruction to update to a future HEAD.

## Reproduce source inspection

```powershell
git clone --filter=blob:none --no-checkout https://github.com/theGreyWanderer-uc/tgwUltima.git .local/upstream/tgwUltima
git -C .local/upstream/tgwUltima show 2b6ee659cb153254ea8e3d2787d601a6fa79f3d2:titan-ultima/src/titan/u9/flx_archive.py
python scripts/audit_upstream.py
```

The last command loads only the three pinned Python source modules into the
ignored audit directory and runs four synthetic probes. Expected result:
`audit_probes_reproduced: 4`. Source SHA-256 values are recorded in
`reports/P0_UPSTREAM_AUDIT.json`.

## CONFIRMED: reuse needs a preservation layer

Synthetic probes reproduce these behaviors at the pinned commit:

1. `repack()` regenerates a custom unknown header byte at `0x70` as zero.
2. A declared out-of-bounds used entry is returned as empty bytes by the reader.
3. The text reader strips every trailing NUL, losing their multiplicity.
4. The text reader accepts an even-length string without a final NUL.

These observations concern synthetic edge cases, not corruption of this game's
original archive. The local `text.flx` passes the stricter checks.

The unchanged MIT container reader is vendored with its license. Project code
wraps it with strict bounds/size checks. The serializer preserves the source
header, physical ordering, exact aliases, gaps and trailer; only known directory
and size fields are updated when synthetic replacement lengths change.
Using the generic upstream writer would conflict with AGENTS.md's requirement
to preserve unknown bytes. This documents why that writer was not reused.

Dependency scope: TITAN 0.7.8 container-reader source, MIT. No pip dependencies
were installed. NumPy, Pillow, FreeType and TITAN's interactive CLI are not needed
for the authorized text round-trip. See `THIRD_PARTY_NOTICES.md`.

## Evidence limits

Upstream `text.py`, `books.py` and `typename.py` provide format/consumer leads.
Only this local `text.flx` received full payload decoding and rebuild validation.
Descriptions of other payload families remain upstream evidence until separately
tested. Japanese rendering, glyph resources and renderer behavior remain UNKNOWN.
