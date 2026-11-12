// U9Cht.exe: the release's front page. One window that finds the game, holds the player's settings,
// applies the Chinese resources for one session, starts U9ChtLauncher.exe and puts the originals back
// when the game ends. Drawn with GDI; no extra dependency.
//
// Folder layout (all beside U9Cht.exe unless overridden on the command line):
//   U9ChtLauncher.exe, U9ChtRuntime.dll   --runtime DIR
//   data\  (build_localization.py output)  --data DIR
//   fonts\ (default font: the first .ttf/.otf/.ttc)
//   u9cht.ini, front.ini, backup\, logs\   --base DIR
// Test: --screenshot FILE.bmp draws the page once and exits.
#include "front_core.h"
#include "platform.h"
#include "protocol.h"
#include "version_manifest.h"
#include <commdlg.h>
#include <shellapi.h>
#include <shlobj.h>
#include <algorithm>
#include <ctime>
#include <thread>

using namespace u9cht;
using namespace u9cht::front;

namespace {
constexpr UINT WM_GAME_ENDED = WM_APP + 1;
constexpr wchar_t IssuesUrl[] = L"https://github.com/pmanyeh/Ultima-9-for-zh/issues";
constexpr COLORREF Background = RGB(27, 21, 16), Gold = RGB(226, 180, 90), Text = RGB(232, 220, 200),
                   Muted = RGB(154, 143, 128), Line = RGB(107, 90, 58), Good = RGB(140, 200, 120),
                   Bad = RGB(230, 120, 100), Button = RGB(42, 33, 25), ButtonHot = RGB(66, 52, 36);
constexpr int Width = 900, Height = 716;

enum Id {
    None, BrowseGame, SearchGame, Hover, DelayMinus, DelayPlus, Wheel, Zoom, Movies,
    FontPick, FontDefault, LetterMinus, LetterPlus, LineMinus, LinePlus, ResPrev, ResNext, Start, Help, Report, Quit
};
struct Hit { RECT r; Id id; bool enabled; };

struct App {
    fs::path base, data, runtime, fonts;
    Settings s;
    Manifest manifest;
    GameStatus game = GameStatus::NotFound;
    std::wstring game_detail, message;
    bool message_bad = false, running = false;
    HWND window = nullptr;
    std::vector<Hit> hits;
    Id hot = None;
    int dpi = 96;
    fs::path launcher_ini() const { return base / L"u9cht.ini"; }
    fs::path front_ini() const { return base / L"front.ini"; }
    fs::path backup() const { return base / L"backup"; }
} app;

int S(int v) { return MulDiv(v, app.dpi, 96); }
std::wstring version_text() {
    std::string name = RuntimeName;
    const auto slash = name.find('/'), dash = name.find('-');
    return std::wstring(name.begin() + long(slash + 1), dash == std::string::npos ? name.end() : name.begin() + long(dash));
}
fs::path default_font() {
    std::error_code ec;
    if (!fs::is_directory(app.fonts, ec)) return {};
    std::vector<fs::path> fonts;
    for (const auto& e : fs::directory_iterator(app.fonts, ec)) {
        auto ext = e.path().extension().wstring();
        std::transform(ext.begin(), ext.end(), ext.begin(), towlower);
        if (ext == L".ttf" || ext == L".otf" || ext == L".ttc") fonts.push_back(e.path());
    }
    std::sort(fonts.begin(), fonts.end());
    return fonts.empty() ? fs::path() : fonts.front();
}
void save() {
    try { save_settings(app.s, app.launcher_ini(), app.front_ini()); }
    catch (...) { app.message = L"無法儲存設定（" + app.base.wstring() + L"）。"; app.message_bad = true; }
}
void refresh_game() {
    app.game_detail.clear();
    app.game = check_game(app.s.game_dir, app.manifest, &app.game_detail);
}
void search_game(bool keep_valid) {
    if (keep_valid && app.game == GameStatus::Ok) return;
    const auto found = find_game_candidates();
    if (!found.empty()) { app.s.game_dir = found.front().wstring(); refresh_game(); save(); }
}
std::wstring game_status_text(bool& ok) {
    ok = app.game == GameStatus::Ok;
    switch (app.game) {
    case GameStatus::Ok: return L"✔ 已找到遊戲，版本相符（GOG 版）";
    case GameStatus::NotFound: return app.s.game_dir.empty() ? L"✘ 找不到遊戲，請按「選擇資料夾」指定 Ultima 9 的安裝位置"
                                                              : L"✘ 這個資料夾裡沒有 u9.exe";
    case GameStatus::ExeMismatch: return L"✘ u9.exe 版本不符：目前只支援 GOG 版";
    case GameStatus::WrapperMismatch: return L"✘ ddraw.dll 不是 GOG 版附的版本";
    case GameStatus::ResourceMismatch: return L"✘ 遊戲檔案和中文化資料不相符：static\\" + app.game_detail;
    }
    return L"";
}

// ---- drawing ----
HFONT make_font(int px, int weight = FW_NORMAL) {
    return CreateFontW(-S(px), 0, 0, 0, weight, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                       CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Microsoft JhengHei UI");
}
struct Painter {
    HDC dc;
    HFONT title, heading, body, note;
    Painter(HDC d) : dc(d), title(make_font(28, FW_BOLD)), heading(make_font(17, FW_BOLD)), body(make_font(16)), note(make_font(14)) {
        SetBkMode(dc, TRANSPARENT);
    }
    ~Painter() { DeleteObject(title); DeleteObject(heading); DeleteObject(body); DeleteObject(note); }
    void text(int x, int y, int w, int h, const std::wstring& t, HFONT f, COLORREF c, UINT align = DT_LEFT) {
        RECT r{S(x), S(y), S(x + w), S(y + h)};
        SelectObject(dc, f); SetTextColor(dc, c);
        DrawTextW(dc, t.c_str(), int(t.size()), &r, align | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS | DT_NOPREFIX);
    }
    void fill(int x, int y, int w, int h, COLORREF c) {
        RECT r{S(x), S(y), S(x + w), S(y + h)};
        HBRUSH b = CreateSolidBrush(c); FillRect(dc, &r, b); DeleteObject(b);
    }
    void frame(int x, int y, int w, int h, COLORREF c) {
        RECT r{S(x), S(y), S(x + w), S(y + h)};
        HBRUSH b = CreateSolidBrush(c); FrameRect(dc, &r, b); DeleteObject(b);
    }
    void button(int x, int y, int w, int h, const std::wstring& t, Id id, bool enabled = true, bool primary = false) {
        const bool hot = enabled && app.hot == id;
        fill(x, y, w, h, hot ? ButtonHot : Button);
        frame(x, y, w, h, !enabled ? RGB(70, 62, 52) : (hot || primary) ? Gold : Line);
        text(x, y, w, h, t, primary ? heading : body, enabled ? (primary ? Gold : Text) : RGB(110, 100, 90), DT_CENTER);
        app.hits.push_back({{S(x), S(y), S(x + w), S(y + h)}, id, enabled});
    }
    void check(int x, int y, const std::wstring& label, const std::wstring& detail, bool on, Id id, bool enabled) {
        const bool hot = enabled && app.hot == id;
        fill(x, y + 7, 18, 18, Button);
        frame(x, y + 7, 18, 18, hot ? Gold : Line);
        if (on) fill(x + 4, y + 11, 10, 10, enabled ? Gold : Muted);
        text(x + 28, y, 250, 32, label, body, enabled ? Text : Muted);
        text(x + 290, y, 300, 32, detail, this->note, Muted);
        app.hits.push_back({{S(x), S(y), S(x + 280), S(y + 32)}, id, enabled});
    }
    void stepper(int x, int y, const std::wstring& label, const std::wstring& value, Id minus, Id plus, bool enabled) {
        text(x, y, 90, 32, label, body, enabled ? Text : Muted);
        button(x + 92, y + 2, 28, 28, L"−", minus, enabled);
        text(x + 122, y, 70, 32, value, body, enabled ? Gold : Muted, DT_CENTER);
        button(x + 194, y + 2, 28, 28, L"＋", plus, enabled);
    }
    void heading_line(int y, const std::wstring& t) {
        text(40, y, 300, 26, t, heading, Gold);
        fill(40, y + 28, 820, 1, Line);
    }
};

void paint(HDC dc) {
    app.hits.clear();
    Painter p(dc);
    p.fill(0, 0, Width, Height, Background);
    p.text(0, 18, Width, 44, L"創世紀 IX：昇華　繁體中文版", p.title, Gold, DT_CENTER);
    p.text(0, 62, Width, 24, L"Ultima IX: Ascension　　版本 " + version_text() + L"　　非官方中文化", p.note, Muted, DT_CENTER);
    const bool idle = !app.running;

    p.heading_line(100, L"遊戲位置");
    p.fill(40, 138, 576, 32, RGB(20, 16, 12)); p.frame(40, 138, 576, 32, Line);
    p.text(50, 138, 560, 32, app.s.game_dir.empty() ? L"（尚未指定）" : app.s.game_dir, p.body, app.s.game_dir.empty() ? Muted : Text);
    p.button(628, 138, 112, 32, L"選擇資料夾…", BrowseGame, idle);
    p.button(748, 138, 112, 32, L"自動搜尋", SearchGame, idle);
    bool game_ok = false; const auto status = game_status_text(game_ok);
    p.text(40, 174, 820, 26, status, p.note, game_ok ? Good : Bad);

    p.heading_line(210, L"中文化資料");
    std::wstring data;
    if (!app.manifest.ok) data = L"✘ 找不到中文化資料（" + (app.data / L"build-manifest.json").wstring() + L"）";
    else data = L"✔ 已就緒：" + std::to_wstring(app.manifest.plans) + L" 條譯文。開始遊戲時套用，離開遊戲後自動還原原本的檔案。";
    p.text(40, 244, 820, 26, data, p.note, app.manifest.ok ? Good : Bad);

    p.heading_line(282, L"強化功能");
    const auto on = [](uint32_t bit) { return (app.s.features & bit) != 0; };
    p.check(44, 314, L"游標停留顯示名稱", L"不必按住 X，停在物品上就顯示名稱", on(FeatureHoverNames), Hover, idle);
    p.stepper(626, 314, L"延遲", std::to_wstring(app.s.hover_delay_ms) + L" ms", DelayMinus, DelayPlus, idle && on(FeatureHoverNames));
    p.check(44, 348, L"滾輪翻頁", L"日誌、法術書、書本", on(FeatureWheelPages), Wheel, idle);
    p.check(44, 382, L"Ctrl＋滾輪縮放鏡頭", L"往上拉近，往下拉遠", on(FeatureWheelZoom), Zoom, idle);
    p.check(44, 416, L"影片中文字幕", L"開場與劇情影片", on(FeatureMovieSubtitles), Movies, idle);

    p.heading_line(458, L"畫面與字型");
    const fs::path font(app.s.font);
    p.text(44, 492, 70, 32, L"字型", p.body, Text);
    p.text(114, 492, 500, 32, app.s.font.empty() ? L"（找不到字型）" : font.filename().wstring(), p.body, app.s.font.empty() ? Bad : Gold);
    p.button(628, 494, 112, 28, L"選擇字型…", FontPick, idle);
    p.button(748, 494, 112, 28, L"預設字型", FontDefault, idle);
    p.stepper(44, 528, L"日誌字距", std::to_wstring(app.s.letter_spacing), LetterMinus, LetterPlus, idle);
    p.stepper(340, 528, L"日誌行距", std::to_wstring(app.s.line_spacing), LineMinus, LinePlus, idle);
    {
        const auto now = game_resolution(app.s.game_dir);
        const auto size = [](uint32_t w, uint32_t h) { return std::to_wstring(w) + L"×" + std::to_wstring(h); };
        const std::wstring chosen = app.s.width ? size(app.s.width, app.s.height) : L"不變更";
        p.text(44, 564, 90, 32, L"解析度", p.body, idle ? Text : Muted);
        p.button(136, 566, 28, 28, L"◀", ResPrev, idle);
        p.text(166, 564, 120, 32, chosen, p.body, idle ? Gold : Muted, DT_CENTER);
        p.button(288, 566, 28, 28, L"▶", ResNext, idle);
        const bool usable = app.s.width || supported(now);
        std::wstring note = now.width ? L"目前遊戲設定：" + size(now.width, now.height) : L"讀不到遊戲的解析度設定";
        if (app.s.width) note += L"。開始遊戲時改成 " + chosen;
        else if (usable) note += L"。開始遊戲時不修改";
        else note += L"。中文化只支援 800×600 和 1600×1200，請改選";
        p.text(340, 564, 520, 32, note, p.note, usable ? Muted : Bad);
    }

    p.text(40, 606, 820, 26, app.running ? L"遊戲進行中……離開遊戲後會回到這裡並還原檔案。" : app.message, p.note,
           app.running ? Gold : app.message_bad ? Bad : Muted, DT_CENTER);
    const bool can_start = idle && game_ok && app.manifest.ok && !app.s.font.empty() &&
                           (app.s.width || supported(game_resolution(app.s.game_dir)));
    int x = 60;
    p.button(x, 644, 180, 46, L"開始遊戲", Start, can_start, true); x += 200;
    p.button(x, 644, 180, 46, L"說明", Help, true); x += 200;
    p.button(x, 644, 180, 46, L"回報問題", Report, true); x += 200;
    p.button(x, 644, 180, 46, L"結束", Quit, idle);
}

// ---- actions ----
std::wstring pick_folder(HWND owner) {
    std::wstring result;
    IFileOpenDialog* dialog = nullptr;
    if (FAILED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&dialog)))) return result;
    DWORD options = 0; dialog->GetOptions(&options);
    dialog->SetOptions(options | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM);
    dialog->SetTitle(L"選擇 Ultima 9 的安裝資料夾（裡面有 u9.exe）");
    if (SUCCEEDED(dialog->Show(owner))) {
        IShellItem* item = nullptr;
        if (SUCCEEDED(dialog->GetResult(&item))) {
            PWSTR path = nullptr;
            if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path))) { result = path; CoTaskMemFree(path); }
            item->Release();
        }
    }
    dialog->Release();
    return result;
}
std::wstring pick_font(HWND owner) {
    wchar_t file[MAX_PATH]{};
    OPENFILENAMEW o{}; o.lStructSize = sizeof(o); o.hwndOwner = owner;
    o.lpstrFilter = L"字型檔 (*.ttf;*.otf;*.ttc)\0*.ttf;*.otf;*.ttc\0";
    o.lpstrFile = file; o.nMaxFile = MAX_PATH; o.lpstrTitle = L"選擇中文字型";
    o.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    return GetOpenFileNameW(&o) ? std::wstring(file) : std::wstring();
}
std::wstring stamp() {
    const auto t = std::time(nullptr); tm local{}; localtime_s(&local, &t);
    wchar_t text[32]; wcsftime(text, std::size(text), L"%Y%m%d-%H%M%S", &local);
    return text;
}
void set_message(const std::wstring& text, bool bad) { app.message = text; app.message_bad = bad; }

