# Improvement backlog

These are ideas that go beyond localization: they would change game behaviour or player experience.
Each one needs the human's explicit approval before research or implementation begins
(AGENTS.md §3, §13). IB-1 and IB-2 were authorized on 2026-11-11 and are implemented.

The two features (IB-1 and IB-2) are implemented in `runtime/U9ChtRuntime/input_hooks.{h,cpp}`:
in-memory IAT hooks on u9.exe's USER32 imports only, with nothing patched on disk.
- They are on by default.
- `runtime/hover_names.off` or `runtime/wheel_pages.off` in the build output turns one off.
- `runtime/input_probe.on` adds log-only counters.

| ID | Idea | Recorded | Status |
| --- | --- | --- | --- |
| IB-1 | Show an object's name on mouse hover instead of only while holding X | 2026-11-09 | Done (runtime 0.2.40); in-game PASS, session 23 |
| IB-2 | Mouse wheel turns pages; Ctrl+wheel zooms the camera | 2026-11-11 | Done (runtime 0.2.40); in-game PASS, session 23 |

## IB-1 — Object names on hover

**Observation (human, 2026-11-09).** Object names appear only while the player holds X. By current
conventions this is hard to discover and awkward to use. Players expect the name to appear when the
cursor rests on an object.

**What it would involve (not yet researched).**
1. Find how the game decides that X is held.
2. Find how the game chooses which objects get labels (the label path is documented in
   `docs/research/P6S2_INVENTORY_LABEL_PATH.md`).
3. Find whether a hovered object can be labelled through the same native path.

**Constraints.**
- This changes game behaviour rather than text, so the executable-patching rules apply: an
  in-memory hook with documented bytes, verification and rollback, and no patch on disk.
- Input and label triggering carry more risk than text replacement.
- Feasibility and difficulty are UNKNOWN.

**Suggested order (original).** Revisit after localization is complete (books, system messages).
Start with a static, read-only study that reports feasibility before any code is written.

**Result (2026-11-11).** No label-path change was needed.

Session 18 ran a log-only probe and CONFIRMED how u9.exe reads input:
- It reads keys and the mouse as window messages, through PeekMessageA.
- X auto-repeats while it is held.
- The game polls GetKeyboardState.

The runtime therefore emulates holding X:
- After the cursor has rested for 250 ms inside the focused game window, it queues a synthetic X key-down.
- It repeats that key-down every 100 ms, which mimics auto-repeat.
- It sets X in the GetKeyboardState array.
- It releases X when any of these happens: the cursor moves, a mouse button is held, focus is lost, or another key is pressed.
  The X key-up is delivered before that other key.

Synthetic messages carry the marker 0xA901 in the repeat-count field. The WM_CHAR they produce is dropped, so no "x" is typed into text fields.

**Pitfall: Ctrl+X = exit_game.** The default keymap binds Ctrl+X to exit_game.
- Session 20: pressing Ctrl while the synthetic X was held opened the exit dialog.
- Session 21: releasing Ctrl did the same.
  - GetAsyncKeyState already reported Ctrl up while its WM_KEYUP was still queued.
  - The new X key-down reached the game before that key-up.

The fix:
- Track modifier state from the key messages the game has actually been given.
- Never start or repeat the synthetic X while any of these is true:
  - a modifier is held physically or as the game sees it;
  - a key message is still queued (`GetQueueStatus(QS_KEY)`).

Session 22: PASS.

## IB-2 — Mouse wheel

The game ignores WM_MOUSEWHEEL (CONFIRMED, session 18). The runtime rewrites each notch as a PgUp or PgDn press, up to 4 per message:
- **No modifier:** wheel down sends PgUp, which is `book_next_page`. Wheel up sends PgDn, which is `book_previous_page`.
- **Ctrl + wheel:** the real Ctrl is held, so the press reaches the game as `ctrl+pageup` (`zoom_in`, wheel up) or `ctrl+pagedown` (`zoom_out`, wheel down).
- **Shift or Alt + wheel:** ignored.

In-game result: PASS, session 23. Checked: journal and book paging, zoom, hover at 250 ms, and pressing or releasing Ctrl.
