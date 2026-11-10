# misctext.flx UI text path — P10-1 research

2026-11-10. Pinned English `u9.exe` SHA-256 `83915175…b545`, image base `0x400000`.
Static analysis: capstone 5.0.7 through the local helper `.local/p10-misc/u9dis.py` (not tracked).
Runtime evidence: private session `.local/p10-misc/session-1` (runtime `0.2.19-p9-5`, log `8fbd701d…2b71b`).
No game text is reproduced here.

## Symptom

With 243 draft misctext translations installed, every misctext screen seen in the session
showed magenta dots where Chinese should be. This included the options book, the save/load
dialog caption, the stats page and the sign description pop-up. Nothing was Chinese.

## Where the Chinese is lost — CONFIRMED

The `0x7F` bytes are **not** a game conversion loss. They are the runtime's own opaque slots.

1. The string object constructor `0x615A10` converts the UTF-16 entry through
   `WideCharToMultiByte` at `0x615B76` into a temporary `wcslen+1` buffer.
   - The runtime (`wide_hook`, return `0x615B7C`) writes the plan's slot string there: ASCII is kept,
     and each CJK scalar becomes `0x7F`.
2. At `0x615B9D…0x615BCF` the constructor `strdup`s that buffer into `obj+0` and frees the temporary.
   - `obj+0` has no stored length.
   - The getter `0x615D00` is simply `mov eax,[ecx]; ret`.
3. The runtime binds `obj+0` to the plan (`ctor_hook`). Counters for all 97 misctext plans that
   were constructed: `wide=1, cache=1, freed=1`; `copies/layout/bounds/glyph/unicode_draws = 0`.
4. UI code copies the text with **inline** `strlen` + `0x7108F0` + `rep movs` sequences.
   - Example: journal fallback title at `0x4265A3…0x426615`, using the named-text factory
     `0x616120(ECX=id, EDX=default)` → `0x615D00` → inline copy.
   - These copies are not a hookable function, so the binding does not follow them.
5. The copies reach the paged text-flow initializer `0x5C7620`. The flow text consists of
   ASCII plus anonymous `0x7F` bytes. The glyph stage finds no binding and draws the native
   `0x7F` glyph, which is the magenta dots.

### Flow callers seen with misctext content (CONFIRMED, `flow_text` events)

| Return address | Length | Note |
| --- | --- | --- |
| `0x42687A` | 1038 / 702 | large pages (options / status), contain `(Avatar)`, `(Earth)` |
| `0x426DF3` | 99 | short page (sign description pop-up, HYPOTHESIS) |
| `0x4260C6` | 1243 | book-page caller with misctext content |
| `0x425F3E` | 854 | page |
| `0x425DC0` | 117 | stats page (`: 30/30`), 3 native high bytes |
| `0x41F305` | 9 | dialog caption (save/load dialog, HYPOTHESIS); text from widget field `+0x80` |
| `0x41F80F` | 8 | caption |

- Every such flow drew its glyphs **outside** the paint-cache chain into 256×256 native rasters.
  This is the same raster class as journal and book pages, which the P8-3 texture glyph writer already handles.
- The save-slot list (`0x420850` / `0x41FBC1`) and the journal entry (`0x426648`) were ASCII.

## Why content matching cannot work — CONFIRMED (offline)

Once reduced to slot strings, the 243 misctext targets have only 32 distinct byte patterns.
12 of those patterns are shared, and they cover 207 of the 243 strings (for example, 64 targets are just `7F 7F`).
A slot run in a flow buffer therefore cannot be mapped back to its scalars by content. The
book method (`bind_book`, k-th slot → k-th scalar of one known plan) does not apply either,
because a UI page concatenates many strings.

## Clock message — CONFIRMED

The "It is … past …" message is not in any FLX. It is assembled from format strings in the
executable's data (`It is %s.`, `It is %s %s.`, `a quarter till`, …, file offset about `0x3A70F4`).
Translating it is a separate executable-string task. It is out of scope here.

## misctext provenance — CONFIRMED (static)

- `0x545990` (entry length) and `0x5459F0` (entry read) each have exactly one caller: the named-text
  factory `0x616120`, at `0x616143` / `0x61616F`.
- Both read the archive global `0xAE7C4C`. That global is loaded from the path record `0x786C20`
  (directory pointer + `misctext.flx`) at `0x545748…0x5457D6`.
- The factory constructs its string object with `0x615A10`. The return address is **`0x6161AB`**.
- 0x616120 has 155 direct callers, all UI code.
- So "constructor returned to `0x6161AB`" identifies a misctext string exactly. This also covers the 3 misctext
  targets that share a plan with text.flx (2044–2046).

## Flow initializer keeps the `char**` — CONFIRMED (static)

`0x5C7620` stores its text argument (a `char**`) at `flow+0x14` and dereferences it later.
For UI callers, that `char**` points at a widget field (for example `+0x80` at `0x41F2D1`) or at a stack copy.
Replacing the buffer, as the journal expansion does, would therefore leave the widget's own field dangling.
Markers are stripped **in place** instead.

## Implemented design M1 (runtime 0.2.20-p10-1)

