#include "compositor.h"
#include <algorithm>

namespace u9cht {
Rect intersect(Rect a, Rect b) noexcept {
    return {std::max(a.left,b.left),std::max(a.top,b.top),std::min(a.right,b.right),std::min(a.bottom,b.bottom)};
}
bool empty(Rect r) noexcept { return r.left >= r.right || r.top >= r.bottom; }
uint8_t logical_metric(uint32_t spacing, uint32_t advance) noexcept {
    return advance <= 255 && spacing < advance ? static_cast<uint8_t>(advance-spacing) : 0;
}
bool FrameList::add_record(const DrawRecord& record) noexcept {
    if (records >= sources.size()) return false;
    for (uint32_t i = 0; i < records; ++i) if (sources[i].node == record.node) return false;
    sources[records++] = record; return true;
}
bool FrameList::add(const DrawCommand& command) noexcept {
    if (!command.glyph || count >= commands.size() || empty(command.clip)) return false;
    bounds = count ? Rect{std::min(bounds.left,command.clip.left),std::min(bounds.top,command.clip.top),
                          std::max(bounds.right,command.clip.right),std::max(bounds.bottom,command.clip.bottom)} : command.clip;
    commands[count++] = command; return true;
}
bool texel_opaque(uint16_t texel, MaskRule rule, uint16_t corner) noexcept {
    switch (rule) {
    case MaskRule::Key: return (texel&0x7FFF) != SampleTransparent;
    case MaskRule::Alpha1555: return (texel&0x8000) != 0;
    case MaskRule::Alpha4444: return (texel>>12) >= 8;
    case MaskRule::Corner: return texel != corner;
    }
    return false;
}
uint32_t build_mask(OccluderMask& mask, const uint16_t* pixels, uint32_t stride, uint32_t width, uint32_t height,
                    MaskRule rule, uint16_t corner) noexcept {
    uint32_t opaque = 0;
    mask.width = width; mask.height = height;
    for (uint32_t y = 0; y < height; ++y) for (uint32_t x = 0; x < width; ++x) {
        const bool solid = texel_opaque(pixels[size_t(y)*stride+x],rule,corner);
        mask.opaque[y*MaskMaxSide+x] = solid;
        opaque += solid;
    }
    return opaque;
}
bool dominant_color(std::span<const uint16_t> pixels, std::array<uint8_t,3>& rgb) noexcept {
    // A glyph sample has few distinct colors; this bound only skips exotic ones.
    std::array<uint16_t,64> values{}; std::array<uint32_t,64> counts{}; uint32_t used = 0;
    for (const auto raw : pixels) {
        const uint16_t value = raw&0x7FFF;
        if (value == 0 || value == SampleTransparent || std::max({(value>>10)&31,(value>>5)&31,value&31}) < 16) continue;
        uint32_t i = 0;
        while (i < used && values[i] != value) ++i;
        if (i == used) { if (used == values.size()) continue; values[used++] = value; }
        ++counts[i];
    }
    uint32_t best = used;
    for (uint32_t i = 0; i < used; ++i) if (best == used || counts[i] > counts[best]) best = i;
    if (best == used) return false;
    const auto value = values[best];
    rgb = {uint8_t((((value>>10)&31)*255+15)/31),uint8_t((((value>>5)&31)*255+15)/31),uint8_t(((value&31)*255+15)/31)};
    return true;
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
        std::array<const OccluderMask*,4> above{}; uint32_t above_count = 0;
        for (uint32_t m = 0; m < frame.mask_count; ++m)
            if (i < frame.masks[m].covers && !empty(intersect(r,frame.masks[m].area))) above[above_count++] = &frame.masks[m];
        const auto hidden = [&](int32_t x, int32_t y) {
            for (uint32_t m = 0; m < above_count; ++m) if (above[m]->hides(x,y)) return true;
            return false;
        };
        for (int32_t y = r.top; y < r.bottom; ++y) {
            auto* dest = pixels+size_t(y-locked.top)*pitch+size_t(r.left-locked.left)*4;
            const auto* alpha = g.alpha.data()+size_t(y-c.top)*g.width+size_t(r.left-c.left);
            for (int32_t x = r.left; x < r.right; ++x, dest+=4, ++alpha) {
                if (above_count && hidden(x,y)) continue;
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
