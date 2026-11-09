#pragma once
#include "hook_manager.h"
#include "identity.h"
#include "platform.h"
#include "compositor.h"
#include "raster_runs.h"
#include <atomic>

namespace u9cht {
struct EntryStats {
    uint64_t wide = 0, cache = 0, copies = 0, layout = 0, bounds = 0, glyph = 0;
    uint64_t raster = 0, queue = 0, submissions = 0, presentations = 0, freed = 0;
    uint64_t width_overrides = 0, unicode_draws = 0, composites = 0, cache_hits = 0, cache_misses = 0;
    uint64_t raster_retired = 0, queue_retired = 0;
    uint64_t shared_rasters = 0;
    uint64_t name_copies = 0;
};
struct Placement { uint32_t offset = 0; int32_t x = 0, y = 0; uint32_t run = 0; std::array<uint8_t,3> rgb{181,132,239}; };
// One native font's displayed color, learned once by drawing a reference glyph privately.
struct FontStyle {
    uintptr_t blob = 0;
    std::array<uint8_t,3> rgb{181,132,239};
    bool sampled = false;
    uint32_t reference = 0;
    uint64_t uses = 0;
};
struct RasterBinding {
    uintptr_t address = 0, pixels = 0;
    uint32_t plan = 0, width = 0, height = 0, stride = 0, count = 0;
    uint64_t generation = 0, hash = 0, paint_generation = 0, identity = 0;
    std::array<Placement, MaxText> placements{};
    RasterRuns runs;
};
struct QueueBinding {
    uintptr_t address = 0, raster = 0;
    uint32_t plan = 0;
    uint64_t generation = 0, raster_generation = 0, last_frame = 0, identity = 0;
};
enum class Life : uint32_t { Cache = 1, Copy, BufferEnd, RasterBegin, RasterReady, QueueBegin, QueueEnd, RasterEnd, Shutdown, RasterRunReady };
struct LifeEvent {
    uint64_t sequence = 0, tick = 0, identity = 0, generation = 0;
    uintptr_t address = 0, related = 0;
    uint32_t plan = 0;
    Life kind = Life::Cache;
    uint64_t raster_hash = 0;
    uint32_t width = 0, height = 0, stride = 0;
    uint32_t glyph_count = 0;
};
struct RasterFault {
    uint64_t tick = 0, frame = 0, paint = 0, identity = 0;
    uintptr_t source = 0, raster = 0, paint_owner = 0, widget = 0, paint_caller = 0;
    uint32_t plan = 0, offset = 0, native_width = 0, native_height = 0;
    bool bound = false;
    uint32_t prior_plan = 0, prior_count = 0;
    uint64_t prior_identity = 0, prior_generation = 0, prior_paint = 0;
};
// P8-2 journal probe: observe-only evidence, never changes game output.
struct JournalAppend {
    uint64_t tick = 0;
    int32_t entry = -1;          // matched plan entry, -1 when not allowlisted
    uint32_t code_page = 0, wide_length = 0, capacity = 0, high_bytes = 0;
    int32_t result = 0;
    uint32_t error = 0;
};
struct FlowProbe {
    uintptr_t flow = 0, caller = 0, widget = 0, text = 0;
    uintptr_t buffers[3]{};      // flow+0x34 (4 KiB), +0x38 (64 KiB), +0x3C (32 KiB)
    uint32_t text_length = 0, text_high = 0;
    uint64_t text_hash = 0, calls = 0, last_tick = 0;
    uint64_t layout[4]{}, bounds[4]{}, glyph[4]{}; // by range: text, +0x34, +0x38, +0x3C
    uintptr_t glyph_paint_caller = 0, glyph_paint_owner = 0, glyph_paint_widget = 0, glyph_raster = 0;
    uint32_t glyph_raster_width = 0, glyph_raster_height = 0;
    uint64_t glyph_outside_paint = 0;
};
struct CallerCount { uintptr_t caller = 0; uint64_t count = 0; };
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
    std::array<FontStyle,64> fonts{};
    uint32_t font_count = 0;
    uint64_t font_overflow = 0;
    static constexpr uint32_t SampleSize = 128;
    std::array<uint16_t,SampleSize*SampleSize> sample{};
    std::array<uint16_t,SampleSize*SampleSize*2> sample_aux{};
    uint64_t occluder_masks = 0;
    std::array<uint64_t,6> occluder_rejects{}; // masks full, tiles, raster fields, size, fault, mostly opaque
    std::array<uint64_t,5> skip_reasons{};     // not current, device lost, backbuffer, stale source, empty
    Rect last_occluder{};
    uint32_t last_occluder_caller = 0, last_occluder_opaque = 0, last_occluder_rule = 0, last_occluder_corner = 0;
    uint32_t last_occluder_type = 0, last_occluder_alpha1555 = 0, last_occluder_alpha4444 = 0;
    std::array<uint32_t,5> last_occluder_raster{}; // tiles, width, height, bits, stride
    uint64_t started = 0, frame = 1, generations = 0, flips = 0;
    uint32_t max_rasters = 0, max_queues = 0;
    uint64_t composite_count = 0, unicode_runs = 0, pixel_writes = 0, lock_failures = 0, unlock_failures = 0;
    uint64_t skipped_frames = 0, compositor_ticks = 0, compositor_max_ticks = 0;
    uint32_t max_frame_records = 0;
    std::atomic<DWORD> render_thread{0};
    std::array<LifeEvent,16384> life_events{}; // Peak observed: 2560 in one 5s snapshot.
    uint32_t life_count = 0, life_dropped = 0;
    uint64_t life_sequence = 0;
    std::array<RasterFault,16> raster_faults{};
    uint32_t raster_fault_count = 0;
    std::array<EntryStats, MaxPlans> stats{};
    std::array<RasterBinding, 64> rasters{};
    std::array<QueueBinding, 128> queues{};
    std::array<JournalAppend,16> journal_appends{};
    uint64_t journal_append_total = 0;
    std::array<FlowProbe,32> flows{};
    uint64_t flow_overflow = 0;
    std::array<CallerCount,32> glyph_callers{}, paint_callers{}, queue_callers{};
    uint64_t caller_overflow = 0;
    void count_caller(std::array<CallerCount,32>& table, uintptr_t caller) noexcept;
    void probe_flow_source(uintptr_t source, uint32_t stage) noexcept;
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
    void add_occluder(uintptr_t node, Rect area, uint32_t caller, float sx, float sy) noexcept;
    const FontStyle& font_style(uintptr_t record) noexcept;
};
extern Engine* engine;
}
