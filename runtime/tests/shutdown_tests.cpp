#include "engine.h"
#include <iostream>
#include <memory>
#include <thread>

int main() {
    using namespace u9cht;
    try {
        auto e = std::make_unique<Engine>();
        require(!e->begin() && e->active.load() == 0,"closed admission accepted call");
        auto* first = e->bind_buffer(0x1000,4,0,0,Life::Cache,0x2000);
        require(first && e->life_count == 1,"cache lifecycle event missing");
        const auto identity = first->identity, generation = first->generation;
        e->retire_buffer(0x1000);
        auto* reused = e->bind_buffer(0x1000,4,1,0,Life::Cache,0x3000);
        require(reused && reused->identity != identity && reused->generation != generation &&
            e->life_events[1].kind == Life::BufferEnd,"address reuse lifecycle incorrect");
        e->rasters[0].address = 0x4000; e->rasters[0].plan = 1;
        e->rasters[0].identity = reused->identity; e->rasters[0].generation = 10;
        e->queues[0] = {0x5000,0x4000,1,11,10,0,reused->identity};
        e->retire(0x4000);
        require(!e->rasters[0].address && !e->queues[0].address &&
            e->stats[1].raster_retired == 1 && e->stats[1].queue_retired == 1,"raster/queue retirement missing");
        require(e->life_events[e->life_count-2].kind == Life::QueueEnd &&
            e->life_events[e->life_count-1].kind == Life::RasterEnd,"retirement event order incorrect");
        e->retire(0x1000);
        require(e->registry.count() == 0,"freed binding remained live");
        require(e->bind_buffer(0x6000,4,0,0,Life::Cache,0x7000) != nullptr,"shutdown fixture failed");
        e->accepting = true;
        require(e->begin() && e->active.load() == 1,"admission did not track active call");
        require(!e->shutdown(true),"live hot unload was not refused");
        std::thread in_flight([&] { Sleep(100); e->active.fetch_sub(1); });
        const auto start = GetTickCount64();
        const auto stopped = e->shutdown(false);
        in_flight.join();
        require(stopped && GetTickCount64()-start >= 90 && e->active.load() == 0,"shutdown did not quiesce");
        require(!e->begin(),"shutdown allowed new work");
        require(e->registry.count() == 0 && e->life_events[e->life_count-1].kind == Life::BufferEnd,
            "shutdown retained live binding metadata");
        std::cout << "PASS: native lifecycle/admission/quiescence/hot-unload refusal cases\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
