// P11 review tool: plays one movie with the Chinese cues (and optional local reference cues) outside the game.
// U9ChtMovieViewer MOVIE.dat [--subs CUES.tsv] [--ref REFERENCE.tsv] [--font FONT.ttf|otf] [--scale N]
// Keys: Space pause, Left/Right -/+5 s, Up/Down -/+1 s, PageUp/PageDown previous/next cue, Home restart,
//       R or F5 reload the cue files, Esc quit.
#include "movie_player.h"
#include "glyph_cache.h"
#include <shellapi.h>
#include <cstdio>
#include <fstream>
#include <sstream>

namespace {
std::string read_file(const std::wstring& path) {
    std::ifstream f(path, std::ios::binary);
    std::ostringstream s; s << f.rdbuf(); return s.str();
}
void message(const std::wstring& text) { MessageBoxW(nullptr,text.c_str(),L"U9Cht Movie Viewer",MB_OK|MB_ICONINFORMATION); }
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    using namespace u9cht;
    int argc = 0; auto** argv = CommandLineToArgvW(GetCommandLineW(),&argc);
    std::wstring movie, subs, ref, font; int scale = 1;
    for (int i = 1; i < argc; ++i) {
        const std::wstring a = argv[i];
        if (a == L"--subs" && i+1 < argc) subs = argv[++i];
        else if (a == L"--ref" && i+1 < argc) ref = argv[++i];
        else if (a == L"--font" && i+1 < argc) font = argv[++i];
        else if (a == L"--scale" && i+1 < argc) scale = std::clamp(_wtoi(argv[++i]),1,3);
        else if (movie.empty()) movie = a;
    }
    if (movie.empty()) {
        message(L"Usage: U9ChtMovieViewer MOVIE.dat [--subs CUES.tsv] [--ref REFERENCE.tsv] [--font FONT] [--scale 1-3]\n\n"
                L"Space pause, Left/Right 5 s, Up/Down 1 s, PageUp/PageDown cue, Home restart, R/F5 reload, Esc quit.");
        return 2;
    }
    MovieStyle style; style.review = true;
    if (!font.empty()) {
        const auto data = read_file(font);
        try { style.font_family = font_family_from_sfnt({reinterpret_cast<const uint8_t*>(data.data()),data.size()}); }
        catch (...) { message(L"Font name table could not be read:\n"+font); return 1; }
        if (!AddFontResourceExW(font.c_str(),FR_PRIVATE,nullptr)) { message(L"Font could not be registered:\n"+font); return 1; }
    }
    MoviePlayer player;
    std::string error;
    if (!player.open(movie,error)) { message(L"Cannot play "+movie+L"\n"+std::wstring(error.begin(),error.end())); return 1; }
    player.set_style(style);
    auto load = [&] {
        uint32_t bad_subs = 0, bad_ref = 0;
        if (!subs.empty()) player.set_cues(parse_subtitles(read_file(subs),&bad_subs));
        if (!ref.empty()) player.set_reference(parse_subtitles(read_file(ref),&bad_ref));
        if (bad_subs || bad_ref) {
            wchar_t text[160]; swprintf_s(text,L"Skipped malformed cue lines: subtitles %u, reference %u",bad_subs,bad_ref);
            message(text);
        }
    };
    load();
    const std::wstring title = L"U9Cht Movie Viewer - " + movie;
    if (!player.create_window(nullptr,0,0,640*scale,480*scale,title.c_str())) return 1;
    player.set_key_handler([&](WPARAM key) {
        const double t = player.time();
        auto jump_cue = [&](bool next) {
            const auto ms = uint32_t(t*1000.0);
            const SubtitleCue* pick = nullptr;
            for (const auto& c : player.cues()) {
                if (c.movie != player.stem()) continue;
                if (next && c.start_ms > ms+50) { pick = &c; break; }
                if (!next && c.start_ms+800 < ms) pick = &c;
            }
            if (pick) player.seek(pick->start_ms/1000.0);
        };
        switch (key) {
        case VK_SPACE: player.pause(!player.paused()); break;
        case VK_LEFT: player.seek(t-5); break;
        case VK_RIGHT: player.seek(t+5); break;
        case VK_DOWN: player.seek(t-1); break;
        case VK_UP: player.seek(t+1); break;
        case VK_PRIOR: jump_cue(false); break;
        case VK_NEXT: jump_cue(true); break;
        case VK_HOME: player.seek(0); break;
        case 'R': case VK_F5: load(); InvalidateRect(player.window(),nullptr,FALSE); break;
        case VK_ESCAPE: PostQuitMessage(0); break;
        }
    });
    player.play();
    MSG msg;
    while (GetMessageW(&msg,nullptr,0,0) > 0) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    player.stop();
    player.destroy_window();
    if (!font.empty()) RemoveFontResourceExW(font.c_str(),FR_PRIVATE,nullptr);
    LocalFree(argv);
    return 0;
}
