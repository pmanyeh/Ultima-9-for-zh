#pragma once
#include "glyph_cache.h"
#include <array>
#include <cstdint>
#include <ddraw.h>
#include <span>

namespace u9cht {
struct Rect { int32_t left = 0, top = 0, right = 0, bottom = 0; };
Rect intersect(Rect a, Rect b) noexcept;
bool empty(Rect r) noexcept;
uint8_t logical_metric(uint32_t spacing, uint32_t advance = 16) noexcept;
struct DrawCommand {
    const Glyph* glyph = nullptr;
    int32_t left = 0, top = 0;
    Rect clip;
    std::array<uint8_t,3> rgb{181,132,239};
};
struct DrawRecord {
    uintptr_t node = 0, raster = 0;
    uint64_t queue_generation = 0, raster_generation = 0;
    uint32_t plan = 0;
};
// Native UI drawn after pending Chinese (the cursor): its opaque texels stay on top.
inline constexpr uint32_t MaskMaxSide = 128;
struct OccluderMask {
    uintptr_t node = 0;
    Rect area;
    uint32_t covers = 0; // Commands before this index were queued earlier, so lie underneath.
    uint32_t width = 0, height = 0;
    std::array<uint8_t,MaskMaxSide*MaskMaxSide> opaque{};
    bool hides(int32_t x, int32_t y) const noexcept {
        if (x < area.left || x >= area.right || y < area.top || y >= area.bottom) return false;
        const auto tx = uint32_t(x-area.left)*width/uint32_t(area.right-area.left);
        const auto ty = uint32_t(y-area.top)*height/uint32_t(area.bottom-area.top);
        return opaque[ty*MaskMaxSide+tx] != 0;
    }
};
struct FrameList {
    uint64_t epoch = 0;
    uintptr_t backend = 0, backbuffer = 0;
    uint32_t width = 0, height = 0, count = 0, records = 0;
    Rect bounds{}; // Union of pending command clips; meaningful while count != 0.
    std::array<DrawCommand,512> commands{};
    std::array<DrawRecord,64> sources{};
    std::array<OccluderMask,4> masks{};
    uint32_t mask_count = 0;
    bool add_record(const DrawRecord& record) noexcept;
    bool add(const DrawCommand& command) noexcept;
    bool current(uint64_t expected, uintptr_t expected_backend, uintptr_t expected_backbuffer) const noexcept {
        return epoch == expected && backend == expected_backend && backbuffer == expected_backbuffer;
    }
    void clear(uint64_t next_epoch) noexcept { epoch = next_epoch; backend = backbuffer = 0; count = records = mask_count = 0; bounds = {}; }
    // True when a later native draw covering `area` must land above pending text.
    bool overlaps(Rect area) const noexcept { return count && !empty(intersect(bounds,area)); }
};
// How a 16-bit texel is judged opaque. Text rasters use the RGB555 key; the cursor raster is
// 128x128 with no key texel (session-defects-3), so alpha layouts and the corner value are tried.
enum class MaskRule : uint32_t { Key = 1, Alpha1555 = 2, Alpha4444 = 3, Corner = 4 };
bool texel_opaque(uint16_t texel, MaskRule rule, uint16_t corner) noexcept;
// Fills `mask` (stride in texels); returns the opaque texel count.
uint32_t build_mask(OccluderMask& mask, const uint16_t* pixels, uint32_t stride, uint32_t width, uint32_t height,
                    MaskRule rule = MaskRule::Key, uint16_t corner = 0) noexcept;
uint64_t blend(uint8_t* pixels, uint32_t pitch, Rect locked, const FrameList& frame) noexcept;
// Most frequent bright RGB555 value in a native glyph sample; false when none.
inline constexpr uint16_t SampleTransparent = 0x7C1F;
bool dominant_color(std::span<const uint16_t> pixels, std::array<uint8_t,3>& rgb) noexcept;
struct SurfaceKey {
    uintptr_t backend = 0, backbuffer = 0;
    uint32_t width = 0, height = 0, pitch = 0, format = 0;
    bool operator==(const SurfaceKey&) const = default;
};
struct SurfaceTracker {
    SurfaceKey key;
    uint64_t generation = 0;
    bool valid = false;
    bool accept(const SurfaceKey& next) noexcept;
    void invalidate() noexcept { if (valid) { valid = false; ++generation; } }
};
// No allocation, GDI, logging or retained surface pointer. The caller owns a
// successfully locked, validated rectangular view and unlocks after this call.
uint64_t blend(uint8_t* pixels, uint32_t pitch, Rect locked, const FrameList& frame) noexcept;
using SurfaceLock = HRESULT(WINAPI*)(void*,RECT*,DDSURFACEDESC2*,DWORD,HANDLE);
using SurfaceUnlock = HRESULT(WINAPI*)(void*,RECT*);
struct SurfaceAccess { void* object; uintptr_t backend; SurfaceLock lock; SurfaceUnlock unlock; };
enum class PaintStatus { Painted, LockFailed, InvalidDescriptor, UnlockFailed };
struct PaintResult { PaintStatus status; uint64_t pixels; };
PaintResult paint_surface(const SurfaceAccess& access, Rect rect, const FrameList& frame, SurfaceTracker& tracker) noexcept;
}
