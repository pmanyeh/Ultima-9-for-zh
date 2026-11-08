#include "compositor.h"
#include <iostream>
#include <memory>
#include <stdexcept>

using namespace u9cht;
namespace {
struct FakeSurface {
    std::array<uint8_t,64> pixels{};
    HRESULT lock_result = S_OK, unlock_result = S_OK;
    bool bad_format = false, locked = false;
    uint32_t locks = 0, unlocks = 0, width = 4, height = 4;
    static HRESULT WINAPI lock(void* object, RECT* r, DDSURFACEDESC2* d, DWORD flags, HANDLE event) {
        auto& s = *static_cast<FakeSurface*>(object); ++s.locks;
        if (flags != 0x801 || event || s.locked) return E_FAIL;
        if (FAILED(s.lock_result)) return s.lock_result;
        s.locked = true; *d = {}; d->dwSize = 124; d->dwFlags = 0x100F;
        d->dwWidth = s.width; d->dwHeight = s.height; d->lPitch = 16;
        d->lpSurface = s.pixels.data()+size_t(r->top)*16+size_t(r->left)*4;
        d->ddpfPixelFormat = {32,DDPF_RGB,0,32,0xFF0000,0xFF00,0xFF,0};
        if (s.bad_format) d->ddpfPixelFormat.dwGBitMask = 0xF0;
        return S_OK;
    }
    static HRESULT WINAPI unlock(void* object, RECT*) {
        auto& s = *static_cast<FakeSurface*>(object); ++s.unlocks;
        if (!s.locked) return E_FAIL;
        s.locked = false; return s.unlock_result;
    }
};
}
int main() {
    auto check = [](bool v) { if (!v) throw std::runtime_error("pixel assertion failed"); };
    try {
        Glyph g; g.width = g.height = 2; g.alpha = {255,128,0,255};
        FrameList frame; frame.clear(3); frame.width = frame.height = 4;
        check(frame.add_record({1,2,3,4,0}) && frame.add_record({5,6,7,8,1}));
        check(!frame.add_record({1,2,3,4,0}));
        check(frame.add({&g,1,1,{1,1,3,3},{200,100,50}}));
        FakeSurface s; for (size_t i = 3; i < s.pixels.size(); i+=4) s.pixels[i] = 0xA5;
        SurfaceTracker tracker;
        SurfaceAccess a{&s,9,FakeSurface::lock,FakeSurface::unlock};
        auto result = paint_surface(a,{1,1,3,3},frame,tracker);
        check(result.status == PaintStatus::Painted && result.pixels == 3 && !s.locked && s.unlocks == 1);
        check(s.pixels[20] == 50 && s.pixels[21] == 100 && s.pixels[22] == 200);
        check(s.pixels[24] == 25 && s.pixels[25] == 50 && s.pixels[26] == 100);
        for (size_t i = 3; i < s.pixels.size(); i+=4) check(s.pixels[i] == 0xA5);
        check(s.pixels[0] == 0 && s.pixels[36] == 0); // Transparent coverage/unrelated pixels untouched.
        check(frame.add({&g,-1,-1,{0,0,1,1},{200,100,50}}));
        check(frame.count == 2 && frame.current(3,0,0) && !frame.current(2,0,0));
        check(!frame.current(3,1,0) && !frame.current(3,0,1));
        const auto generation = tracker.generation;
        check(!tracker.accept(tracker.key) && tracker.generation == generation);
        s.lock_result = DDERR_SURFACELOST;
        result = paint_surface(a,{1,1,3,3},frame,tracker);
        check(result.status == PaintStatus::LockFailed && s.unlocks == 1 && !tracker.valid && result.pixels == 0);
        s.lock_result = S_OK;
        result = paint_surface(a,{1,1,3,3},frame,tracker);
        check(result.status == PaintStatus::Painted && tracker.valid && tracker.generation > generation);
        s.bad_format = true;
        result = paint_surface(a,{1,1,3,3},frame,tracker);
        check(result.status == PaintStatus::InvalidDescriptor && s.unlocks == 3 && !s.locked);
        s.bad_format = false; s.width = 3;
        check(paint_surface(a,{1,1,3,3},frame,tracker).status == PaintStatus::InvalidDescriptor);
        s.width = 4; s.unlock_result = E_FAIL;
        check(paint_surface(a,{1,1,3,3},frame,tracker).status == PaintStatus::UnlockFailed && !tracker.valid);
        frame.clear(4); check(frame.epoch == 4 && frame.count == 0 && frame.records == 0);
        auto clipped = intersect({-2,-3,5,6},{0,0,4,4}); check(clipped.left == 0 && clipped.bottom == 4);
        check(empty(intersect({0,0,1,1},{1,1,2,2})));
        check(logical_metric(0) == 16 && logical_metric(3)+3 == 16 && logical_metric(16) == 0);
        check(logical_metric(2,8) == 6 && logical_metric(8,8) == 0 && logical_metric(0,256) == 0);
        GlyphKey k; k.scalar = 0x4E2D; k.em = 20; k.mode = GGO_GRAY8_BITMAP|GGO_GLYPH_INDEX;
        auto changed = k; changed.em = 40; check(!(k == changed));
        changed = k; changed.font[0] = L'x'; check(!(k == changed));
        changed = k; changed.scalar = 0x6587; check(!(k == changed));
        changed = k; changed.mode = 1; check(!(k == changed));
        // Full-capacity lookup: every scalar/em pair resolves to its own slot.
        auto keys = std::make_unique<std::array<GlyphKey,GlyphCacheCapacity>>();
        auto table = std::make_unique<GlyphIndex>();
        check(table->find(0x4E2D,20,*keys) == -1);
        for (uint32_t i = 0; i < GlyphCacheCapacity; ++i) {
            auto& key = (*keys)[i]; key.scalar = 0x4E00+i/2; key.em = i%2 ? 40 : 20;
            table->insert(key.scalar,key.em,i);
        }
        for (uint32_t i = 0; i < GlyphCacheCapacity; ++i)
            check(table->find(0x4E00+i/2,i%2 ? 40 : 20,*keys) == int(i));
        check(table->find(0x4E00+GlyphCacheCapacity,20,*keys) == -1 && table->find(0x4E00,80,*keys) == -1);
        table->clear(); check(table->find(0x4E00,20,*keys) == -1);
        // Occlusion bounds follow pending commands and reset with the frame.
        FrameList pending; pending.width = pending.height = 64;
        check(!pending.overlaps({0,0,64,64}));
        pending.add({&g,0,0,{10,10,20,20},{1,2,3}});
        pending.add({&g,0,0,{30,5,40,15},{1,2,3}});
        check(pending.bounds.left == 10 && pending.bounds.top == 5 && pending.bounds.right == 40 && pending.bounds.bottom == 20);
        check(pending.overlaps({39,19,50,50}) && !pending.overlaps({40,0,50,50}) && !pending.overlaps({0,20,64,64}));
        pending.clear(2); check(!pending.overlaps({0,0,64,64}) && pending.count == 0);
        // Occluder mask: opaque texels stay on top of earlier text only; key texels and later text paint.
        {
            auto occluded = std::make_unique<FrameList>();
            occluded->width = occluded->height = 8;
            Glyph solid; solid.width = 8; solid.height = 1; solid.alpha.assign(8,255);
            occluded->add({&solid,0,0,{0,0,8,1},{255,255,255}});
            auto& m = occluded->masks[0];
            const std::array<uint16_t,4> texels{0x1234,SampleTransparent,uint16_t(SampleTransparent|0x8000),0};
            check(build_mask(m,texels.data(),4,4,1) == 2);
            m.area = {0,0,8,8}; m.covers = 1; occluded->mask_count = 1;
            occluded->add({&solid,0,1,{0,1,8,2},{255,255,255}});
            check(m.hides(0,0) && m.hides(1,7) && !m.hides(2,0) && !m.hides(5,0) && m.hides(6,0) && !m.hides(8,0) && !m.hides(0,8));
            std::array<uint32_t,64> screen{};
            check(blend(reinterpret_cast<uint8_t*>(screen.data()),32,{0,0,8,8},*occluded) == 12);
            check(screen[0] == 0 && screen[1] == 0 && (screen[2]&0xFFFFFF) == 0xFFFFFF && (screen[5]&0xFFFFFF) == 0xFFFFFF && screen[6] == 0);
            for (uint32_t x = 0; x < 8; ++x) check((screen[8+x]&0xFFFFFF) == 0xFFFFFF);
            occluded->clear(3); check(occluded->mask_count == 0);
            check(texel_opaque(0x8000,MaskRule::Alpha1555,0) && !texel_opaque(0x7FFF,MaskRule::Alpha1555,0));
            check(texel_opaque(0x8000,MaskRule::Alpha4444,0) && !texel_opaque(0x7FFF,MaskRule::Alpha4444,0));
            check(texel_opaque(5,MaskRule::Corner,4) && !texel_opaque(4,MaskRule::Corner,4));
            const std::array<uint16_t,4> argb{0x0FFF,0xF000,0x7000,0x8123};
            check(build_mask(m,argb.data(),4,4,1,MaskRule::Alpha4444) == 2 && !m.opaque[0] && m.opaque[1] && !m.opaque[2] && m.opaque[3]);
        }
        // Font color: most frequent bright value; transparent key, black and dim shadow never win.
        const auto rgb555 = [](uint16_t r, uint16_t g, uint16_t b) { return uint16_t(r<<10|g<<5|b); };
        std::array<uint16_t,10> shaded{SampleTransparent,0,rgb555(3,3,3),rgb555(3,3,3),rgb555(3,3,3),rgb555(31,16,0),rgb555(31,16,0),rgb555(0,0,31),0x8000,SampleTransparent};
        std::array<uint8_t,3> found{9,9,9};
        check(dominant_color(shaded,found) && found[0] == 255 && found[1] == 132 && found[2] == 0);
        std::array<uint16_t,3> blank{SampleTransparent,0,rgb555(2,2,2)};
        found = {9,9,9}; check(!dominant_color(blank,found) && found[0] == 9);
        // Colors are carried per command, so labels in one raster stay independent.
        FakeSurface two; SurfaceTracker tt;
        FrameList split; split.width = split.height = 4;
        split.add({&g,0,0,{0,0,2,2},{255,0,0}});
        split.add({&g,2,2,{2,2,4,4},{0,0,255}});
        check(paint_surface({&two,9,FakeSurface::lock,FakeSurface::unlock},{0,0,4,4},split,tt).pixels == 6);
        check(two.pixels[2] == 255 && two.pixels[0] == 0 && two.pixels[40] == 255 && two.pixels[42] == 0);
        FakeSurface multiple; SurfaceTracker mt;
        FrameList multi; multi.width = multi.height = 4;
        multi.add({&g,0,0,{0,0,2,2},{255,255,255}});
        multi.add({&g,2,2,{2,2,4,4},{255,255,255}});
        check(paint_surface({&multiple,9,FakeSurface::lock,FakeSurface::unlock},{0,0,4,4},multi,mt).pixels == 6);
        check(multiple.pixels[0] == 255 && multiple.pixels[40] == 255);
        std::cout << "PASS: native frame/cache/metric/clipping/XRGB/surface/failure cases\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
