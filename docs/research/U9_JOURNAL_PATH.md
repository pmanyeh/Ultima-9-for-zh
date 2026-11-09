# Journal (diary) text path — P8-1 research

2026-11-08. Pinned English `u9.exe` SHA-256 `83915175…b545`, image base `0x400000`.
Static analysis used capstone 5.0.7 over the mapped image (local helper, not tracked).
Runtime evidence comes from the private P8-W1 session (`.local/p8-w1/session-1`).
No game asset content is reproduced here.

## Summary

The journal is **not** drawn from text.flx plans. Each journal entry is converted once more from
UTF-16 using the system ANSI code page and **appended as bytes to `savegame/diary.txt`**. The journal
page then reads that file back and lays it out. Chinese journal text therefore needs:

1. a lossless, locale-independent byte encoding at the append step; and
2. a Unicode association for those bytes on the display side.

The append step is the root cause of the current failure. It loses data before any rendering happens.

## Evidence

### Runtime (CONFIRMED, P8-W1 session counters)

| Entry | Category | Constructor (`wide`) | Selected conversion (`cache`) | Complete copy / layout / glyph |
| --- | --- | --- | --- | --- |
| 4078 | journal | 1 | 1 | 0 / 0 / 0 |
| 4165 | journal | 1 | 1 | 0 / 0 / 0 |
| 4251 | subtitle (for comparison) | 1 | 1 | 1 / 32 / 32 |

The journal strings are constructed and matched to their plans, but they never reach the
hooked dialogue copy, width or glyph boundaries.

### Saved data (CONFIRMED)

- Neither the save files nor `processes.dat` contain journal source text (ASCII or UTF-16) or 0x7F-slot
  strings. The search covered `u9game*.sav`, `nonfixed.*` and `processes.dat`.
- The session's `savegame/diary.txt` (91 bytes) holds `Day 1: ` followed by **CP950 (Big5)** bytes of
  our Chinese targets, including the `譯名(English)` annotations.
- Each entry is cut off after about half its characters. Two entries end in a lone Big5 lead byte
  (`… A6 0A`), which is the first byte of 列.

### Static code (CONFIRMED by disassembly; behavior in game not yet traced)

| VA | Role |
| --- | --- |
| `0x61e18e`, `0x61e1bb` | Only callers of the journal-add routine (script side). |
| `0x42e0a0` | Journal add, fastcall `ECX`=text object, `EDX`=flag. It calls `0x615db0` at **`0x42e0a6`**, then `0x42e0c0(ECX=obj+0 bytes, EDX=flag)`. |
| `0x615db0` | Text-object method "rebuild bytes from UTF-16". It allocates `wcslen+1` bytes and calls `WideCharToMultiByte(CP_ACP, 0, obj+8, -1, buf, wcslen+1, 0, 0)` at **`0x615df1`** (IAT `0x74010c`). It writes NUL at `buf[wcslen]`, then stores a strdup in `obj+0`. **Only caller: `0x42e0a6`.** |
| `0x42e0c0` | Opens `diary.txt` (string `0x784c38`) with read/write access, `OPEN_ALWAYS`, and seeks to the end. When the day changes it writes a `Day N:` header built from named texts `0x62`/`0x63`. It then writes the entry bytes unchanged, plus `\n` if missing. **No wrapping.** Other callers: `0x4206c9` (typed-note box destructor appends its ASCII buffer) and `0x42ed29`. |
| `0x426410`… | Journal page loader. It opens `diary.txt` (string `0x7846c4`) for reading and reads the whole file into a heap buffer. It strdups that buffer into `page+0xC8`, falling back to the named text "Journal Notes" (`0x7846d0`, id `0x1b`). It then calls `0x5c7620(ECX=page+0xD4, widget=page+0xCC, &page+0xC8, 1, 0)`. |
| `0x5c7620` | Paged text-flow initializer (64 KiB layout buffer at `+0x38`, 4 KiB at `+0x34`). It has 24 callers, including book pages. |

The English design assumes one byte per UTF-16 unit (`wcslen+1`). That holds for ASCII text and
for single-byte code pages only. Consequences, all CONFIRMED by code reading:

- With CP950 (this machine), `WideCharToMultiByte` runs out of buffer. The entry is truncated and can end
  in a split double-byte character.
- With a single-byte code page such as 1252, CJK becomes `?`.
- The result depends on the player's system locale. Neither outcome is acceptable.

No path writes the whole journal buffer back to `diary.txt`; it is append-only (STRONG EVIDENCE,
static). Display-side transforms therefore would not write back into saves.

### Japanese oracle (from `U9_JP_CJK_IMPLEMENTATION.md`)

The Japanese executable converts with a length query first, then allocates `query+1` bytes. That
fixes sizing but still depends on the locale code page. It is not reusable here.

## Observe-only session (P8-2, 2026-11-09)

