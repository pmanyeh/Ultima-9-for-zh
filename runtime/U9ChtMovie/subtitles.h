#pragma once
// P11 movie subtitles: runtime cue file, generated from translation/zh-TW/movies.jsonl.
// UTF-8 text, one cue per line:  <movie>\t<start_ms>\t<end_ms>\t<text>
// <movie> is the file stem in lower case (for example "intro" for Movies\intro.dat). "\n" inside <text> is a
// line break. Empty lines and lines starting with '#' are ignored. Header-only; tested by movie_subtitle_tests.cpp.
#include <algorithm>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace u9cht {
struct SubtitleCue { std::string movie; uint32_t start_ms = 0, end_ms = 0; std::u16string text; };

inline bool utf8_to_u16(std::string_view in, std::u16string& out) {
    out.clear();
    for (size_t i = 0; i < in.size();) {
        const auto c = uint8_t(in[i]);
        uint32_t cp = 0; size_t n = 0;
        if (c < 0x80) { cp = c; n = 1; }
        else if ((c & 0xE0) == 0xC0) { cp = c & 0x1F; n = 2; }
        else if ((c & 0xF0) == 0xE0) { cp = c & 0x0F; n = 3; }
        else if ((c & 0xF8) == 0xF0) { cp = c & 0x07; n = 4; }
        else return false;
        if (i+n > in.size()) return false;
        for (size_t k = 1; k < n; ++k) {
            const auto t = uint8_t(in[i+k]);
            if ((t & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (t & 0x3F);
        }
        if ((n == 2 && cp < 0x80) || (n == 3 && cp < 0x800) || (n == 4 && cp < 0x10000) || cp > 0x10FFFF ||
            (cp >= 0xD800 && cp <= 0xDFFF)) return false;
        if (cp >= 0x10000) { cp -= 0x10000; out += char16_t(0xD800 + (cp >> 10)); out += char16_t(0xDC00 + (cp & 0x3FF)); }
        else out += char16_t(cp);
        i += n;
    }
    return true;
}

// Parses a cue file. Malformed lines are counted in `rejected` and skipped; cues are sorted per movie by start.
inline std::vector<SubtitleCue> parse_subtitles(std::string_view data, uint32_t* rejected = nullptr) {
    std::vector<SubtitleCue> cues; uint32_t bad = 0;
    if (data.substr(0,3) == "\xEF\xBB\xBF") data.remove_prefix(3);
    while (!data.empty()) {
        const auto nl = data.find('\n');
        std::string_view line = data.substr(0,nl);
        data = nl == std::string_view::npos ? std::string_view{} : data.substr(nl+1);
        if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
        if (line.empty() || line[0] == '#') continue;
        std::string_view f[4]; size_t k = 0;
        for (; k < 3; ++k) {
            const auto tab = line.find('\t');
            if (tab == std::string_view::npos) break;
            f[k] = line.substr(0,tab); line.remove_prefix(tab+1);
        }
        if (k != 3) { ++bad; continue; }
        f[3] = line;
        auto number = [](std::string_view s, uint32_t& v) {
            if (s.empty() || s.size() > 9) return false;
            v = 0; for (char c : s) { if (c < '0' || c > '9') return false; v = v*10 + uint32_t(c-'0'); }
            return true;
        };
        SubtitleCue cue; cue.movie = std::string(f[0]);
        std::string text; text.reserve(f[3].size());
        for (size_t i = 0; i < f[3].size(); ++i) {
            if (f[3][i] == '\\' && i+1 < f[3].size() && f[3][i+1] == 'n') { text += '\n'; ++i; }
            else text += f[3][i];
        }
        if (cue.movie.empty() || !number(f[1],cue.start_ms) || !number(f[2],cue.end_ms) || cue.end_ms <= cue.start_ms ||
            !utf8_to_u16(text,cue.text) || cue.text.empty()) { ++bad; continue; }
        cues.push_back(std::move(cue));
    }
    std::stable_sort(cues.begin(),cues.end(),[](const SubtitleCue& a, const SubtitleCue& b) {
        return a.movie != b.movie ? a.movie < b.movie : a.start_ms < b.start_ms;
    });
    if (rejected) *rejected = bad;
    return cues;
}

// Cues of one movie active at `ms` (start <= ms < end), in start order.
inline std::vector<const SubtitleCue*> active_cues(const std::vector<SubtitleCue>& cues, std::string_view movie, uint32_t ms) {
    std::vector<const SubtitleCue*> out;
    for (const auto& c : cues) if (c.movie == movie && c.start_ms <= ms && ms < c.end_ms) out.push_back(&c);
    return out;
}

// Lower-case file stem: ".\\movies\\Intro.DAT" -> "intro".
inline std::string movie_stem(std::u16string_view path) {
    size_t slash = path.find_last_of(u"\\/");
    std::u16string_view name = slash == std::u16string_view::npos ? path : path.substr(slash+1);
    const auto dot = name.find_last_of(u'.');
    if (dot != std::u16string_view::npos) name = name.substr(0,dot);
    std::string out;
    for (auto c : name) out += char(c < 128 ? (c >= 'A' && c <= 'Z' ? c+32 : c) : '_');
    return out;
}
}
