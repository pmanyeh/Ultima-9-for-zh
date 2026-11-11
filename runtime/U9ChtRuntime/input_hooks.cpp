#include "input_hooks.h"
#include <atomic>
#include <cstdlib>
#include <cstdio>
#include <deque>
#include <mutex>
#include <vector>

namespace u9cht::input_hooks {
PeekFn peek_original = nullptr;
GetFn get_original = nullptr;
AsyncFn async_original = nullptr;
StateFn state_original = nullptr;
BoardFn board_original = nullptr;

namespace {
Options options;

// ---- probe counters (log only) ----
std::atomic<long> async_calls[256]{}, state_calls[256]{}, keydown[256]{}, keyup[256]{}, async_down[256]{};
std::atomic<long> board_calls{0}, peek_calls{0}, get_calls{0};
std::atomic<long> mouse_move{0}, char_msgs{0};
std::atomic<long> buttons[10]{};     // WM_LBUTTONDOWN (0x201) .. WM_MBUTTONDBLCLK (0x209)
std::atomic<long> wheel_msgs{0}, wheel_delta{0}, hwheel_msgs{0};
std::mutex sample_lock;
std::vector<std::string> samples;

// ---- feature counters ----
std::atomic<long> wheel_pages{0}, wheel_zoom{0}, wheel_skipped_modifier{0}, hover_presses{0}, hover_releases{0},
                  chars_suppressed{0}, board_overrides{0}, modifier_releases{0}, preempted_releases{0};

// ---- synthetic messages (game thread only) ----
constexpr WORD Marker = 0xA901;      // repeat-count field of synthetic key messages
constexpr UINT ScanX = 0x2D, ScanPrior = 0x49, ScanNext = 0x51;
std::deque<MSG> pending;
HWND game_window = nullptr;          // window that receives the game's mouse messages
POINT last_cursor{-1,-1};
DWORD last_move = 0, last_repeat = 0;
bool hover_active = false;
constexpr DWORD RepeatMs = 100;      // mimic keyboard auto-repeat while the synthetic X is held (session 18)

bool synthetic(const MSG& m) { return LOWORD(m.lParam) == Marker; }

LPARAM key_lparam(UINT scan, bool extended, bool up, bool repeat) {
    LPARAM l = Marker | (LPARAM(scan & 0xFF) << 16);
    if (extended) l |= LPARAM(1) << 24;
    if (up) l |= (LPARAM(1) << 30) | (LPARAM(1) << 31);
    else if (repeat) l |= LPARAM(1) << 30;
    return l;
}

void queue_key(HWND hwnd, UINT vk, UINT scan, bool extended, bool up, bool repeat = false) {
    MSG m{};
    m.hwnd = hwnd; m.message = up ? WM_KEYUP : WM_KEYDOWN; m.wParam = vk;
    m.lParam = key_lparam(scan,extended,up,repeat); m.time = GetTickCount(); GetCursorPos(&m.pt);
    pending.push_back(m);
}

bool down(int vk) { return async_original && (async_original(vk) & 0x8000) != 0; }
// Message-synchronized key state (GetKeyState), i.e. what the game sees with the current message.
bool key_state_down(int vk) { return state_original && (state_original(vk) & 0x8000) != 0; }
bool modifier_down() { return key_state_down(VK_CONTROL) || key_state_down(VK_SHIFT) || key_state_down(VK_MENU); }

void sample(const char* what, const MSG& m) {
    std::lock_guard<std::mutex> lock(sample_lock);
    if (samples.size() >= 24) return;
    char text[192];
    std::snprintf(text,sizeof(text),"{\"what\":\"%s\",\"msg\":%u,\"wparam\":%lu,\"lparam\":%ld,\"tick\":%lu}",
        what,m.message,static_cast<unsigned long>(m.wParam),static_cast<long>(m.lParam),static_cast<unsigned long>(GetTickCount()));
    samples.emplace_back(text);
}

void observe(const MSG& m) {
    const UINT id = m.message;
    if (id == WM_KEYDOWN || id == WM_SYSKEYDOWN) {
        const auto vk = static_cast<unsigned>(m.wParam) & 0xFF; ++keydown[vk];
        if ((vk == 'X' || vk == VK_PRIOR || vk == VK_NEXT) && !synthetic(m)) sample("keydown",m);
    } else if (id == WM_KEYUP || id == WM_SYSKEYUP) {
        const auto vk = static_cast<unsigned>(m.wParam) & 0xFF; ++keyup[vk];
        if ((vk == 'X' || vk == VK_PRIOR || vk == VK_NEXT) && !synthetic(m)) sample("keyup",m);
    } else if (id == WM_CHAR) ++char_msgs;
    else if (id == WM_MOUSEMOVE) ++mouse_move;
    else if (id >= WM_LBUTTONDOWN && id <= WM_MBUTTONDBLCLK) ++buttons[id-WM_LBUTTONDOWN];
    else if (id == WM_MOUSEWHEEL) { ++wheel_msgs; wheel_delta += GET_WHEEL_DELTA_WPARAM(m.wParam); sample("wheel",m); }
    else if (id == 0x20E) ++hwheel_msgs; // WM_MOUSEHWHEEL
}

// Drops queued synthetic X repeats, so nothing re-presses X after the release.
void drop_pending_x() {
    for (auto it = pending.begin(); it != pending.end();)
        it = (synthetic(*it) && it->wParam == 'X' && it->message == WM_KEYDOWN) ? pending.erase(it) : it + 1;
}

void release_hover(bool send) {
    if (!hover_active) return;
    hover_active = false;
    drop_pending_x();
    if (send && game_window) { queue_key(game_window,'X',ScanX,false,true); ++hover_releases; }
}

// Physical modifier state (GetAsyncKeyState), ahead of the message queue. Session 20: Ctrl pressed while the
// synthetic X was held reached the game as Ctrl+X = exit_game.
bool physical_modifier() { return down(VK_CONTROL) || down(VK_SHIFT) || down(VK_MENU) || down(VK_LWIN) || down(VK_RWIN); }

// Modifier state as the GAME has seen it, from the key messages it has been handed. Session 21: after Ctrl was
// released, GetAsyncKeyState already reported it up while its WM_KEYUP was still queued; the hover X key-down
// (served from the pending queue first) reached the game before that key-up, i.e. as Ctrl+X = exit_game.
unsigned seen_modifiers = 0;
int modifier_bit(WPARAM vk) {
    switch (vk) {
    case VK_SHIFT: case VK_LSHIFT: case VK_RSHIFT: return 1;
    case VK_CONTROL: case VK_LCONTROL: case VK_RCONTROL: return 2;
    case VK_MENU: case VK_LMENU: case VK_RMENU: return 4;
    case VK_LWIN: return 8;
    case VK_RWIN: return 16;
    default: return 0;
    }
}
void track_modifiers(const MSG& m) {
    if (synthetic(m)) return;
    const int bit = modifier_bit(m.wParam);
    if (!bit) return;
    if (m.message == WM_KEYDOWN || m.message == WM_SYSKEYDOWN) seen_modifiers |= bit;
    else if (m.message == WM_KEYUP || m.message == WM_SYSKEYUP) seen_modifiers &= ~unsigned(bit);
}
// Key input still waiting in the thread's message queue (not yet seen by the game).
bool keys_queued() { return (HIWORD(GetQueueStatus(QS_KEY)) & QS_KEY) != 0; }
// No modifier is held physically or as far as the game knows, and no key message is still on its way.
bool modifiers_clear() { return !physical_modifier() && !seen_modifiers && !keys_queued(); }

// Called on every PeekMessageA (the game polls it continuously; session 18: ~1,200 calls per minute or more).
void update_hover() {
    if (!options.hover) return;
    const DWORD now = GetTickCount();
    POINT p{}; GetCursorPos(&p);
    if (p.x != last_cursor.x || p.y != last_cursor.y) {
        last_cursor = p; last_move = now;
        release_hover(true);
        return;
    }
    if (!game_window) return;
    const HWND foreground = GetForegroundWindow();
    const bool focused = foreground && (foreground == game_window || GetAncestor(game_window,GA_ROOT) == foreground);
    POINT c = p; ScreenToClient(game_window,&c);
    RECT r{}; GetClientRect(game_window,&r);
    const bool inside = PtInRect(&r,c) != FALSE;
    const bool busy = down(VK_LBUTTON) || down(VK_RBUTTON) || down(VK_MBUTTON);
    if (hover_active) {
        if (physical_modifier() || seen_modifiers) { release_hover(true); ++modifier_releases; return; }
        if (!focused || !inside || busy) { release_hover(true); if (!focused) seen_modifiers = 0; return; }
        if (now - last_repeat >= RepeatMs && !keys_queued()) { queue_key(game_window,'X',ScanX,false,false,true); last_repeat = now; }
        return;
    }
    if (!focused) seen_modifiers = 0;
    if (!focused || !inside || busy || down('X') || !modifiers_clear()) return;
    if (now - last_move < options.hover_delay_ms) return;
    queue_key(game_window,'X',ScanX,false,false);
    hover_active = true; last_repeat = now; ++hover_presses;
}

bool in_filter(const MSG& m, UINT min, UINT max) { return (!min && !max) || (m.message >= min && m.message <= max); }

// Rewrites a removed message for the features. Returns the message to hand to the game.
void transform(MSG& m) {
    track_modifiers(m);
    if (options.hover) {
        if (m.message == WM_MOUSEMOVE || (m.message >= WM_LBUTTONDOWN && m.message <= WM_MBUTTONDBLCLK)) game_window = m.hwnd;
        if (m.message == WM_CHAR && synthetic(m)) { m.message = WM_NULL; m.wParam = 0; m.lParam = 0; ++chars_suppressed; return; }
        // A real key or button ends the synthetic hold; a real X takes over without a synthetic release.
        // The release must reach the game BEFORE the real input, so the real message is put back at the front of
        // the queue and the synthetic X key-up is delivered in its place.
        if (!synthetic(m) && hover_active) {
            if ((m.message == WM_KEYDOWN || m.message == WM_SYSKEYDOWN) && m.wParam == 'X') { hover_active = false; drop_pending_x(); }
            else if (m.message == WM_KEYDOWN || m.message == WM_SYSKEYDOWN ||
                     (m.message >= WM_LBUTTONDOWN && m.message <= WM_MBUTTONDBLCLK)) {
                const MSG real = m;
                hover_active = false; drop_pending_x();
                pending.push_front(real);
                m = MSG{}; m.hwnd = game_window ? game_window : real.hwnd; m.message = WM_KEYUP; m.wParam = 'X';
                m.lParam = key_lparam(ScanX,false,true,false); m.time = real.time; m.pt = real.pt;
                ++hover_releases; ++preempted_releases;
                return;
            }
        }
    }
    if (options.wheel && m.message == WM_MOUSEWHEEL) {
        const int delta = GET_WHEEL_DELTA_WPARAM(m.wParam);
        // Ctrl+wheel = zoom: the real Ctrl is held, so a PgUp/PgDn press reaches the game as ctrl+pageup (zoom_in)
        // or ctrl+pagedown (zoom_out) in the default keymap. Wheel up = zoom in. (authorized 2026-11-11)
        const bool zoom = key_state_down(VK_CONTROL) && !key_state_down(VK_SHIFT) && !key_state_down(VK_MENU);
        if (!zoom && modifier_down()) { ++wheel_skipped_modifier; return; }
        // Without modifiers: wheel down = next page = PgUp in the default keymap.
        const bool prior = zoom ? delta > 0 : delta < 0;
        const UINT vk = prior ? VK_PRIOR : VK_NEXT, scan = prior ? ScanPrior : ScanNext;
        int notches = std::abs(delta) / WHEEL_DELTA; if (notches < 1) notches = 1; if (notches > 4) notches = 4;
        const HWND hwnd = m.hwnd ? m.hwnd : game_window;
        for (int i = 0; i < notches; ++i) { queue_key(hwnd,vk,scan,true,false); queue_key(hwnd,vk,scan,true,true); }
        (zoom ? wheel_zoom : wheel_pages) += notches;
        m.message = WM_NULL; m.wParam = 0; m.lParam = 0;   // the queued keys follow on the next PeekMessage
    }
}

std::string table(const char* key, std::atomic<long>* values) {
    std::string out;
    for (int i = 0; i < 256; ++i) if (const long v = values[i].exchange(0)) {
        out += out.empty() ? "" : ",";
        out += "\"" + std::to_string(i) + "\":" + std::to_string(v);
    }
    return out.empty() ? std::string() : "\"" + std::string(key) + "\":{" + out + "}";
}
}

void configure(const Options& o) { options = o; }
bool any_enabled() { return options.probe || options.wheel || options.hover; }

BOOL WINAPI peek_hook(LPMSG msg, HWND hwnd, UINT min, UINT max, UINT remove) {
    if (options.probe) ++peek_calls;
    if (msg && (options.wheel || options.hover)) {
        update_hover();
        if (!pending.empty() && in_filter(pending.front(),min,max)) {
            *msg = pending.front();
            if (remove & PM_REMOVE) { pending.pop_front(); if (options.probe) observe(*msg); }
            return TRUE;
        }
    }
    const BOOL got = peek_original(msg,hwnd,min,max,remove);
    if (got && msg && (remove & PM_REMOVE)) {
        if (options.probe) observe(*msg);
        if (options.wheel || options.hover) transform(*msg);
    }
    return got;
}
BOOL WINAPI get_hook(LPMSG msg, HWND hwnd, UINT min, UINT max) {
    if (msg && (options.wheel || options.hover) && !pending.empty() && in_filter(pending.front(),min,max)) {
        *msg = pending.front(); pending.pop_front();
        if (options.probe) observe(*msg);
        return TRUE;
    }
    const BOOL got = get_original(msg,hwnd,min,max);
    if (options.probe) ++get_calls;
    if (got > 0 && msg) {
        if (options.probe) observe(*msg);
        if (options.wheel || options.hover) transform(*msg);
    }
    return got;
}
SHORT WINAPI async_hook(int vk) {
    const SHORT r = async_original(vk);
    if (options.probe && vk >= 0 && vk < 256) { ++async_calls[vk]; if (r & 0x8000) ++async_down[vk]; }
    return r;
}
SHORT WINAPI state_hook(int vk) {
    const SHORT r = state_original(vk);
    if (options.probe && vk >= 0 && vk < 256) ++state_calls[vk];
    return r;
}
BOOL WINAPI board_hook(PBYTE keys) {
    if (options.probe) ++board_calls;
    const BOOL ok = board_original(keys);
    // The synthetic hold also shows in the polled key-state array (HYPOTHESIS: the game may poll X here).
    if (ok && keys && hover_active) { keys['X'] |= 0x80; ++board_overrides; }
    return ok;
}

std::string drain_fields() {
    std::string out;
    const auto add = [&](const std::string& field) { if (field.empty()) return; if (!out.empty()) out += ','; out += field; };
    const auto count = [&](const char* key, std::atomic<long>& v) { if (const long n = v.exchange(0)) add("\"" + std::string(key) + "\":" + std::to_string(n)); };
    count("wheel_pages",wheel_pages); count("wheel_zoom",wheel_zoom); count("wheel_skipped_modifier",wheel_skipped_modifier);
    count("hover_presses",hover_presses); count("hover_releases",hover_releases);
    count("chars_suppressed",chars_suppressed); count("modifier_releases",modifier_releases); count("preempted_releases",preempted_releases); count("board_overrides",board_overrides);
    if (options.probe) {
        count("peek_calls",peek_calls); count("get_calls",get_calls); count("keyboard_state_calls",board_calls);
        count("mouse_move",mouse_move); count("char",char_msgs);
        count("wheel_msgs",wheel_msgs); count("wheel_delta",wheel_delta); count("hwheel_msgs",hwheel_msgs);
        {   std::string b;
            for (int i = 0; i < 10; ++i) if (const long n = buttons[i].exchange(0)) {
                b += b.empty() ? "" : ","; b += "\"" + std::to_string(WM_LBUTTONDOWN+i) + "\":" + std::to_string(n); }
            if (!b.empty()) add("\"buttons\":{" + b + "}"); }
        add(table("keydown",keydown)); add(table("keyup",keyup));
        add(table("async_calls",async_calls)); add(table("async_down",async_down)); add(table("state_calls",state_calls));
        {   std::lock_guard<std::mutex> lock(sample_lock);
            if (!samples.empty()) {
                std::string s;
                for (const auto& x : samples) { s += s.empty() ? "" : ","; s += x; }
                samples.clear();
                add("\"samples\":[" + s + "]");
            } }
        if (!out.empty()) add("\"dinput_loaded\":" + std::string(GetModuleHandleW(L"dinput.dll") ? "true" : "false"));
    }
    return out;
}
}