Runtime `0.2.10-p8-2` adds counters only: the journal append conversion, a pass-through hook on the
text-flow initializer `0x5C7620`, and caller tables. Game output was unchanged. See
`reports/P8_2_JOURNAL_OBSERVE.md`.

| Flow caller (return) | Calls | Text bytes | Bounds hits (text) | Glyph hits (text) | Glyph raster |
| --- | --- | --- | --- | --- | --- |
| `0x426648` (journal page) | 1 | 92 = size of `diary.txt` | 0 | 455 | 256×256 |
| `0x4260c6` (book page) | 1 | 3,562 | 103,680 | 15,139 | 256×256 |
| `0x42771f` (book page) | 1 | 1,404 | 19,761 | 4,554 | 256×256 |

- CONFIRMED: the journal page is flow caller `0x426648`. Its text pointer is the strdup of
  `diary.txt`, and glyphs are drawn directly from that buffer.
- CONFIRMED: journal and book glyphs go through the already-hooked glyph function `0x5C5A80`
  (via `0x5C5D09`), with the source pointer in stack slot 9, like dialogue.
- CONFIRMED: every journal/book glyph was drawn **outside** the paint-cache chain `0x5CFCE0`
  (paint generation 0) into a **256×256** native raster.
- CONFIRMED (screenshot): the journal is a perspective 3D book; the page texture is warped on screen.
  The flat screen-space compositor used for dialogue cannot place text on it.
- CONFIRMED: journal line measuring does not reach the hooked bounds (`0x5C5F5B`) or layout
  (`0x5C7BB3`) points; book pages do reach the bounds point.
- No journal entry was appended during the session, so the append counters are still unobserved.

## Unknowns

- UNKNOWN: which function measures journal line widths (it is not a hooked width point).
- UNKNOWN: how the page texture is submitted. The only queue callers seen were `0x5CFDBB`,
  `0x5CFEC5` (both inside the paint-cache function) and `0x5620CA`.
- UNKNOWN: how the text flow wraps text with no spaces. It may force breaks at byte level.
- HYPOTHESIS: the history timeline (4216–4242) is drawn by a different page class.

## Consequence for the design

Storing the entry (J1/J2) is only half the problem. Drawing needs a **texture-space glyph writer**:
when the hooked glyph function `0x5C5A80` meets a CJK slot on a page raster, write our cached glyph
coverage into that 256×256 raster at the native glyph position, the same place the native blit
(`0x5E20E0`) writes. The 3D page then warps Chinese like English. This is new runtime work. It
also needs a width hook for the journal measuring path. Books (books-*.flx) share the same writer.

## Candidate design (not implemented, needs a decision)

**J1 — UTF-8 diary entries (recommended for evaluation).**

- Hook the single call site `0x42e0a6` in memory, the same class of reversible hook as the existing 14.
  When `obj+8` exactly matches an allowlisted plan, write the plan's UTF-8 into `obj+0` using the game
  allocator (`0x7108f0`; freed natively by `0x7108e0`). Otherwise call the original `0x615db0`.
- Result: `diary.txt` holds lossless, locale-independent UTF-8. English text is byte-identical
  because ASCII is unchanged.
- On the display side, after the loader reads the file, decode UTF-8 runs into 0x7F slots plus Unicode
  metadata, and accept only scalars that are in the pack's glyph allowlist. Then reuse the existing
  width, glyph and compositor stages, provided the unknowns above confirm the same paint chain.
- Trade-offs:
  - Display association is content-based (decoded scalars), not an exact plan match.
  - A save made with Chinese journal entries shows mojibake for those entries if loaded without the
    runtime. Saves still load.

**J2 — marker entries (`U9Jxxxx` in `diary.txt`).**

- Keeps exact plan identity, and the marker always fits the `wcslen+1` buffer.
- Without the runtime the journal shows raw markers.
- Markers must be expanded to plan text at display time, which needs a larger buffer.
- The `Day N:` header and typed notes interleave with the markers.

**Hook cost.** The runtime already replaces the `WideCharToMultiByte` IAT slot (`0x74010c`), so it
already sees the `0x615df1` call (return address `0x615df7`).

- J2's append step needs no new hook: one more selected return address in the existing conversion
  hook, writing a 7-byte marker that always fits `wcslen+1`.
- J1 cannot be done there, because UTF-8 needs up to 3 bytes per unit. J1 needs a new call-site hook
  at `0x42e0a6`.
- Both options need a display-side hook after the loader reads `diary.txt`.

Neither option needs an on-disk executable patch. The next safe step is an **observe-only** session: log the `0x42e0a6` matches and the paint
chain taken while the journal page is open, with no output change.

## Already-affected test saves

The diary entries in local test saves written since P8-W1 are truncated Big5. That data is lost and
cannot be repaired from the file. Only the local test copy is affected; the human's original
installation is untouched.
