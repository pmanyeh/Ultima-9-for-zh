#pragma once
#include "glyph_cache.h"
#include <array>
#include <cstdint>
#include <ddraw.h>

namespace u9cht {
struct Rect { int32_t left = 0, top = 0, right = 0, bottom = 0; };
Rect intersect(Rect a, Rect b) noexcept;
bool empty(Rect r) noexcept;
uint8_t logical_metric(uint32_t spacing) noexcept;
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
struct FrameList {
    uint64_t epoch = 0;
    uintptr_t backend = 0, backbuffer = 0;
    uint32_t width = 0, height = 0, count = 0, records = 0;
    std::array<DrawCommand,512> commands{};
    std::array<DrawRecord,64> sources{};
    bool add_record(const DrawRecord& record) noexcept;
    bool add(const DrawCommand& command) noexcept;
    bool current(uint64_t expected, uintptr_t expected_backend, uintptr_t expected_backbuffer) const noexcept {
        return epoch == expected && backend == expected_backend && backbuffer == expected_backbuffer;
    }
    void clear(uint64_t next_epoch) noexcept { epoch = next_epoch; backend = backbuffer = 0; count = records = 0; }
};
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
