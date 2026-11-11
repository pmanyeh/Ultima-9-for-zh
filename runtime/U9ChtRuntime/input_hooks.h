#pragma once
// Input hooks on u9.exe's USER32 imports (in-memory IAT entries only; nothing is patched on disk).
//
// Session 18 (log-only probe) CONFIRMED that u9.exe takes keyboard and mouse input as window messages pulled with
// PeekMessageA, queries modifiers with GetKeyState and polls GetKeyboardState, and never handles WM_MOUSEWHEEL.
//
// Three independent features, each off unless enabled:
//  - probe:  log-only counters of messages and key-state queries (runtime/input_probe.on).
//  - wheel:  WM_MOUSEWHEEL without modifiers becomes a PgUp/PgDn key press, which the default keymap binds to
//            book_next_page / book_previous_page (wheel down = PgUp = next page). (IB-2, authorized 2026-11-11)
//            Ctrl+wheel becomes PgUp/PgDn with the real Ctrl held = zoom_in / zoom_out (wheel up = zoom in).
//  - hover:  the cursor resting 250 ms over the game window holds the "examine" key (X) until the cursor moves,
//            so object names show without holding X. (IB-1, authorized 2026-11-11)
// Synthetic key messages carry a marker in the repeat-count field; WM_CHAR produced from them by
// TranslateMessage is turned into WM_NULL so no "x" is typed into text fields.
#include <windows.h>
#include <string>

namespace u9cht::input_hooks {
using PeekFn = BOOL(WINAPI*)(LPMSG, HWND, UINT, UINT, UINT);
using GetFn = BOOL(WINAPI*)(LPMSG, HWND, UINT, UINT);
using AsyncFn = SHORT(WINAPI*)(int);
using StateFn = SHORT(WINAPI*)(int);
using BoardFn = BOOL(WINAPI*)(PBYTE);

struct Options {
    bool probe = false;
    bool wheel = false;
    bool hover = false;
    DWORD hover_delay_ms = 250;
};
void configure(const Options& options);
bool any_enabled();

extern PeekFn peek_original;
extern GetFn get_original;
extern AsyncFn async_original;
extern StateFn state_original;
extern BoardFn board_original;

BOOL WINAPI peek_hook(LPMSG msg, HWND hwnd, UINT min, UINT max, UINT remove);
BOOL WINAPI get_hook(LPMSG msg, HWND hwnd, UINT min, UINT max);
SHORT WINAPI async_hook(int vk);
SHORT WINAPI state_hook(int vk);
BOOL WINAPI board_hook(PBYTE keys);

// JSON object body (no braces) with probe and feature counters since the last call, or "" when nothing happened.
std::string drain_fields();
}