void start_game() {
    if (app.running) return;
    if (!app.manifest.ok) { set_message(L"找不到中文化資料，無法開始。", true); return; }
    if (app.s.font.empty()) { set_message(L"請先選擇中文字型。", true); return; }
    const auto undo = recover(app.s.game_dir, app.backup());
    if (!undo.ok) { set_message(undo.message, true); return; }
    refresh_game();
    if (app.game != GameStatus::Ok) { set_message(L"遊戲檢查沒有通過，無法開始。", true); return; }
    save();
    const auto launcher = app.runtime / L"U9ChtLauncher.exe", dll = app.runtime / L"U9ChtRuntime.dll";
    const auto pack = app.data / L"runtime" / L"allowlist.u9ct";
    std::error_code ec;
    if (!fs::is_regular_file(launcher, ec) || !fs::is_regular_file(dll, ec) || !fs::is_regular_file(pack, ec)) {
        set_message(L"程式檔不完整：找不到 U9ChtLauncher.exe、U9ChtRuntime.dll 或 allowlist.u9ct。", true); return;
    }
    if (!app.s.width && !supported(game_resolution(app.s.game_dir))) {
        set_message(L"遊戲目前的解析度中文化不支援，請選 800×600 或 1600×1200。", true); return;
    }
    if (const auto res = apply_resolution(app.s.game_dir, {app.s.width, app.s.height}); !res.ok) { set_message(res.message, true); return; }
    const auto installed = install(app.s.game_dir, app.data, app.manifest, app.backup());
    if (!installed.ok) { set_message(installed.message, true); return; }
    fs::create_directories(app.base / L"logs", ec);
    const auto name = stamp();
    const auto log = app.base / L"logs" / (name + L".jsonl");
    const auto err = app.base / L"logs" / (name + L"-launcher.txt");
    std::wstring command = L"\"" + launcher.wstring() + L"\" --game-dir \"" + app.s.game_dir + L"\" --runtime \"" + dll.wstring() +
        L"\" --log \"" + log.wstring() + L"\" --mode render --allowlist \"" + pack.wstring() + L"\" --config \"" +
        app.launcher_ini().wstring() + L"\"";
    SECURITY_ATTRIBUTES sa{sizeof(sa), nullptr, TRUE};
    HANDLE out = CreateFileW(err.c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    STARTUPINFOW si{}; si.cb = sizeof(si);
    if (out != INVALID_HANDLE_VALUE) { si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = out; si.hStdError = out; }
    PROCESS_INFORMATION pi{};
    const BOOL ok = CreateProcessW(launcher.c_str(), command.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr,
                                   app.runtime.c_str(), &si, &pi);
    if (out != INVALID_HANDLE_VALUE) CloseHandle(out);
    if (!ok) {
        const auto r = recover(app.s.game_dir, app.backup());
        set_message(L"無法啟動 U9ChtLauncher.exe。" + std::wstring(r.ok ? L"" : L" " + r.message), true); return;
    }
    CloseHandle(pi.hThread);
    app.running = true; set_message(L"", false);
    ShowWindow(app.window, SW_MINIMIZE);
    std::thread([process = pi.hProcess, window = app.window] {
        WaitForSingleObject(process, INFINITE);
        DWORD code = 0; GetExitCodeProcess(process, &code); CloseHandle(process);
        PostMessageW(window, WM_GAME_ENDED, code, 0);
    }).detach();
}
void game_ended(DWORD code) {
    app.running = false;
    const auto r = recover(app.s.game_dir, app.backup());
    refresh_game();
    if (!r.ok) set_message(r.message, true);
    else if (code == 2) set_message(L"中文化程式沒有成功啟動遊戲，遊戲檔案已還原。詳細原因在 logs 資料夾。", true);
    else set_message(L"遊戲已結束，已還原遊戲原本的檔案。", false);
    ShowWindow(app.window, SW_RESTORE); SetForegroundWindow(app.window);
}
void act(Id id) {
    auto& s = app.s;
    const auto toggle = [&](uint32_t bit) { s.features ^= bit; };
    switch (id) {
    case BrowseGame: { const auto dir = pick_folder(app.window); if (!dir.empty()) { s.game_dir = dir; refresh_game(); } break; }
    case SearchGame: {
        const auto found = find_game_candidates();
        if (found.empty()) set_message(L"自動搜尋沒有找到 Ultima 9，請用「選擇資料夾」指定。", true);
        else { s.game_dir = found.front().wstring(); refresh_game(); set_message(L"找到：" + s.game_dir, false); }
        break;
    }
    case Hover: toggle(FeatureHoverNames); break;
    case Wheel: toggle(FeatureWheelPages); break;
    case Zoom: toggle(FeatureWheelZoom); break;
    case Movies: toggle(FeatureMovieSubtitles); break;
    case DelayMinus: s.hover_delay_ms = std::max(MinHoverDelayMs, s.hover_delay_ms - 50); break;
    case DelayPlus: s.hover_delay_ms = std::min(MaxHoverDelayMs, s.hover_delay_ms + 50); break;
    case LetterMinus: if (s.letter_spacing) --s.letter_spacing; break;
    case LetterPlus: s.letter_spacing = std::min(MaxJournalLetterSpacing, s.letter_spacing + 1); break;
    case LineMinus: if (s.line_spacing) --s.line_spacing; break;
    case LinePlus: s.line_spacing = std::min(MaxJournalLineSpacing, s.line_spacing + 1); break;
    case ResPrev: case ResNext: {
        // Index -1 = keep the game's own setting, then the offered sizes in order.
        const int count = int(std::size(Resolutions));
        int i = -1;
        for (int k = 0; k < count; ++k) if (Resolutions[k].width == s.width && Resolutions[k].height == s.height) i = k;
        i = (id == ResNext ? i + 1 + 1 : i - 1 + 1 + count + 1) % (count + 1) - 1;
        s.width = i < 0 ? 0 : Resolutions[i].width; s.height = i < 0 ? 0 : Resolutions[i].height;
        break;
    }
    case FontPick: { const auto f = pick_font(app.window); if (!f.empty()) s.font = f; break; }
    case FontDefault: s.font = default_font().wstring(); break;
    case Start: start_game(); break;
    case Help: {
        const auto help = app.base / L"說明.txt";
        std::error_code ec;
        if (fs::is_regular_file(help, ec)) ShellExecuteW(app.window, L"open", help.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
        else set_message(L"找不到說明檔：" + help.wstring(), true);
        return;
    }
    case Report: ShellExecuteW(app.window, L"open", IssuesUrl, nullptr, nullptr, SW_SHOWNORMAL); return;
    case Quit: DestroyWindow(app.window); return;
    default: return;
    }
    if (id != Start) save();
}

LRESULT CALLBACK proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps; HDC dc = BeginPaint(hwnd, &ps);
        RECT r; GetClientRect(hwnd, &r);
        HDC mem = CreateCompatibleDC(dc);
        HBITMAP bmp = CreateCompatibleBitmap(dc, r.right, r.bottom);
        auto old = SelectObject(mem, bmp);
        paint(mem);
        BitBlt(dc, 0, 0, r.right, r.bottom, mem, 0, 0, SRCCOPY);
        SelectObject(mem, old); DeleteObject(bmp); DeleteDC(mem);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_MOUSEMOVE: {
        const POINT pt{short(LOWORD(lp)), short(HIWORD(lp))};
        Id hot = None;
        for (const auto& h : app.hits) if (h.enabled && PtInRect(&h.r, pt)) hot = h.id;
        if (hot != app.hot) { app.hot = hot; InvalidateRect(hwnd, nullptr, FALSE); }
        SetCursor(LoadCursorW(nullptr, hot ? IDC_HAND : IDC_ARROW));
        TRACKMOUSEEVENT t{sizeof(t), TME_LEAVE, hwnd, 0}; TrackMouseEvent(&t);
        return 0;
    }
    case WM_MOUSELEAVE: if (app.hot) { app.hot = None; InvalidateRect(hwnd, nullptr, FALSE); } return 0;
    case WM_SETCURSOR: if (LOWORD(lp) == HTCLIENT) return TRUE; break;
    case WM_LBUTTONUP: {
        const POINT pt{short(LOWORD(lp)), short(HIWORD(lp))};
        for (const auto& h : app.hits) if (h.enabled && PtInRect(&h.r, pt)) { act(h.id); break; }
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE && !app.running) DestroyWindow(hwnd);
        if (wp == VK_RETURN) { act(Start); InvalidateRect(hwnd, nullptr, FALSE); }
        return 0;
    case WM_GAME_ENDED: game_ended(DWORD(wp)); InvalidateRect(hwnd, nullptr, FALSE); return 0;
    case WM_DPICHANGED: {
        app.dpi = HIWORD(wp);
        const auto* r = reinterpret_cast<RECT*>(lp);
        SetWindowPos(hwnd, nullptr, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_NOZORDER | SWP_NOACTIVATE);
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }
    case WM_CLOSE: if (app.running) return 0; break;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

bool save_bitmap(HDC dc, HBITMAP bmp, int w, int h, const fs::path& file) {
    BITMAPINFOHEADER info{sizeof(info), w, -h, 1, 24, BI_RGB};
    const int stride = (w * 3 + 3) & ~3;
    std::vector<unsigned char> pixels(size_t(stride) * size_t(h));
    if (!GetDIBits(dc, bmp, 0, UINT(h), pixels.data(), reinterpret_cast<BITMAPINFO*>(&info), DIB_RGB_COLORS)) return false;
    BITMAPFILEHEADER head{0x4D42, DWORD(sizeof(BITMAPFILEHEADER) + sizeof(info) + pixels.size()), 0, 0,
                          DWORD(sizeof(BITMAPFILEHEADER) + sizeof(info))};
    HANDLE f = CreateFileW(file.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    const bool ok = WriteFile(f, &head, sizeof(head), &written, nullptr) && WriteFile(f, &info, sizeof(info), &written, nullptr) &&
                    WriteFile(f, pixels.data(), DWORD(pixels.size()), &written, nullptr);
    CloseHandle(f);
    return ok;
}
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int show) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    const fs::path exe_dir = fs::path(module_path(nullptr)).parent_path();
    app.base = app.data = app.runtime = exe_dir;
    app.data = exe_dir / L"data";
    fs::path screenshot;
    int argc = 0;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    for (int i = 1; argv && i + 1 < argc; i += 2) {
        const std::wstring key = argv[i];
        if (key == L"--base") app.base = argv[i + 1];
        else if (key == L"--data") app.data = argv[i + 1];
        else if (key == L"--runtime") app.runtime = argv[i + 1];
        else if (key == L"--screenshot") screenshot = argv[i + 1];
    }
    if (argv) LocalFree(argv);
    std::error_code ec;
    app.base = fs::absolute(app.base, ec); app.data = fs::absolute(app.data, ec); app.runtime = fs::absolute(app.runtime, ec);
    app.fonts = exe_dir / L"fonts";
    if (!fs::is_directory(app.fonts, ec)) app.fonts = app.base / L"fonts";
    fs::create_directories(app.base, ec);

    app.s = load_settings(app.launcher_ini(), app.front_ini());
    if (app.s.font.empty() || !fs::is_regular_file(app.s.font, ec)) app.s.font = default_font().wstring();
    app.manifest = read_manifest(app.data / L"build-manifest.json");
    if (!app.s.game_dir.empty()) {
        const auto undo = recover(app.s.game_dir, app.backup());   // a session cut short by a crash or power loss
        if (!undo.ok) set_message(undo.message, true);
        else if (!undo.message.empty()) set_message(L"上次沒有正常結束，" + undo.message, false);
    }
    refresh_game();
    search_game(true);

    WNDCLASSEXW wc{sizeof(wc)};
    wc.lpfnWndProc = proc; wc.hInstance = instance; wc.lpszClassName = L"U9ChtFront";
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hIcon = LoadIconW(nullptr, IDI_APPLICATION);
    RegisterClassExW(&wc);
    const DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    app.dpi = int(GetDpiForSystem());
    RECT r{0, 0, S(Width), S(Height)};
    AdjustWindowRectExForDpi(&r, style, FALSE, 0, UINT(app.dpi));
    app.window = CreateWindowExW(0, wc.lpszClassName, L"創世紀 IX 繁體中文版", style, CW_USEDEFAULT, CW_USEDEFAULT,
                                 r.right - r.left, r.bottom - r.top, nullptr, nullptr, instance, nullptr);
    if (!app.window) return 1;
    app.dpi = int(GetDpiForWindow(app.window));

    if (!screenshot.empty()) {
        app.dpi = 96;
        HDC screen = GetDC(nullptr);
        HDC mem = CreateCompatibleDC(screen);
        HBITMAP bmp = CreateCompatibleBitmap(screen, Width, Height);
        auto old = SelectObject(mem, bmp);
        paint(mem);
        SelectObject(mem, old);
        const bool ok = save_bitmap(mem, bmp, Width, Height, screenshot);
        DeleteObject(bmp); DeleteDC(mem); ReleaseDC(nullptr, screen);
        DestroyWindow(app.window);
        return ok ? 0 : 1;
    }
    ShowWindow(app.window, show);
    UpdateWindow(app.window);
    MSG m;
    while (GetMessageW(&m, nullptr, 0, 0) > 0) { TranslateMessage(&m); DispatchMessageW(&m); }
    CoUninitialize();
    return 0;
}
