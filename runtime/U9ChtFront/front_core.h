#pragma once
// The release's front page (U9Cht.exe): settings, finding the game, and installing the Chinese resources
// for one play session only. Everything here is UI-free and tested by tests/front_core_tests.cpp.
//
// Install model (same as the developer session tool, scripts/run_p8_0_session.py): before the game starts
// the four built FLX files replace the player's originals in <game>/static, after a verified backup and a
// receipt written BEFORE the first replacement; when the game ends they are put back and verified. A
// receipt left by a crash or power loss is resolved by recover() the next time the page starts.
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace u9cht::front {
namespace fs = std::filesystem;

struct Settings {
    std::wstring game_dir;          // front.ini [game] dir
    std::wstring font;              // u9cht.ini [font] file ("" = the release's default font)
    uint32_t letter_spacing = 2, line_spacing = 3;
    uint32_t features = 0;          // protocol.h Feature* bits
    uint32_t hover_delay_ms = 0;
    uint32_t width = 0, height = 0;  // front.ini [display]; 0 = keep the game's own setting
};
struct Resolution { uint32_t width = 0, height = 0; };
// The sizes the Chinese runtime draws at (engine.cpp: 20 px glyphs at 800x600, 40 px at 1600x1200). Any other
// size makes the runtime end the game safely (error 18, session at the front page 2026-11-12: 1024x768, 1280x960).
inline constexpr Resolution Resolutions[] = {{800, 600}, {1600, 1200}};
inline bool supported(Resolution r) {
    for (const auto& s : Resolutions) if (s.width == r.width && s.height == r.height) return true;
    return false;
}
// GameScreenWidth/Height in Options.ini ({0,0} when absent).
Resolution game_resolution(const fs::path& game);
// Sets Options.ini GameScreenWidth/Height and dxcfg.ini display=WxH (its @refresh is kept). Every other byte
// of both files stays as it is. The change is persistent, like changing it in the game's own options.
struct Result;
Result apply_resolution(const fs::path& game, Resolution r);
Settings default_settings();
// Missing files or keys keep the defaults; out-of-range values are clamped.
Settings load_settings(const fs::path& launcher_ini, const fs::path& front_ini);
// UTF-16LE with BOM, as GetPrivateProfile*W reads it (font paths may hold Chinese).
void save_settings(const Settings& s, const fs::path& launcher_ini, const fs::path& front_ini);

struct Manifest {
    bool ok = false;
    std::map<std::wstring, std::wstring> source, output;   // static file name -> SHA-256 (lowercase hex)
    uint64_t plans = 0;
};
Manifest read_manifest(const fs::path& build_manifest_json);
// Exposed for tests: the {"name": "hex", ...} object after "key":, or empty when absent/malformed.
std::map<std::wstring, std::wstring> json_hash_object(const std::string& json, const std::string& key);

enum class GameStatus { Ok, NotFound, ExeMismatch, WrapperMismatch, ResourceMismatch };
// ResourceMismatch: a static file matches neither the build's source nor its output.
GameStatus check_game(const fs::path& dir, const Manifest& m, std::wstring* detail = nullptr);
// Registry (GOG, Steam libraries, uninstall entries) and common folders; folders holding u9.exe, supported
// editions first.
std::vector<fs::path> find_game_candidates();
// "GOG", "Steam" or "" (no u9.exe, or an executable this release does not support).
std::wstring game_edition(const fs::path& dir);
// Library folders listed in a Steam libraryfolders.vdf text (exposed for tests).
std::vector<std::wstring> steam_library_paths(const std::string& vdf);

struct Result { bool ok = true; std::wstring message; };
// Undo an install whose receipt is in `backup`. Files changed by anything else are left alone and reported.
Result recover(const fs::path& game, const fs::path& backup);
Result install(const fs::path& game, const fs::path& data, const Manifest& m, const fs::path& backup);
}
