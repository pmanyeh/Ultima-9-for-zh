#pragma once
// P10-2 clock message (CONFIRMED static, 0x654D00..0x655210): English time sentences built in the executable with
//   "It is %s."                 hour phrase
//   "It is %s %s."              "a quarter past" | "half past" | "a quarter till", hour phrase
//   "It is %d minute%s%s %s."   minutes, " " | "s ", "past" | "till", hour phrase   (till: the next hour, by the game)
// hour phrase = midnight | noon | one..eleven [+ " in the morning" | " in the afternoon" | " in the evening"].
// The sentence reaches the screen message holder (0x624680 -> copy 0x41BC61). clock_to_chinese() turns one such
// sentence into Traditional Chinese; anything else returns an empty string (the English stays).
// Header-only and free of game access: tested by clock_text_tests.cpp.
#include <array>
#include <cstdint>
#include <string>
#include <string_view>

namespace u9cht {
// Every CJK scalar clock_to_chinese() can produce. The pack carries a one-character plan for each
// (u9cht/l10n/runtime_pack.py CLOCK_SCALARS must equal this string).
inline constexpr char16_t ClockScalars[] = u"現在是差分就了。早上下午晚中夜點半十一二兩三四五六七八九";
inline constexpr uint32_t ClockMaxEnglish = 64;

namespace clock_detail {
inline bool take(std::string_view& s, std::string_view prefix) noexcept {
    if (s.substr(0,prefix.size()) != prefix) return false;
    s.remove_prefix(prefix.size()); return true;
}
// Chinese numeral 1..59; `hour` uses 兩 for 2.
inline std::u16string number(uint32_t n, bool hour) {
    static constexpr char16_t digits[] = u"零一二三四五六七八九";
    if (n == 2 && hour) return u"兩";
    std::u16string out;
    if (n >= 20) out += digits[n/10];
    if (n >= 10) out += u'十';
    if (n%10 || n < 10) out += digits[n%10];
    return out;
}
// Parses an hour phrase that must consume the whole view.
inline bool hour_phrase(std::string_view s, std::u16string& out) {
    static constexpr std::array<std::string_view,11> words{"one","two","three","four","five","six","seven","eight","nine","ten","eleven"};
    if (s == "midnight") { out = u"午夜十二點"; return true; }
    if (s == "noon") { out = u"中午十二點"; return true; }
    for (uint32_t i = 0; i < words.size(); ++i) {
        std::string_view rest = s;
        if (!take(rest,words[i])) continue;
        std::u16string period;
        if (rest.empty()) period.clear();
        else if (rest == " in the morning") period = u"早上";
        else if (rest == " in the afternoon") period = u"下午";
        else if (rest == " in the evening") period = u"晚上";
        else continue;
        out = period + number(i+1,true) + u"點";
        return true;
    }
    return false;
}
}

inline std::u16string clock_to_chinese(std::string_view en) {
    using namespace clock_detail;
    if (en.size() > ClockMaxEnglish || !take(en,"It is ") || en.size() < 2 || en.back() != '.') return {};
    en.remove_suffix(1);
    std::u16string hour;
    std::string_view s = en;
    if (take(s,"a quarter past ")) return hour_phrase(s,hour) ? u"現在是" + hour + u"十五分。" : std::u16string{};
    s = en;
    if (take(s,"half past ")) return hour_phrase(s,hour) ? u"現在是" + hour + u"半。" : std::u16string{};
    s = en;
    if (take(s,"a quarter till ")) return hour_phrase(s,hour) ? u"現在差十五分就是" + hour + u"了。" : std::u16string{};
    s = en;
    if (!s.empty() && s[0] >= '1' && s[0] <= '9') {
        uint32_t minutes = 0;
        while (!s.empty() && s[0] >= '0' && s[0] <= '9' && minutes < 100) { minutes = minutes*10 + uint32_t(s[0]-'0'); s.remove_prefix(1); }
        if (minutes < 1 || minutes > 59) return {};
        if (!take(s,minutes == 1 ? " minute " : " minutes ")) return {};
        const bool past = take(s,"past "), till = !past && take(s,"till ");
        if ((!past && !till) || !hour_phrase(s,hour)) return {};
        const auto m = number(minutes,false);
        return past ? u"現在是" + hour + m + u"分。" : u"現在差" + m + u"分就是" + hour + u"了。";
    }
    return hour_phrase(en,hour) ? u"現在是" + hour + u"。" : std::u16string{};
}
}
