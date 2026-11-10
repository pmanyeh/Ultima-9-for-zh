#include "clock_text.h"
#include <iostream>
#include <stdexcept>
#include <string>

int main() {
    using namespace u9cht;
    auto check = [](bool v, const char* what) { if (!v) throw std::runtime_error(what); };
    auto is = [](std::string_view en, std::u16string_view zh) { return clock_to_chinese(en) == zh; };
    try {
        // Every sentence shape the executable builds (strings at 0x7A8A38..0x7A8B54).
        check(is("It is seven in the morning.", u"現在是早上七點。"), "hour + morning");
        check(is("It is two in the afternoon.", u"現在是下午兩點。"), "two uses 兩");
        check(is("It is eleven in the evening.", u"現在是晚上十一點。"), "eleven + evening");
        check(is("It is midnight.", u"現在是午夜十二點。"), "midnight");
        check(is("It is noon.", u"現在是中午十二點。"), "noon");
        check(is("It is ten.", u"現在是十點。"), "hour without period");
        check(is("It is a quarter past seven in the morning.", u"現在是早上七點十五分。"), "quarter past");
        check(is("It is half past noon.", u"現在是中午十二點半。"), "half past");
        check(is("It is a quarter till eight in the evening.", u"現在差十五分就是晚上八點了。"), "quarter till");
        check(is("It is 3 minutes past seven in the morning.", u"現在是早上七點三分。"), "minutes past");
        check(is("It is 1 minute past midnight.", u"現在是午夜十二點一分。"), "one minute");
        check(is("It is 22 minutes till one in the afternoon.", u"現在差二十二分就是下午一點了。"), "minutes till");
        check(is("It is 10 minutes past two.", u"現在是兩點十分。"), "ten minutes");
        check(is("It is 14 minutes past two.", u"現在是兩點十四分。"), "fourteen");
        check(is("It is 30 minutes past nine.", u"現在是九點三十分。"), "thirty");
        // Not a clock sentence or malformed: the English stays.
        for (const char* bad : {"It is locked.", "It is 3 minute past seven.", "It is 1 minutes past seven.",
                                "It is 0 minutes past seven.", "It is 60 minutes past seven.", "It is seven in the night.",
                                "It is half past.", "It is seven", "Is it seven.", "It is twelve.", ""})
            check(clock_to_chinese(bad).empty(), bad);
        // Every produced scalar is in ClockScalars, and the Chinese is never longer in bytes than the English
        // (one slot byte per scalar), so it always fits the holder's copy of the English.
        const std::u16string allowed = ClockScalars;
        const char* hours[] = {"midnight","noon","one","two","three","four","five","six","seven","eight","nine","ten","eleven"};
        const char* periods[] = {""," in the morning"," in the afternoon"," in the evening"};
        uint32_t checked = 0;
        for (const char* h : hours) for (const char* p : periods) {
            const std::string hour = std::string(h) + ((std::string(h) == "midnight" || std::string(h) == "noon") ? "" : p);
            std::string sentences[] = {"It is "+hour+".", "It is a quarter past "+hour+".", "It is half past "+hour+".",
                                       "It is a quarter till "+hour+"."};
            for (const auto& en : sentences) {
                const auto zh = clock_to_chinese(en); check(!zh.empty(), en.c_str());
                for (auto c : zh) check(allowed.find(c) != std::u16string::npos, "scalar outside ClockScalars");
                check(zh.size() <= en.size(), "Chinese longer than English"); ++checked;
            }
            for (uint32_t m = 1; m <= 59; ++m) for (const char* dir : {"past","till"}) {
                const std::string en = "It is "+std::to_string(m)+(m == 1 ? " minute " : " minutes ")+dir+" "+hour+".";
                const auto zh = clock_to_chinese(en); check(!zh.empty(), en.c_str());
                for (auto c : zh) check(allowed.find(c) != std::u16string::npos, "scalar outside ClockScalars");
                check(zh.size() <= en.size(), "Chinese longer than English"); ++checked;
            }
        }
        std::cout << "PASS: clock sentences (" << checked << " generated), malformed input, scalar set, length bound\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
