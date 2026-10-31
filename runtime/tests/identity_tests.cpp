#include "identity.h"
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
        std::cout << "PASS: 13 multi-identity/copy/reuse/overlap/lifetime checks\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
