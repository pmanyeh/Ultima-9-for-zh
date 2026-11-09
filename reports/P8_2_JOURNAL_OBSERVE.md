# Phase

P8-2 — Journal draw-path observation (observe-only). Authorized by the human on 2026-11-08
("需要你授權的 runtime 改進<==可以"); the session was started after the human's 「準備好了」 on 2026-11-09.

# Scope

Find out how the journal page draws its text, without changing game output. No J1/J2 storage
change and no new drawing were implemented.

# Status

PASS WITH LIMITATIONS. The draw path was observed. No journal entry was appended during play, so the
append-side counters remain unobserved.

# Environment

- Runtime `U9ChtRuntime/0.2.10-p8-2`, built with Visual Studio 18 2026, Win32, into `.local/p8-2/build` (LOCAL ONLY).
- DLL SHA-256 `99ab4d2662e6bc74f4878ad48bf1d075920f5e86e342280905362c4fd273ae3c`.
- Launcher SHA-256 `7345284e57bc705adff3462fa99fa5e1997c92b6582c23463a0b3992991bbf00`.
- Pack SHA-256 `bf461adc93b0cba95ef013914fdd161c555bbc6e59a08496dedc6e625e9cdd7f` (P8-1 build, unchanged).
- System ANSI code page 950.

# Inputs

The private game copy and the P8-1 localization build. The private `diary.txt` holds one English entry (92 bytes).

# Work Performed

Observe-only probes, all CPU counters:

1. In the existing `WideCharToMultiByte` IAT hook, the return address `0x615DF7` (journal append) is
   recorded and passed through unchanged. Recorded fields: code page, length, capacity, result and the
   matched entry.
2. A pass-through inline hook at the text-flow initializer `0x5C7620`. Original bytes `8B 44 24 08 53`
   (`mov eax,[esp+8]; push ebx`) are copied into the gateway. The hook records the caller, the text
   pointer, length and FNV hash, and the flow buffers.
3. Non-allowlisted layout, bounds and glyph sources are attributed to recorded flow buffers. The paint
   context and native raster size are kept for glyph hits.
4. Caller tables for the glyph, paint-cache and queue hooks.

`scripts/run_p8_0_session.py` gained `--preserve-saves`. It backs up the whole savegame directory,
including `diary.txt`, and restores it after the session.

# Findings

See `docs/research/U9_JOURNAL_PATH.md`, section "Observe-only session".

- CONFIRMED: the journal page is flow caller `0x426648`, and its text is the 92-byte `diary.txt`.
- CONFIRMED: journal glyphs pass the hooked glyph function `0x5C5A80` but outside the paint-cache
  chain, and are drawn into a 256×256 page raster. Book pages behave the same.
- CONFIRMED: the journal is a 3D perspective book. The flat compositor cannot render on it.
- CONFIRMED: journal width measuring does not reach the existing width hooks.

# Evidence

| Check | Result |
| --- | --- |
| Smoke session (`.local/p8-2/session-smoke`) | exit 0, 17 hooks, 0 errors, raster hashes 4,582 = 4,582, saves restored |
| Human session (`.local/p8-2/session-journal`) | exit 0, 91,258 frames, 0 errors, 0 raster faults, hooks restored |
| Restoration | protected assets match P0, config restored, preserved saves restored |
| Log SHA-256 | `c2c84c3afcd8e5316c186a3de123759cca002ddbda3c1acf092f06e14d744077` |
| Visual | Journal showed the English entry, as expected (screenshot kept locally by the human) |

# Tests

- `ctest` (Release): 6/6 passed.
- `python -m unittest discover -s tests`: 153 run, OK, 3 skipped.

# Results

The display half of the journal cannot use the dialogue compositor. It needs a texture-space glyph writer.

# Files Changed

`runtime/U9ChtRuntime/engine.cpp`, `runtime/U9ChtRuntime/engine.h`, `runtime/CMakeLists.txt`,
`runtime/common/version_manifest.h`, `u9cht/l10n/runtime_pack.py`, `scripts/run_p8_0_session.py`,
`docs/research/U9_JOURNAL_PATH.md`, this report.

# Risks

The probes stay in the runtime. Their cost is a few lock-protected counter updates per glyph, paint and
queue call. No frame-time regression was seen, but none was measured either.

# Blockers

None for research. Implementing journal Chinese requires a new texture-space writer (new runtime scope).

# Deviations From Master Plan

None. Observe-only, with no executable patch on disk.

# Recommendation

Before building the writer, decide the storage form (J1 UTF-8 or J2 marker). Then prototype the
texture writer on one book or journal string. A second observe session that appends a journal entry
would confirm the append counters.
