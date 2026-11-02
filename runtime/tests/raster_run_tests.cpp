#include "raster_runs.h"
#include <iostream>
#include <stdexcept>

int main() {
    using namespace u9cht;
    auto check = [](bool v) { if (!v) throw std::runtime_error("raster run regression failed"); };
    try {
        // Actual failing menu sequence:4040,4039,4038 in one161x70 repaint.
        const PaintScope scope{4806,0x1000,0x2000,RasterRuns::SharedCaller};
        RasterRuns menu;
        auto* first = menu.acquire(scope,0,8,0x3000); check(first != nullptr); first->drawn = 6;
        auto* second = menu.acquire(scope,1,9,0x4000); check(second != nullptr); second->drawn = 9;
        auto* third = menu.acquire(scope,2,10,0x5000); check(third != nullptr); third->drawn = 5;
        check(menu.size() == 3 && menu.at(0).identity == 8 && menu.at(1).identity == 9 &&
              menu.at(2).identity == 10 && menu.at(0).drawn+menu.at(1).drawn+menu.at(2).drawn == 20);
        check(menu.acquire(scope,1,9,0x4000) == second && menu.size() == 3);
        auto bad = scope; ++bad.generation; check(!menu.acquire(bad,3,11,0x6000));
        bad = scope; ++bad.widget; check(!menu.acquire(bad,3,11,0x6000));
        bad = scope; ++bad.owner; check(!menu.acquire(bad,3,11,0x6000));
        bad = scope; ++bad.caller; check(!menu.acquire(bad,3,11,0x6000));
        check(!menu.acquire(scope,MaxPlans,11,0x6000) && !menu.acquire(scope,3,0,0x6000));
        menu.seal(); check(!menu.acquire(scope,1,9,0x4000) && !menu.acquire(scope,3,11,0x6000));
        // A stale texture or an unmeasured caller cannot silently become a menu.
        RasterRuns ordinary;
        const PaintScope outside{};
        check(ordinary.acquire(outside,0,1,0x7000) != nullptr);
        check(ordinary.acquire(outside,0,1,0x7000) != nullptr);
        check(!ordinary.acquire(outside,1,2,0x8000));
        RasterRuns unknown;
        bad = scope; bad.caller = 0x1234;
        check(unknown.acquire(bad,0,1,0x7000) != nullptr);
        check(!unknown.acquire(bad,1,2,0x8000));
        RasterRuns bounded;
        for (uint32_t i = 0; i < 8; ++i) check(bounded.acquire(scope,i,i+1,0x9000+i*16) != nullptr);
        check(!bounded.acquire(scope,8,9,0xA000));
        // Repaint resets metadata; an old run must not survive address reuse.
        menu = {};
        check(menu.size() == 0 && menu.acquire(scope,3,11,0x6000) != nullptr && menu.at(0).drawn == 0);
        std::cout << "PASS: shared response raster identities, scope isolation, seal, capacity and repaint reuse\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
