#pragma once
#include "hook_manager.h"
#include "identity.h"
#include "platform.h"
#include "compositor.h"
#include <atomic>

namespace u9cht {
struct EntryStats {
    uint64_t wide = 0, cache = 0, copies = 0, layout = 0, bounds = 0, glyph = 0;
    uint64_t raster = 0, queue = 0, submissions = 0, presentations = 0, freed = 0;
    uint64_t width_overrides = 0, unicode_draws = 0, composites = 0, cache_hits = 0, cache_misses = 0;
    uint64_t raster_retired = 0, queue_retired = 0;
};
struct Placement { uint32_t offset = 0; int32_t x = 0, y = 0; };
struct RasterBinding {
    uintptr_t address = 0, pixels = 0;
    uint32_t plan = 0, width = 0, height = 0, stride = 0, count = 0;
    uint64_t generation = 0, hash = 0, paint_generation = 0, identity = 0;
    std::array<Placement, MaxText> placements{};
    std::array<uint8_t,3> rgb{181,132,239};
};
struct QueueBinding {
    uintptr_t address = 0, raster = 0;
    uint32_t plan = 0;
    uint64_t generation = 0, raster_generation = 0, last_frame = 0, identity = 0;
};
enum class Life : uint32_t { Cache = 1, Copy, BufferEnd, RasterBegin, RasterReady, QueueBegin, QueueEnd, RasterEnd, Shutdown };
struct LifeEvent {
    uint64_t sequence = 0, tick = 0, identity = 0, generation = 0;
    uintptr_t address = 0, related = 0;
    uint32_t plan = 0;
    Life kind = Life::Cache;
    uint64_t raster_hash = 0;
    uint32_t width = 0, height = 0, stride = 0;
};
struct Engine {
    Pack pack;
    Registry registry;
    HookManager hooks;
    Logger* log = nullptr;
    bool render = false;
    SRWLOCK mutex = SRWLOCK_INIT;
    SRWLOCK io_gate = SRWLOCK_INIT;
    std::atomic<bool> accepting{false}, entered{false};
    std::atomic<uint32_t> active{0}, errors{0}, first_error{0};
    Handle worker, stop;
    GlyphCache glyphs;
    FrameList draw_list;
    SurfaceTracker surface;
    std::array<uint32_t,32768> colors{};
    uint64_t started = 0, frame = 1, generations = 0, flips = 0;
    uint32_t max_rasters = 0, max_queues = 0;
    uint64_t composite_count = 0, unicode_runs = 0, pixel_writes = 0, lock_failures = 0, unlock_failures = 0;
    uint64_t skipped_frames = 0, compositor_ticks = 0, compositor_max_ticks = 0;
    uint32_t max_frame_records = 0;
    std::atomic<DWORD> render_thread{0};
    std::array<LifeEvent,4096> life_events{};
    uint32_t life_count = 0, life_dropped = 0;
    uint64_t life_sequence = 0;
    std::array<EntryStats, MaxPlans> stats{};
    std::array<RasterBinding, 64> rasters{};
    std::array<QueueBinding, 128> queues{};
    bool begin() noexcept;
    void fail(uint32_t code) noexcept;
    void install(const Config& config, Logger& logger);
    bool shutdown(bool explicit_unload) noexcept;
    void snapshot(const char* event) noexcept;
    Located locate(uintptr_t source) noexcept;
    RasterBinding* raster(uintptr_t address) noexcept;
    QueueBinding* queue(uintptr_t address) noexcept;
    void retire(uintptr_t address) noexcept;
    void retire_buffer(uintptr_t address) noexcept;
    Binding* bind_buffer(uintptr_t address, uint32_t length, uint32_t plan, uint64_t identity, Life kind, uintptr_t related) noexcept;
    LifeEvent* trace(Life kind, uint32_t plan, uintptr_t address, uint64_t identity, uint64_t generation, uintptr_t related = 0) noexcept;
    void compose(uintptr_t backend) noexcept;
};
extern Engine* engine;
}
