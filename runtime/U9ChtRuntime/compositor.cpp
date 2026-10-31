#include "compositor.h"
#include <algorithm>

namespace u9cht {
Rect intersect(Rect a, Rect b) noexcept {
    return {std::max(a.left,b.left),std::max(a.top,b.top),std::min(a.right,b.right),std::min(a.bottom,b.bottom)};
}
bool empty(Rect r) noexcept { return r.left >= r.right || r.top >= r.bottom; }
uint8_t logical_metric(uint32_t spacing) noexcept { return spacing < 16 ? static_cast<uint8_t>(16-spacing) : 0; }
bool FrameList::add_record(const DrawRecord& record) noexcept {
    if (records >= sources.size()) return false;
    for (uint32_t i = 0; i < records; ++i) if (sources[i].node == record.node) return false;
    sources[records++] = record; return true;
}
bool FrameList::add(const DrawCommand& command) noexcept {
    if (!command.glyph || count >= commands.size() || empty(command.clip)) return false;
    commands[count++] = command; return true;
}
bool SurfaceTracker::accept(const SurfaceKey& next) noexcept {
    const bool changed = !valid || !(key == next);
    if (changed) { key = next; ++generation; valid = true; }
    return changed;
}
uint64_t blend(uint8_t* pixels, uint32_t pitch, Rect locked, const FrameList& frame) noexcept {
    uint64_t written = 0;
    for (uint32_t i = 0; i < frame.count; ++i) {
        const auto& c = frame.commands[i]; const auto& g = *c.glyph;
        const auto r = intersect(intersect(c.clip,locked),{c.left,c.top,c.left+int(g.width),c.top+int(g.height)});
        if (empty(r)) continue;
        for (int32_t y = r.top; y < r.bottom; ++y) {
            auto* dest = pixels+size_t(y-locked.top)*pitch+size_t(r.left-locked.left)*4;
            const auto* alpha = g.alpha.data()+size_t(y-c.top)*g.width+size_t(r.left-c.left);
            for (int32_t x = r.left; x < r.right; ++x, dest+=4, ++alpha) {
                const uint32_t a = *alpha; written += a != 0;
                for (uint32_t channel = 0; channel < 3; ++channel)
                    dest[channel] = static_cast<uint8_t>((c.rgb[2-channel]*a+dest[channel]*(255-a)+127)/255);
                // X byte is deliberately untouched for every coverage value.
            }
        }
    }
    return written;
}
PaintResult paint_surface(const SurfaceAccess& a, Rect locked, const FrameList& frame, SurfaceTracker& tracker) noexcept {
    RECT rect{locked.left,locked.top,locked.right,locked.bottom};
    DDSURFACEDESC2 desc{}; desc.dwSize = sizeof(desc);
    static_assert(sizeof(desc) == 124);
    if (FAILED(a.lock(a.object,&rect,&desc,0x801,nullptr))) {
        tracker.invalidate(); return {PaintStatus::LockFailed,0};
    }
    PaintResult result{PaintStatus::InvalidDescriptor,0};
    const auto& pf = desc.ddpfPixelFormat;
    const bool format = pf.dwSize == 32 && pf.dwFlags == DDPF_RGB && pf.dwFourCC == 0 &&
        pf.dwRGBBitCount == 32 && pf.dwRBitMask == 0xFF0000 && pf.dwGBitMask == 0xFF00 &&
        pf.dwBBitMask == 0xFF && pf.dwRGBAlphaBitMask == 0;
    if (desc.dwSize == 124 && (desc.dwFlags&0x100F) == 0x100F && format &&
        desc.dwWidth == frame.width && desc.dwHeight == frame.height && desc.lpSurface &&
        desc.lPitch >= int32_t(frame.width*4) && desc.lPitch <= 0x10000 && desc.lPitch%4 == 0) {
        tracker.accept({a.backend,reinterpret_cast<uintptr_t>(a.object),desc.dwWidth,desc.dwHeight,uint32_t(desc.lPitch),32});
        result = {PaintStatus::Painted,blend(static_cast<uint8_t*>(desc.lpSurface),uint32_t(desc.lPitch),locked,frame)};
    } else tracker.invalidate();
    const auto hr = a.unlock(a.object,&rect);
    desc.lpSurface = nullptr;
    if (FAILED(hr)) { tracker.invalidate(); result.status = PaintStatus::UnlockFailed; }
    return result;
}
}
