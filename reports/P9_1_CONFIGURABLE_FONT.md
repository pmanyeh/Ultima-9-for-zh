# Phase

P9-1 — Configurable Chinese font (first step toward player settings). Authorized by the human on
2026-11-09 ("好的，就依妳的順序"). The game session started only after the human's 「準備好了」.

# Scope

Let the player choose the CJK font file. Out of scope: glyph size, weight, colour, letter spacing and
line height. Each of those becomes a new settings key when it is implemented.

# Status

PASS. The human confirmed in game that the font changed to jf-openhuninn-2.1.

# Environment

- Runtime `U9ChtRuntime/0.2.12-p9-1`, built with Visual Studio 18 2026, Win32, into `.local/p9-1/build` (LOCAL ONLY).
- DLL SHA-256 `1c32c423e73e541625e6280003848239d6f18fe355d9694d93ae20775c39e9d1`.
- Launcher SHA-256 `8dd93d9f0cf6277f8d58734b09ca22e58b52e5c9874f4c86eefa4ced66edd745`.
- Offline check tool SHA-256 `fee10a10582638f7cc4bcd98318f895b0b39b44f34447183f67076acb9b27b1a`.
- Pack: the P8-1 build (`.local/p8-1/out`), unchanged.
- Rollback: 0.2.11 (`.local/p8-3/build`).

# Inputs

| Font | Family (from the file) | License | SHA-256 | Tracked |
| --- | --- | --- | --- | --- |
| Noto Sans CJK TC Regular 2.004 | `Noto Sans CJK TC` | SIL OFL 1.1 | `dce08bd4…88b4` | no |
| jf-openhuninn 2.1 | `jf-openhuninn-2.1` | SIL OFL 1.1 | `9d5bf493…c825` | no |

Font files stay local. Only hashes are recorded.

# Work Performed

**The runtime no longer has a built-in font.**
- `FontHash` and the hard-coded family `Noto Sans CJK TC` are removed.
- `GlyphCache::open` reads the chosen file once and hashes it.
- The family is read from the file's OpenType `name` table: Windows platform, nameID 1, en-US preferred.
- Collections (`ttcf`) are refused with a clear message.

**Substitution protection is kept but changed.**
- GDI on a zh-TW system reports localized face names (for example `jf open 粉圓 2.1`), so the face-name comparison is gone.
- Instead, the data of the face GDI actually selected (`GetFontData`) must hash to the chosen file. This is the stronger check, and it already existed.

**Layout invariant (new).**
- Offline wrapping assumes every CJK glyph advances exactly one 16-unit cell. The previous build relied on Noto happening to satisfy this.
- Now `Engine::install` and `U9ChtShowcaseCheck` require it, and `RUNTIME_CONTRACT["custom_logical_advance"] = 16` is enforced by `logical_advance` in the pipeline.
- A font that disagrees is refused before READY, so the game is never resumed with broken layout.

**Player settings file (`--config`).**
- The launcher reads a Windows INI. `[font] file` is the only key in this version.
- The format is strict: any unknown section or key is an error, so a setting is never silently ignored.
- Relative paths resolve against the INI's directory.
- Giving a font both by `--font` and by the settings file is an error.
- Example file: `config/u9cht.example.ini`. A real copy holds a local path and stays under `.local/`.

**Logging.** New events `runtime_font` and `offline_font` record the family, SHA-256 and file name.

**Session runner.** `--config` passes the INI to the launcher, records `settings_sha256`, and hashes the font the INI names.

# Findings

- CONFIRMED: jf-openhuninn-2.1 covers all 2,291 pack scalars, and each advances exactly 16 units at 16, 20 and 40 px.
- CONFIRMED (human): dialogue text renders in jf-openhuninn in game.
- CONFIRMED: the J2 append path works in play.
  - The game added journal entry 4078 during the session.
  - The runtime wrote the marker (`wide_length` 38, `capacity` 39, `result` 8, `marker: true`, `high_bytes` 0).
  - This closes the open item from P8-3.
- The journal page was not opened in this session (0 expansions, 0 texture glyphs), so journal rendering with the new font was not observed.

# Evidence

**Offline (`U9ChtShowcaseCheck`, P8-1 pack)**

| Case | Result |
| --- | --- |
| Noto Sans CJK TC | PASS: 7,095 plans, 2,291 glyphs, 6,873 cache entries |
| jf-openhuninn-2.1 | PASS: same counts, prewarm 2,125 ms |
| `msjh.ttc` (collection) | refused: "font collections (.ttc) are not supported" |
| `arial.ttf` (no CJK) | refused: "unsupported Unicode glyph" |

**Launcher `--validate-only`**

| Case | Result |
| --- | --- |
| Valid `[font] file` | exit 0 |
| `size = 90` | exit 2, "unsupported key font.size" |
| `[layout]` | exit 2, "unsupported section [layout]" |
| `--font` and settings file together | exit 2 |

**Game session `.local/p9-1/session-font`**

- Run: exit 0, 17 hooks, 28,643 frames, 0 errors, 0 raster faults, 0 cache misses after prewarm.
- Restoration: protected assets match P0, config restored, preserved saves restored.
- Log SHA-256: `ccc5816ba67d9f21ba69cd7e35dca472bfdd6d505c11345d4387501bc64bdce9`.

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: 153 run, OK, 3 skipped.

# Results

The player can switch the Chinese font through a settings file without rebuilding the pack, as long as
the font keeps the one-cell advance.

# Files Changed

`runtime/U9ChtRuntime/glyph_cache.cpp`, `runtime/U9ChtRuntime/glyph_cache.h`, `runtime/U9ChtRuntime/engine.cpp`,
`runtime/U9ChtLauncher/main.cpp`, `runtime/tools/showcase_check.cpp`, `runtime/common/version_manifest.h`,
`runtime/CMakeLists.txt`, `u9cht/l10n/runtime_pack.py`, `scripts/run_p8_0_session.py`,
`config/u9cht.example.ini`, this report.

# Risks

- **Proportional fonts are refused by design.** A font whose CJK punctuation is half-width needs the rewrap work planned for later (cell size and spacing).
- **INI encoding.** Windows profile APIs read ANSI or UTF-16 LE with a BOM, not UTF-8. A non-ASCII path in a UTF-8 INI would fail to resolve. The example file documents this, and the error is explicit (file not found).
- The pipeline's own font QA (`validate --font`) still uses the pinned Noto metadata in `resource-capabilities.json`. Use `U9ChtShowcaseCheck` to qualify another font.

# Blockers

None.

# Deviations From Master Plan

None. No executable patch; font files are not tracked.

# Recommendation

Proceed to the journal width hook, then glyph scale, weight and colour as settings keys.
