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

## Session-3 result (runtime 0.2.21-p10-1) — PASS WITH LIMITATIONS

Private session `.local/p10-misc/session-3`, log `083698e3…0a85`, exit 0. finish restored everything.

- Ctrl+O no longer crashes. The options page, table of contents, main-menu buttons and quit dialog render Chinese (screenshots).
- Counters: `marked=419`, `stripped=312`, `draw_strips=105`, `bounded=0`, `invalid=10`, `leaks=10`, `errors=0`.
- **Bestiary title (CONFIRMED, static + runtime)**: `0x4260F1` loads misctext 255 and
  `sprintf("\x0C\x11%c", text[0])` (format `0x7846B4` / `0x7846BC`, chosen by `text[0] <= 'M'`) as a decorative
  drop cap; `text+1` becomes the title label. The marker lead became the drop cap and the three digits leaked
  (`!n\` = plan 7297 = misctext 255). This is the only reference to either format string.
- Options buttons are off-centre: the width `0x5C6240` is taken from the still-marked text.
- The quit dialog (flow `0x41F305`) overflows its frame: texture glyphs are always 16 px, while that dialog's
  native font is smaller.
- Sign (book entry 340, flow `0x426DF3`): `book_flow` reports `bound=true`, yet the glyph stage did not locate the
  slots (unlocated glyphs counted in the flow probe). The 64-entry ring held only 17 buffers then, so this was not
  eviction. Cause UNKNOWN.

## Runtime 0.2.22-p10-1

- Misctext 255 gets a sacrificial leading space (`MiscDropCapEntry`). The drop cap is a space and the full title stays in `text+1`.
- New hook **`string_width` at `0x5C6240`**. Original bytes `57 8B 7C 24 08 33 C0`, lengths 1/4/2.
  The human authorized it on 2026-11-10 ("請繼續調整" in reply to the list naming this hook).
  - For text holding a marker, the width is the native width of the stripped copy, plus for each CJK slot
    (texture advance − (native 0x7F width + spacing)). Counters: `misc.measures`, `misc.measure_faults`.
- Diagnostics:
  - `flow_misses` records unlocated 0x7F glyphs inside a recorded flow text, with the covering ring buffer if any.
  - `texture_fonts` records, per font blob used by texture glyphs, its height (`blob+4`), spacing and extra leading.
    This is input for font-relative CJK sizing (dialog overflow), which is not yet implemented.

## Session-4 result (runtime 0.2.22-p10-1) — PASS WITH LIMITATIONS

Private session `.local/p10-misc/session-4`, log `27dc21be…813d`, exit 0. finish restored everything.

- The bestiary title rendered as full Chinese (drop-cap fix works).
  - The human prefers the original decorative English title, so misctext 255 is now kept in English (store record removed).
- Counters: `marked=143`, `stripped=92`, `draw_strips=40`, `measures=20`, `measure_faults=0`, `leaks=0`, `invalid=0`, `errors=0`.
- Texture fonts seen: blob heights 15 (2,755 glyphs), 18 (6,205) and 18 (147). Spacing is 0 for all; extra leading is −1.
- Sign (book 340): `bound=true` again, and the flow probe counted 30 unlocated glyphs inside its text range.
  `flow_misses` stayed empty because the 0.2.22 filter only recorded bytes equal to `0x7F`.
  So the bytes at the unlocated glyph sources were **not** `0x7F` when drawn. Cause still UNKNOWN.

## Runtime 0.2.23-p10-1

- Message box (`0x41F2C3` → flow return `0x41F305`): the text rectangle `(0x1C,0x26,0x9C,0x50)` is the caller's
  own stack local (CONFIRMED, static). When the flow holds misctext Chinese, it is inset by 8 raster px on both sides
  before line positions are fixed. Width goes from 128 to 112. Counter: `misc.message_insets`.
- `flow_misses` now records any unlocated byte inside a flow text: the first 8 byte values, plus `slot_misses` for `0x7F`.
- Translation: BOOKS-EN 1 heading "Beasts" → 怪獸／敵人, because the list includes human foes (human review).

## Session-5 result (runtime 0.2.23-p10-1) and the sign path

Private session `.local/p10-misc/session-5`, log `5a7c4f94…0110`, exit 0. finish restored everything.
Counters: `message_insets=1`, `measures=26`, `leaks=0`, `errors=0`.

- `flow_misses` showed that every unlocated glyph inside bound book flows was ASCII (`slot_misses=0`).
  Book 340 is the save/load help page, not a sign. Its Chinese was drawn.
- **Signs (CONFIRMED, static):** `0x5E96F0` reads the sign's book id (object property `0x4D` via `0x4C5640`),
  then calls the book reader `0x42E560` (call `0x5E9701`). It passes the returned buffer to the screen message
  routine `0x624680(text, len/10+2, 1)` and frees the buffer.
  - So signs never reach a text flow. Their converted book stays a pending book, which explains `book_overwritten`.
  - The text is shown in the on-screen message area, the same place as the clock message.
- `0x42E560` converts into its own buffer at `0x42E644`. It compacts markup in place (CRLF and backtick codes,
  `0x42E692…`) and returns that buffer.
- `0x624680` constructs the message holder `0x41BBB0`. Its full copy is the existing copy hook site `0x41BC61`.
- Misctext messages 3–6 (`0x63BB19` → `0x63BB3F`) pass a marked string object cache to the same routine.

## Runtime 0.2.24-p10-1

- The book conversion records its output buffer (`pending_book_buffer`).
- At the existing copy hook `0x41BC61` (dispatch stage 0, lock held), an unbound source is handled in two ways:
  - If it equals the pending book buffer, the holder's copy is bound like a book page
    (k-th `0x7F` → k-th CJK scalar) and the pending book is consumed. Counter: `misc.book_messages`.
  - Otherwise, markers in the holder's copy are stripped in place. Counter: `misc.misc_message_strips`.
  - Both use the texture glyph path. The message raster is low resolution, so this is not the subtitle compositor.
- `bind_book` and `strip_misc` gained a `locked` flag so they can run inside dispatch without re-taking the lock.

## Session-6 result (runtime 0.2.24-p10-1)

Private session `.local/p10-misc/session-6`, log `fc0da18b…e8a7`, exit 0. finish restored everything.

- Signs now show Chinese in the screen message area (screenshots: 禁止露營, 野花保護區). `misc.book_messages=6`.
  - The text is hard to read: the probe chose ink `0x8000` (RGB1555 black) for the message font
    (blob height 21, reference `I`). That font is a light fill inside a dark outline; the P9-4 rule
    "darkest recurring shade" picks the outline.
- The message box shows the inset on first display, but a mouse-over re-flow loses it. The re-flowed buffer is already
  stripped, so `strip_misc` reports no Chinese.

## Runtime 0.2.25-p10-1

- Ink rule: for each recurring shade, compute its most enclosed pixel (equal solid neighbours in the 3×3 cell).
  The ink is the darkest shade whose enclosure is within 2 of the best.
  - Thin light edge tones of anti-aliased book fonts stay excluded.
  - An outlined font picks its fill.
  - When the pick is not the darkest shade, the darkest becomes a 1-pixel down-right drop shadow, drawn first.
  - Logged as `inks[].shadow` / `shadow_value`.
  - Book and journal inks should be unchanged. This still needs a visual check.
- Message box: a re-flow of a buffer already registered with Chinese segments is inset as well.

## Session-7 result (runtime 0.2.25-p10-1)

Private session `.local/p10-misc/session-7`, log `f133b72e…d1fa`, exit 0. finish restored everything.

- Signs are still dark. For the message font (height 21), the probe's reference glyph `I` has a single solid
  shade, `0x8000`: 78 written pixels, enclosure 8, no shadow chosen.
  - The light fill seen on English messages is therefore **not** a solid main-plane shade.
  - HYPOTHESIS: the fill is written to the aux plane only, or blended with the background.
- The probe's two passes shared one aux buffer, so the aux plane of the black-background pass was overwritten. This was unobserved until now.
- `message_insets=5`: the message box inset now survives re-flows.

## Runtime 0.2.26-p10-1

- Separate aux buffers for the two probe passes.
- `inks[].samples` lists up to 8 distinct written pixel classes of the reference glyph:
  (main on 0x0000, main on 0xFFFF, aux on 0, aux on ~0, count). It also logs `aux_only` (main differs, aux equal) and `aux_enclosure`.
- If aux-only pixels form a stroke interior (enclosure ≥ 5, within 2 of the solid ink), they become the ink and the
  solid shade becomes the 1-pixel shadow (`aux_fill=true`). Otherwise the behaviour is unchanged.

## Session-8 result (runtime 0.2.26-p10-1)

Private session `.local/p10-misc/session-8`, log `6d670301…9551`, exit 0. finish restored everything. Signs were still dark.

- Pixel classes (CONFIRMED). The message font (height 21), reference `I`, 78 solid pixels:
  - `0x8000` ×56 (thick dark outline);
  - light shades `0xDA1D` ×5, `0xD73B` ×5, `0xC631` ×4, `0xEF7D` ×2, `0xEB5A` ×2, plus `0x8066` ×4.
  - The aux plane is untouched; the aux-fill hypothesis is disproven.
- The fill is a thin anti-aliased light core spread over several shades. Each shade has low enclosure, so the enclosure rule kept the outline.
- Other fonts: the height-15 font is `0x98C6` ×22 plus a light edge tone ×4. Book fonts (height 18) have many shades, with dark below half of the pixels.

## Runtime 0.2.27-p10-1

- Outlined-font test: split the solid shades at the luma midpoint. A light pixel is *core* when all four neighbours are solid.
  - If dark pixels are at least half of the written pixels and there are at least 4 core pixels, the font is outlined.
  - Ink = the most frequent core shade; outline = the previous (dark) ink, drawn first at all 8 one-pixel offsets.
  - Logged as `inks[].outline`, `core_light`, `dark_pixels`.
- From the session-8 samples, book fonts fail the dark-majority test.
  - The height-15 font passes it, but its light pixels are edge pixels, so it is expected to fail the core test. Needs an in-game check.

## Session-9 result (runtime 0.2.27-p10-1) — PASS

Private session `.local/p10-misc/session-9`, log `8ca78dc9…fdd7`, exit 0. finish restored everything.

- Signs render readable Chinese in the message area: a light fill with a dark outline (human-confirmed, screenshots).
- Ink decisions:
  - Message font (height 21): outlined, fill `0xD73B` (18 core pixels, 60 of 78 dark).
  - Height-15 font: not outlined, `0x98C6`.
  - Book fonts (height 18): not outlined, `0x80A8` and `0xA447`. These are the same inks as sessions 4–8.
- Counters: `book_messages=7`, `message_insets=7`, `errors=0`, texture `faults=0`, `rejects=[0,0,0,0]`.
