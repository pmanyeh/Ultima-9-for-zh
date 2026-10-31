#include "engine.h"
#include <iostream>
#include <memory>
#include <thread>

int main() {
    using namespace u9cht;
    try {
        auto e = std::make_unique<Engine>();
        require(!e->begin() && e->active.load() == 0,"closed admission accepted call");
        e->accepting = true;
        require(e->begin() && e->active.load() == 1,"admission did not track active call");
        require(!e->shutdown(true),"live hot unload was not refused");
        std::thread in_flight([&] { Sleep(100); e->active.fetch_sub(1); });
        const auto start = GetTickCount64();
        const auto stopped = e->shutdown(false);
        in_flight.join();
        require(stopped && GetTickCount64()-start >= 90 && e->active.load() == 0,"shutdown did not quiesce");
        require(!e->begin(),"shutdown allowed new work");
        std::cout << "PASS: 5 admission/quiescence/hot-unload refusal checks\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
