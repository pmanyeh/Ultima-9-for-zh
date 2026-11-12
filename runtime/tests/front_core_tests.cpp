// Front page core (U9ChtFront/front_core.h) on synthetic files only: no game asset is read.
#include "front_core.h"
#include "platform.h"
#include "protocol.h"
#include "version_manifest.h"
#include <fstream>
#include <iostream>

using namespace u9cht;
using namespace u9cht::front;
namespace {
int failures = 0;
void check(bool ok, const char* what) { if (!ok) { ++failures; std::cerr << "FAIL: " << what << '\n'; } }
void write(const fs::path& p, const std::string& data) {
    fs::create_directories(p.parent_path());
    std::ofstream(p, std::ios::binary | std::ios::trunc) << data;
}
std::string read(const fs::path& p) {
    std::ifstream in(p, std::ios::binary); return std::string(std::istreambuf_iterator<char>(in), {});
}
std::string hex(const fs::path& p) { return utf8(sha256(p)); }
}

int main() {
    const auto root = fs::temp_directory_path() / L"u9cht-front-tests";
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(root);

    {   // JSON hash objects
        const std::string a(64, 'a'), b(64, 'b');
        const std::string json = "{\"x\": 1, \"source_game_sha256\": {\"text.flx\": \"" + a + "\", \"BOOKS-EN.FLX\": \"" + b +
                                 "\"}, \"runtime_plan_count\": 10083}";
        const auto m = json_hash_object(json, "source_game_sha256");
        check(m.size() == 2 && m.at(L"text.flx") == std::wstring(64, L'a'), "hash object parsed");
        check(json_hash_object(json, "missing").empty(), "missing key");
        check(json_hash_object("{\"k\": {\"a\": \"xyz\"}}", "k").empty(), "non-hash value rejected");
        check(json_hash_object("{\"k\": {\"a\": \"" + std::string(64, 'A') + "\"}}", "k").empty(), "uppercase hash rejected");
        write(root / L"m.json", "{\"source_game_sha256\": {\"text.flx\": \"" + a + "\"}, \"resource_output_sha256\": {\"text.flx\": \"" +
              b + "\"}, \"runtime_plan_count\": 10083}");
        const auto man = read_manifest(root / L"m.json");
        check(man.ok && man.plans == 10083, "manifest read");
        write(root / L"bad.json", "{\"source_game_sha256\": {\"a\": \"" + a + "\"}, \"resource_output_sha256\": {\"..\": \"" + b + "\"}}");
        check(!read_manifest(root / L"bad.json").ok, "unsafe or unmatched names rejected");
        check(!read_manifest(root / L"absent.json").ok, "absent manifest");
    }
    {   // Steam libraries and editions
        const std::string vdf = "\"libraryfolders\"\n{\n\t\"0\"\n\t{\n\t\t\"path\"\t\t\"C:\\\\Program Files (x86)\\\\Steam\"\n"
                                "\t\t\"label\"\t\t\"\"\n\t}\n\t\"1\"\n\t{\n\t\t\"path\"\t\t\"D:\\\\Steam \\\"Lib\\\"\"\n\t}\n}\n";
        const auto libs = steam_library_paths(vdf);
        check(libs.size() == 2 && libs[0] == L"C:\\Program Files (x86)\\Steam" && libs[1] == L"D:\\Steam \"Lib\"", "vdf library paths");
        check(steam_library_paths("").empty() && steam_library_paths("\"path\" \"unterminated").empty(), "vdf malformed");
        check(std::wstring(exe_edition(ExeHash)) == L"GOG" && std::wstring(exe_edition(SteamExeHash)) == L"Steam" &&
              std::wstring(exe_edition(std::wstring(64, L'0'))).empty() && known_exe(SteamExeHash), "editions");
        write(root / L"ed" / L"u9.exe", "not the game");
        check(game_edition(root / L"ed").empty() && game_edition(root / L"none").empty(), "unsupported or missing exe");
    }
    {   // Settings round trip, defaults and clamping
        const auto ini = root / L"u9cht.ini", front = root / L"front.ini";
        auto d = load_settings(ini, front);
        check(d.features == DefaultFeatures && d.hover_delay_ms == DefaultHoverDelayMs && d.letter_spacing == 2, "defaults");
        Settings s = d;
        s.game_dir = L"C:\\遊戲\\Ultima 9"; s.font = L"D:\\字型\\a.ttf"; s.letter_spacing = 4; s.line_spacing = 7;
        s.features = FeatureWheelZoom | FeatureMovieSubtitles; s.hover_delay_ms = 400;
        save_settings(s, ini, front);
        const auto t = load_settings(ini, front);
        check(t.game_dir == s.game_dir && t.font == s.font && t.letter_spacing == 4 && t.line_spacing == 7 &&
              t.features == s.features && t.hover_delay_ms == 400, "settings round trip (non-ASCII paths)");
        write(ini, "[journal]\r\nletter_spacing = 99\r\n[features]\r\nhover_delay_ms = 5\r\nwheel_pages = 7\r\n");
        const auto c = load_settings(ini, front);
        check(c.letter_spacing == MaxJournalLetterSpacing && c.hover_delay_ms == MinHoverDelayMs &&
              (c.features & FeatureWheelPages), "clamped and invalid values");
    }
    {   // Resolution: only the three values change, every other byte is kept
        const auto game = root / L"res";
        write(game / L"Options.ini", "[Video]\r\nGameScreenWidth=800\r\nGameScreenHeight=600\r\nGameScreenDepth=32\r\n");
        write(game / L"dxcfg.ini", "[general]\r\ndisplay=800x600@120\r\npresentation=windowed\r\n");
        const auto r = game_resolution(game);
        check(r.width == 800 && r.height == 600, "resolution read");
        check(apply_resolution(game, {1600, 1200}).ok, "resolution applied");
        check(read(game / L"Options.ini") == "[Video]\r\nGameScreenWidth=1600\r\nGameScreenHeight=1200\r\nGameScreenDepth=32\r\n" &&
              read(game / L"dxcfg.ini") == "[general]\r\ndisplay=1600x1200@120\r\npresentation=windowed\r\n", "only sizes changed");
        check(apply_resolution(game, {0, 0}).ok && game_resolution(game).width == 1600, "zero keeps the setting");
        write(game / L"dxcfg.ini", "[general]\r\ndisplay=desktop\r\npresentation=application\r\n");   // Steam release
        check(apply_resolution(game, {800, 600}).ok && game_resolution(game).width == 800 &&
              read(game / L"dxcfg.ini") == "[general]\r\ndisplay=desktop\r\npresentation=application\r\n", "desktop wrapper left as is");
        write(game / L"Options.ini", "[Video]\r\nGameScreenDepth=32\r\n");
        check(!apply_resolution(game, {1600, 1200}).ok && read(game / L"Options.ini") == "[Video]\r\nGameScreenDepth=32\r\n",
              "Options.ini without sizes refused untouched");
        check(game_resolution(root / L"nowhere").width == 0, "missing Options.ini");
        const auto ini = root / L"r-u9cht.ini", front = root / L"r-front.ini";
        auto s = default_settings(); s.width = 1600; s.height = 1200;
        save_settings(s, ini, front);
        check(load_settings(ini, front).width == 1600, "resolution choice saved");
        check(supported({800, 600}) && supported({1600, 1200}) && !supported({1024, 768}) && !supported({0, 0}), "supported sizes");
        write(front, "[display]\r\nwidth = 1234\r\nheight = 5\r\n");
        check(load_settings(ini, front).width == 0, "unoffered size ignored");
    }
    {   // Install and recover on a synthetic game folder
        const auto game = root / L"game", data = root / L"data", backup = root / L"backup";
        write(game / L"static" / L"text.flx", "english text");
        write(game / L"static" / L"TYPENAME.FLX", "english names");
        write(data / L"static" / L"text.flx", "chinese text");
        write(data / L"static" / L"TYPENAME.FLX", "chinese names");
        const std::string manifest = "{\"source_game_sha256\": {\"text.flx\": \"" + hex(game / L"static/text.flx") +
            "\", \"TYPENAME.FLX\": \"" + hex(game / L"static/TYPENAME.FLX") + "\"}, \"resource_output_sha256\": {\"text.flx\": \"" +
            hex(data / L"static/text.flx") + "\", \"TYPENAME.FLX\": \"" + hex(data / L"static/TYPENAME.FLX") + "\"}}";
        write(data / L"build-manifest.json", manifest);
        const auto m = read_manifest(data / L"build-manifest.json");
        check(m.ok, "synthetic manifest");
        check(check_game(game, m) == GameStatus::NotFound, "no u9.exe");
        check(recover(game, backup).ok, "nothing to recover");

        auto r = install(game, data, m, backup);
        check(r.ok && read(game / L"static/text.flx") == "chinese text" && read(game / L"static/TYPENAME.FLX") == "chinese names",
              "install replaces both files");
        check(fs::is_regular_file(backup / L"installed.txt"), "receipt written");
        check(!install(game, data, m, backup).ok, "second install refused while a receipt exists");
        r = recover(game, backup);
        check(r.ok && read(game / L"static/text.flx") == "english text" && read(game / L"static/TYPENAME.FLX") == "english names",
              "recover restores originals");
        check(!fs::exists(backup / L"installed.txt") && !fs::exists(backup / L"text.flx"), "backup cleared");

        // A file changed by something else after install is never overwritten.
        check(install(game, data, m, backup).ok, "install again");
        write(game / L"static" / L"text.flx", "patched by someone else");
        r = recover(game, backup);
        check(!r.ok && read(game / L"static/text.flx") == "patched by someone else" &&
              read(game / L"static/TYPENAME.FLX") == "english names", "foreign change kept, other file restored");
        check(fs::is_regular_file(backup / L"installed.txt") && read(backup / L"text.flx") == "english text", "backup kept on conflict");
        write(game / L"static" / L"text.flx", "english text");
        check(recover(game, backup).ok && !fs::exists(backup / L"installed.txt"), "recover after manual fix");

        // Version mismatch and damaged data are refused before anything changes.
        write(game / L"static" / L"text.flx", "other version");
        r = install(game, data, m, backup);
        check(!r.ok && read(game / L"static/TYPENAME.FLX") == "english names" && !fs::exists(backup / L"installed.txt"),
              "source mismatch refused");
        write(game / L"static" / L"text.flx", "english text");
        write(data / L"static" / L"text.flx", "damaged");
        r = install(game, data, m, backup);
        check(!r.ok && read(game / L"static/text.flx") == "english text", "damaged data refused");
    }
    fs::remove_all(root, ec);
    if (failures) { std::cerr << failures << " failure(s)\n"; return 1; }
    std::cout << "front core tests passed\n";
    return 0;
}
