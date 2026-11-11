#include "identity.h"
#include "platform.h"
#include <fstream>
#include <memory>
#include <string>
#include <cstring>
#include <iostream>
#include <stdexcept>

int main() {
    using namespace u9cht;
    auto check = [](bool value) { if (!value) throw std::runtime_error("identity assertion failed"); };
    try {
        Registry r;
        auto* a = r.bind(0x1000,5,0); check(a != nullptr);
        const auto first = *a;
        auto* b = r.bind(0x2000,4,1); check(b && b->identity != first.identity);
        check(r.locate(0x1003).offset == 3 && r.locate(0x2000).binding->plan == 1);
        check(!r.locate(0x1004).binding); // NUL is not a scalar.
        auto* copied = r.bind(0x3000,5,0,first.identity);
        check(copied && copied->identity == first.identity && copied->generation != first.generation);
        check(!r.bind(0x3002,5,1)); // Ambiguous partial overlap rejected.
        check(r.retire(0x1000) && !r.locate(0x1000).binding);
        a = r.bind(0x1000,4,1);
        check(a && a->generation != first.generation && a->identity != first.identity && a->plan == 1);
        check(r.locate(0x3000).binding->identity == first.identity); // Copies have independent lifetime.
        check(r.retire(0x3000) && !r.retire(0x3000));
        check(!r.bind(0,5,0) && !r.bind(0xFFFFFFFE,8,0));
        check(r.count() == 2 && r.maximum == 3);
        r.clear(); check(r.count() == 0 && !r.locate(0x1000).binding);
        wchar_t temp_dir[MAX_PATH]{},temp_file[MAX_PATH]{};
        check(GetTempPathW(MAX_PATH,temp_dir) && GetTempFileNameW(temp_dir,L"u9t",0,temp_file));
        struct Cleanup { const wchar_t* path; ~Cleanup() { DeleteFileW(path); } } cleanup{temp_file};
        auto fixture = [](uint32_t count) {
            std::string out("U9CTP51\0",8);
            auto u32 = [&](uint32_t value) { out.append(reinterpret_cast<const char*>(&value),4); };
            u32(1); u32(count); out.append(64,'a'); return out;
        };
        auto append_plan = [](std::string& out, uint32_t id, const std::u16string& text) {
            const auto length = uint32_t(text.size());
            out.append(reinterpret_cast<const char*>(&id),4); out.append(reinterpret_cast<const char*>(&length),4);
            out.append(reinterpret_cast<const char*>(text.data()),text.size()*2);
        };
        auto write = [&](const std::string& bytes) { std::ofstream f(std::filesystem::path(temp_file),std::ios::binary); f.write(bytes.data(),bytes.size()); };
        auto bytes = fixture(2); append_plan(bytes,1,u"A中B"); append_plan(bytes,2,u"文中"); write(bytes);
        Pack pack; pack.load(temp_file,true);
        check(pack.match(L"A中B") == 0 && pack.plans[0].slots[1] == 0x7F && pack.plans[0].slots[0] == 'A');
        check(pack.match(L"unknown") == -1 && pack.plans[1].slots[1] == 0x7F);
        auto rejected = [&](const std::string& bad, bool render = true) {
            write(bad); Pack p;
            try { p.load(temp_file,render); return false; } catch (...) { return p.count == 0; }
        };
        check(rejected(bytes,false)); // Observe cannot carry opaque Unicode.
        check(rejected(bytes.substr(0,bytes.size()-1)) && rejected(bytes+"x"));
        auto duplicate = fixture(2); append_plan(duplicate,1,u"A"); append_plan(duplicate,1,u"B"); check(rejected(duplicate));
        auto ambiguous = fixture(2); append_plan(ambiguous,1,u"A"); append_plan(ambiguous,2,u"A"); check(rejected(ambiguous));
        auto invalid = fixture(1); append_plan(invalid,1,std::u16string(1,0xD800)); check(rejected(invalid));
        invalid = fixture(1); append_plan(invalid,1,u"你"); check(rejected(invalid));
        check(rejected(fixture(17)) && rejected(fixture(0)));
        auto showcase = [&]() {
            auto out = fixture(2); uint32_t v = 2;
            std::memcpy(out.data()+8,&v,4);
            const uint32_t glyphs[] = {2,0x4E2D,0x6587};
            out.append(reinterpret_cast<const char*>(glyphs),sizeof(glyphs));
            append_plan(out,1,u"A\u4E2D\n\u6587"); append_plan(out,2,u"\u6587\u4E2D");
            return out;
        };
        auto s = showcase(); write(s); pack.load(temp_file,true);
        check(pack.count == 2 && pack.glyph_count == 2 && pack.plans[0].slots[2] == '\n');
        check(pack.match(L"A\u4E2D\n\u6587") == 0 && rejected(s,false));
        check(rejected(s.substr(0,s.size()-1)) && rejected(s+"x"));
        auto bad = s; uint32_t value = MaxGlyphScalars+1;
        std::memcpy(bad.data()+80,&value,4); check(rejected(bad));
        bad = s; value = 0xD800; std::memcpy(bad.data()+84,&value,4); check(rejected(bad));
        bad = s; value = 0x4E2D; std::memcpy(bad.data()+88,&value,4); check(rejected(bad));
        bad = s; value = 0x6588; std::memcpy(bad.data()+88,&value,4); check(rejected(bad));
        bad = s; value = MaxPlans+1; std::memcpy(bad.data()+12,&value,4); check(rejected(bad));
        auto punctuation = [&](uint32_t first) {
            auto out = fixture(1); uint32_t v = 2;
            std::memcpy(out.data()+8,&v,4);
            const uint32_t glyphs[] = {2,first,0x2026};
            out.append(reinterpret_cast<const char*>(glyphs),sizeof(glyphs));
            append_plan(out,1,std::u16string(u"A") + char16_t(first) + u"…");
            return out;
        };
        auto dash = punctuation(0x2015); write(dash); pack.load(temp_file,true); // Full-width bar and ellipsis.
        check(pack.count == 1 && pack.glyph_count == 2 && pack.plans[0].slots[1] == 0x7F);
        check(rejected(punctuation(0x2014))); // 0.9 em dash has no exact logical advance.
        auto names = fixture(3); value = 3; std::memcpy(names.data()+8,&value,4);
        names.append(64,'b');
        const uint32_t name_glyphs[] = {2,0x4E2D,0x6587};
        names.append(reinterpret_cast<const char*>(name_glyphs),sizeof(name_glyphs));
        append_plan(names,4,u"\u4E2D");
        append_plan(names,NameDomain|5290,u"\u6587\u4E2D");
        append_plan(names,NameDomain|826,u"\u6587\u4E2D"); // Same label, distinct resource identities.
        write(names); pack.load(temp_file,true);
        check(pack.has_names && pack.typename_hash == std::wstring(64,L'b'));
        check(pack.match(L"\u4E2D") == 0 && pack.match(L"\u6587\u4E2D") == -1);
        check(pack.match_name("U9T14AA",NameCopyCaller) == 1);
        check(pack.match_name("U9T033A",NameCopyCaller) == 2);
        check(pack.match_name("U9T14AA",NameCopyCaller+1) == -1);
        check(pack.match_name("U9T14AAx",NameCopyCaller) == -1);
        check(pack.match_name("U9T14aa",NameCopyCaller) == -1);
        check(pack.match_name("U9T14A",NameCopyCaller) == -1);
        uint32_t lead = 99;
        check(pack.match_name("(27) U9T14AA",NameCopyCaller,&lead) == 1 && lead == 5);
        check(pack.match_name("U9T033A",NameCopyCaller,&lead) == 2 && lead == 0);
        check(pack.match_name("(27) U9T14AA",NameCopyCaller) == -1); // prefix only when asked for
        check(pack.match_name("(27)U9T14AA",NameCopyCaller,&lead) == -1);
        check(pack.match_name("() U9T14AA",NameCopyCaller,&lead) == -1);
        check(pack.match_name("(2x) U9T14AA",NameCopyCaller,&lead) == -1);
        check(pack.match_name("(27) U9T14AAx",NameCopyCaller,&lead) == -1);
        check(pack.match_name("(12345678901) U9T14AA",NameCopyCaller,&lead) == -1);
        check(count_prefix("(1234567890) x") == 0 && count_prefix("(123456789) x") == 12 && count_prefix(nullptr) == 0);
        check(pack.match_name(nullptr,NameCopyCaller) == -1 && rejected(names,false));
        check(rejected(names.substr(0,names.size()-1)) && rejected(names+"x"));
        bad = names; value = NameDomain|8192;
        const size_t name_start = 144+sizeof(name_glyphs)+8+2;
        std::memcpy(bad.data()+name_start,&value,4); check(rejected(bad));
        bad = names; bad[80] = 'z'; check(rejected(bad));
        bad = names; const char16_t lf = u'\n';
        std::memcpy(bad.data()+name_start+8,&lf,2); check(rejected(bad));
        // Text length boundary and over-long lookups.
        auto longest = fixture(1); append_plan(longest,1,std::u16string(MaxText,u'A')); write(longest); pack.load(temp_file,true);
        check(pack.match(std::wstring(MaxText,L'A').c_str()) == 0);
        check(pack.match(std::wstring(MaxText+1,L'A').c_str()) == -1 && pack.match(std::wstring(MaxText-1,L'A').c_str()) == -1);
        auto too_long = fixture(1); append_plan(too_long,1,std::u16string(MaxText+1,u'A')); check(rejected(too_long));
        // Maximum-capacity v3 pack: half text plans, half name plans, all scalars used.
        const auto full_pack = [&](uint32_t last_id, char16_t last_second) {
            std::string out("U9CTP51\0",8);
            auto u32 = [&](uint32_t v) { out.append(reinterpret_cast<const char*>(&v),4); };
            u32(3); u32(uint32_t(MaxPlans)); out.append(64,'a'); out.append(64,'b');
            u32(uint32_t(MaxGlyphScalars));
            for (uint32_t i = 0; i < MaxGlyphScalars; ++i) u32(0x4E00+i);
            for (uint32_t i = 0; i < MaxPlans; ++i) {
                const bool name = i >= MaxPlans/2;
                const auto slot = name ? i-uint32_t(MaxPlans/2) : i;
                std::u16string text{char16_t(0x4E00+slot),char16_t(name ? 0x4E01 : 0x4E00)};
                if (!name && i == MaxPlans/2-1) { text[1] = last_second; }
                append_plan(out,name ? (NameDomain|slot) : (i == MaxPlans/2-1 ? last_id : i),text);
            }
            return out;
        };
        const auto last_text = uint32_t(MaxPlans/2-1);
        write(full_pack(last_text,0x4E00)); auto big = std::make_unique<Pack>(); big->load(temp_file,true);
        check(big->count == MaxPlans && big->glyph_count == MaxGlyphScalars);
        const wchar_t first_text[] = {0x4E00,0x4E00,0}, final_text[] = {wchar_t(0x4E00+last_text),0x4E00,0}, absent[] = {0x4E00,0x4E02,0};
        check(big->match(first_text) == 0 && big->match(final_text) == int(last_text) && big->match(absent) == -1);
        check(big->match_name("U9T0000",NameCopyCaller) == int(MaxPlans/2));
        check(big->match_name("U9T1FFF",NameCopyCaller) == int(MaxPlans-1));
        check(big->match_name("U9T2000",NameCopyCaller) == -1 && big->match_name("U9T1fff",NameCopyCaller) == -1);
        check(rejected(full_pack(0,0x4E00))); // Duplicate entry at capacity.
        auto twin = fixture(2); append_plan(twin,1,u"\u4E2D"); append_plan(twin,2,u"\u4E2D"); check(rejected(twin)); // Same text is still ambiguous natively.
        std::cout << "PASS: identity/lifetime, v1/v2/v3 packs, resource-marker scope and malformed-input checks\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
