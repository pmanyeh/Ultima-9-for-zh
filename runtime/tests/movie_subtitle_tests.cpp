#include "subtitles.h"
#include <iostream>
#include <stdexcept>

int main() {
    using namespace u9cht;
    auto check = [](bool v, const char* what) { if (!v) throw std::runtime_error(what); };
    try {
        uint32_t bad = 0;
        const auto cues = parse_subtitles(
            "\xEF\xBB\xBF# synthetic cues\r\n"
            "intro\t5000\t7000\t第二句\r\n"
            "intro\t1000\t3500\t第一句\\n第二行\r\n"
            "ambush\t0\t900\tA\r\n"
            "\n"
            "intro\t9000\t8000\tend before start\n"
            "intro\t1x\t2000\tbad number\n"
            "intro\t1000\t2000\n"
            "intro\t1000\t2000\t\xFF\xFE\n", &bad);
        check(bad == 4, "malformed lines counted");
        check(cues.size() == 3, "valid cues kept");
        check(cues[0].movie == "ambush" && cues[1].start_ms == 1000 && cues[2].start_ms == 5000, "sorted per movie by start");
        check(cues[1].text == u"第一句\n第二行", "escaped line break and UTF-8");
        check(active_cues(cues,"intro",999).empty() && active_cues(cues,"intro",1000).size() == 1 &&
              active_cues(cues,"intro",3499).size() == 1 && active_cues(cues,"intro",3500).empty(), "half-open interval");
        check(active_cues(cues,"ambush",500).size() == 1 && active_cues(cues,"intro",500).empty(), "per movie");
        check(movie_stem(u".\\movies\\Intro.DAT") == "intro" && movie_stem(u"samhayne.dat") == "samhayne" &&
              movie_stem(u"C:/x/RAVEN") == "raven", "movie stem");
        std::u16string out;
        check(utf8_to_u16("\xF0\x9F\x98\x80",out) && out.size() == 2, "surrogate pair");
        check(!utf8_to_u16("\xC0\x80",out) && !utf8_to_u16("\xED\xA0\x80",out), "overlong and surrogate rejected");
        std::cout << "PASS: movie cue parsing, ordering, intervals, stems and UTF-8 validation\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
