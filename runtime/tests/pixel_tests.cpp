#include "compositor.h"
#include <iostream>
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
        GlyphKey k; k.scalar = 0x4E2D; k.em = 20; k.mode = GGO_GRAY8_BITMAP|GGO_GLYPH_INDEX;
        auto changed = k; changed.em = 40; check(!(k == changed));
        changed = k; changed.font[0] = L'x'; check(!(k == changed));
        changed = k; changed.scalar = 0x6587; check(!(k == changed));
        changed = k; changed.mode = 1; check(!(k == changed));
        std::array<Glyph,2> cache; cache[0].key = k; cache[1].key = k; cache[1].key.em = 40;
        check(find_glyph(cache,k) == &cache[0] && find_glyph(cache,k) == find_glyph(cache,k));
        changed = k; changed.em = 40; check(find_glyph(cache,changed) == &cache[1]);
        changed.em = 80; check(!find_glyph(cache,changed));
        FakeSurface multiple; SurfaceTracker mt;
        FrameList multi; multi.width = multi.height = 4;
        multi.add({&g,0,0,{0,0,2,2},{255,255,255}});
        multi.add({&g,2,2,{2,2,4,4},{255,255,255}});
        check(paint_surface({&multiple,9,FakeSurface::lock,FakeSurface::unlock},{0,0,4,4},multi,mt).pixels == 6);
        check(multiple.pixels[0] == 255 && multiple.pixels[40] == 255);
        std::cout << "PASS: native frame/cache/metric/clipping/XRGB/surface/failure cases\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
