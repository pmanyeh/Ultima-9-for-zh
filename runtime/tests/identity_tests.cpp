#include "identity.h"
#include "platform.h"
#include <fstream>
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
            write(bad); try { Pack p; p.load(temp_file,render); return false; } catch (...) { return true; }
        };
        check(rejected(bytes,false)); // Observe cannot carry opaque Unicode.
        check(rejected(bytes.substr(0,bytes.size()-1)) && rejected(bytes+"x"));
        auto duplicate = fixture(2); append_plan(duplicate,1,u"A"); append_plan(duplicate,1,u"B"); check(rejected(duplicate));
        auto ambiguous = fixture(2); append_plan(ambiguous,1,u"A"); append_plan(ambiguous,2,u"A"); check(rejected(ambiguous));
        auto invalid = fixture(1); append_plan(invalid,1,std::u16string(1,0xD800)); check(rejected(invalid));
        invalid = fixture(1); append_plan(invalid,1,u"你"); check(rejected(invalid));
        check(rejected(fixture(17)) && rejected(fixture(0)));
        std::cout << "PASS: 22 multi-identity/lifetime/allowlist/malformed-input checks\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
