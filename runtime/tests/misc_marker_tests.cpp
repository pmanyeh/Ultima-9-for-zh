#include "misc_marker.h"
#include <iostream>
#include <stdexcept>
#include <string>

int main() {
    using namespace u9cht;
    auto check = [](bool v, const char* what) { if (!v) throw std::runtime_error(what); };
    // Synthetic plans: slot strings only (0x7F = one CJK scalar), no game text.
    const std::string plans[] = {"\x7F\x7F", "\x7F\x7F\x7F: ", "AB\x7F"};
    auto slots = [&](uint32_t plan, uint32_t& length) -> const uint8_t* {
        if (plan >= 3) return nullptr;
        length = uint32_t(plans[plan].size());
        return reinterpret_cast<const uint8_t*>(plans[plan].data());
    };
    auto marked = [](uint32_t plan) { char m[4]; encode_misc_marker(plan,m); return std::string(m,4); };
    try {
        // Round trip across the whole digit range.
        for (uint32_t plan : {0u, 1u, 93u, 94u, 8835u, 16383u, MiscMarkerLimit-1}) {
            char m[4]; check(encode_misc_marker(plan,m),"encode");
            uint32_t back = 0;
            check(decode_misc_marker(reinterpret_cast<uint8_t*>(m),4,back) && back == plan,"decode round trip");
            for (char c : std::string(m+1,3)) check(c >= 0x21 && c <= 0x7E,"printable digits");
        }
        { char m[4]; check(!encode_misc_marker(MiscMarkerLimit,m),"limit"); }
        // Every marker byte must survive the native draw-string routine (no byte below 0x20).
        { char m[4]; encode_misc_marker(12345,m); for (char c : std::string(m,4)) check(uint8_t(c) >= 0x20,"printable marker"); }

        // Concatenated page: two markers, ASCII between them and digits directly after a plan.
        std::string page = "\x0C" + marked(1) + plans[1] + "30/30\n" + marked(0) + plans[0] + "-";
        page.push_back('\0');
        auto* bytes = reinterpret_cast<uint8_t*>(page.data());
        auto r = strip_misc_markers(bytes,uint32_t(page.size()-1),slots);
        const std::string expect = "\x0C" + plans[1] + "30/30\n" + plans[0] + "-";
        check(r.markers == 2 && r.invalid == 0 && r.partial == 0,"page counters");
        check(r.length == expect.size() && std::string(page.c_str()) == expect,"page strip in place");
        check(r.segments.size() == 2 && r.segments[0].offset == 1 && r.segments[0].plan == 1 &&
              r.segments[0].length == plans[1].size(),"first segment");
        check(r.segments[1].offset == 1+plans[1].size()+6 && r.segments[1].plan == 0 &&
              r.segments[1].length == 2,"second segment");

        // Truncated copy binds only the matching prefix.
        std::string cut = marked(1) + "\x7F\x7F"; cut.push_back('\0');
        r = strip_misc_markers(reinterpret_cast<uint8_t*>(cut.data()),uint32_t(cut.size()-1),slots);
        check(r.markers == 1 && r.partial == 1 && r.segments.size() == 1 && r.segments[0].length == 2 &&
              std::string(cut.c_str()) == "\x7F\x7F","truncated prefix");

        // Unknown plan, malformed digits and a lone lead byte stay untouched.
        std::string bad = marked(7) + "x" + std::string("\x8F\x20!!") + "\x8F"; bad.push_back('\0');
        const std::string before = bad;
        r = strip_misc_markers(reinterpret_cast<uint8_t*>(bad.data()),uint32_t(bad.size()-1),slots);
        check(r.markers == 0 && r.invalid == 3 && r.segments.empty() && bad == before,"invalid markers kept");

        // Already stripped text (a re-flowed buffer) is unchanged.
        std::string plain = plans[2] + " ok"; plain.push_back('\0');
        const std::string plain_before = plain;
        r = strip_misc_markers(reinterpret_cast<uint8_t*>(plain.data()),uint32_t(plain.size()-1),slots);
        check(r.markers == 0 && r.invalid == 0 && plain == plain_before,"plain unchanged");
        std::cout << "PASS: misc marker encode/decode, in-place strip, segments, truncation and malformed input\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