1. **Constructor** (`ctor_hook`, existing site `0x615A10`): when the return address is `0x6161AB`,
   a text-domain plan matched, and render with texture glyphs is enabled:
   - allocate `marker + slot string` with the game allocator `0x7108F0`;
   - store it in `obj+0`;
   - free the native cache with `0x7108E0`.
   - The marker is `0x1E` followed by three base-94 digits (`0x21..0x7E`) of the plan index.
   - Any check failure falls back to the old binding (`misc.mark_failures`).
2. **Flow initializer** (`flow_hook`, existing site `0x5C7620`): for every caller except the journal page
   `0x426648`, `strip_misc_markers` (`misc_marker.h`) removes markers in place.
   - The NUL moves to the new end.
   - Each marker binds the following bytes that match the plan's slots. A truncated copy binds the matching prefix (`misc.partial`).
   - Segments go into the shared journal/book buffer ring, enlarged from 8 to 64 entries.
   - A re-flow of an already stripped buffer finds no markers and keeps its segments until the game frees the buffer.
3. **Width and glyph**: unchanged journal/book machinery: `journal_locate` at `0x5C7BB3` / `0x5C5F5B` /
   `0x5C6378` / `0x5C6F5A`, and the texture glyph writer at `0x5C5A80` via `0x5C5D09`.
4. **Diagnostics** (`texture.misc` in `runtime_counters`): `marked`, `mark_failures`, `stripped`, `buffers`,
   `invalid`, `partial`, and `leaks`. `leaks` counts glyph calls on a `0x1E` byte, meaning a marked string was drawn outside a stripped flow.

Marker overhead: with the current drafts, 34 of 243 marked strings are longer than their English
source, by at most 4 bytes. HYPOTHESIS: UI copies are heap `strlen`-sized (the observed pattern), so this is
harmless. A fixed-size stack copy would be the risk to watch for.

Remaining risks:

- A misctext string consumed outside `0x5C7620` shows `0x1E` plus three ASCII characters (`leaks`).
- Letter spacing follows the journal setting; leading is not changed for UI flows.
- No new hook site and no executable byte changes. Excluding misctext from the build restores English behaviour.

Unit tests: `runtime/tests/misc_marker_tests.cpp`, which covers encode/decode, concatenation, digits after a plan,
truncation, malformed markers, and re-flowed text.

## Session-2 result (runtime 0.2.20-p10-1, 2026-11-10) — FAIL, crash

Private session `.local/p10-misc/session-2`, log `c66ab8a9…b13f`. Exit code `0xC0000005` on Ctrl+O.
finish restored every protected asset, save and config.

- Counters: `marked=46`, `stripped=0`, `leaks=0`, `errors=0`.
  - Marked at load: spellbook entries 102–158.
  - Marked on Ctrl+O, just before the crash: options labels 69–89 and save-slot texts 231–234.
- **Cause (CONFIRMED, static):** the draw-string routine `0x5C5C00(text,end)` dispatches bytes `0x00–0x0D`
  through its own control-code table (`0x5C5C2B`). Every other byte goes to the glyph function `0x5C5A80`.
  That function returns NULL for bytes `< 0x20` (`0x5C5A84`). The caller then raises the fatal
  "Invalid character encountered in print." (`0x5C5D0D` → `0x556480`, string `0x7A16E4`).
  The marker lead `0x1E` hits exactly this. → **The marker lead must be ≥ 0x20.**
- Options labels are **not** text flows. 0x428AEF… measures each label with `0x5C6240`
  (control bytes count as 4 spaces), then copies it inline into a label widget (`vtable 0x742D18`, text at `+0x24`).
  The label's draw method `0x41F710` passes `[+0x24]` to `0x5C5C00` (call at `0x41F751`).
- `0x5C5C00` has 21 direct callers. These include the label draw (`0x41F751`), the flow line draw (`0x5C66F0`) and the
  dialogue/name labels (`0x41ACAD`, `0x41AEBD`). Its prologue `8B 44 24 08 53` matches the existing
  `0x5C7620` hook pattern.
- The sign description (flow `0x426DF3`, same FNV hash as session-1) contained `0x7F` slots but no marker.
  It is **not** a misctext string. It is a text-domain string from another constructor caller (UNKNOWN which one).

## Runtime 0.2.21-p10-1 (fix for session-2)

- Marker lead changed to **`0x8F`**.
  - It is ≥ 0x20, so it is never dispatched to the NULL-returning glyph branch.
  - It is undefined in Windows-1252 and never appears in plan slots.
  - All four marker bytes are now ≥ 0x20; a unit test checks this.
- New hook **`draw_string` at `0x5C5C00`**, authorized by the human on 2026-11-10.
  - Original bytes are `8B 44 24 08 53`, instruction lengths 4/1, the same pattern as `0x5C7620`.
  - Unbounded calls (`end == 0xFFFFFFFF`, as from the label draw `0x41F751`) strip markers from the label's own buffer in place before the native loop runs.
  - Bounded calls are only counted (`misc.bounded`).
  - New counters: `misc.draw_strips`, `misc.bounded`.
- Book diagnostic for the sign page (flow `0x426DF3` after the book reader `0x42E560`):
  - one `book_flow` event per consumed conversion, giving caller, entry, length and whether it was bound;
  - `misc.book_overwritten` counts conversions that replaced an unconsumed pending book.
  - Session evidence so far: session-1 converted 11 and bound 5; session-2 converted 3 and bound 1, with 0 mismatches.
- Known limit: label centring is computed by `0x5C6240` on the marked string before stripping, so a label may be off-centre by up to 4 native character widths.
