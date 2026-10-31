#include "engine.h"
#include <intrin.h>
#include <algorithm>
#include <cstring>
#include <cmath>
#include <ddraw.h>
#include <psapi.h>

namespace u9cht {
Engine* engine = nullptr;
namespace {
void* ctor_gateway = nullptr;
void* copy_gateway = nullptr;
void* layout_after = reinterpret_cast<void*>(0x5C7BBA);
void* bounds_after = reinterpret_cast<void*>(0x5C5F62);
void* glyph_gateway = nullptr;
void* paint_gateway = nullptr;
void* raster_begin_after = reinterpret_cast<void*>(0x5CFD56);
void* queue_gateway = nullptr;
void* destroy_gateway = nullptr;
void* free_gateway = nullptr;
void* flip_gateway = nullptr;
void* triangle_original = reinterpret_cast<void*>(0x589F50);
decltype(&WideCharToMultiByte) wide_original = nullptr;
decltype(&ExitProcess) exit_original = nullptr;
struct Constructor { uintptr_t object = 0; int plan = -1; const wchar_t* wide = nullptr; };
thread_local std::array<Constructor, 16> constructors;
thread_local uint32_t constructor_depth = 0;
thread_local uint64_t paint_generation = 0;
alignas(16) thread_local std::array<uint8_t,32> metric_header;
struct Guard {
    Engine* state;
    Guard() noexcept : state(engine && engine->begin() ? engine : nullptr) {}
    ~Guard() { if (state) state->active.fetch_sub(1); }
};
struct Exclusive {
    SRWLOCK& lock;
    explicit Exclusive(SRWLOCK& value) : lock(value) { AcquireSRWLockExclusive(&lock); }
    ~Exclusive() { ReleaseSRWLockExclusive(&lock); }
};
uintptr_t word(uintptr_t p) { return *reinterpret_cast<const uintptr_t*>(p); }
uint64_t raster_hash(const RasterBinding& r) {
    const auto* p = reinterpret_cast<const uint8_t*>(r.pixels);
    uint64_t h = 14695981039346656037ULL;
    for (size_t i = 0; i < size_t(r.stride)*r.height*2; ++i) { h ^= p[i]; h *= 1099511628211ULL; }
    return h;
}
int WINAPI wide_hook(UINT cp, DWORD flags, LPCWCH wide, int length, LPSTR out, int capacity,
                     LPCCH fallback, LPBOOL used) {
    Guard guard;
    if (guard.state && reinterpret_cast<uintptr_t>(_ReturnAddress()) == 0x615B7C &&
        length == -1 && constructor_depth && constructor_depth <= constructors.size()) {
        auto& e = *guard.state;
        const int plan = e.pack.match(wide);
        if (plan >= 0) {
            auto& p = e.pack.plans[size_t(plan)];
            auto& c = constructors[constructor_depth-1]; c.plan = plan; c.wide = wide;
            { Exclusive lock(e.mutex); ++e.stats[size_t(plan)].wide; }
            if (e.render) {
                if (e.errors.load() || !out || capacity < int(p.length+1)) { e.fail(1); return 0; }
                std::memcpy(out, p.slots.data(), p.length+1);
                if (used) *used = FALSE;
                return int(p.length+1);
            }
        }
    }
    return wide_original(cp, flags, wide, length, out, capacity, fallback, used);
}
uintptr_t __fastcall ctor_hook(uintptr_t self, void*, uintptr_t a, uintptr_t b, uintptr_t c) {
    Guard guard;
    const auto fn = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t,uintptr_t,uintptr_t)>(ctor_gateway);
    if (!guard.state) return fn(self,a,b,c);
    auto& e = *guard.state;
    if (constructor_depth >= constructors.size()) { e.fail(2); return fn(self,a,b,c); }
    constructors[constructor_depth++] = {self, -1, nullptr};
    const uintptr_t result = fn(self,a,b,c);
    const auto current = constructors[--constructor_depth];
    if (current.plan >= 0) {
        Exclusive lock(e.mutex);
        const auto& p = e.pack.plans[size_t(current.plan)];
        const auto cache = word(self), wide = word(self+8);
        if (wide != reinterpret_cast<uintptr_t>(current.wide) ||
            std::memcmp(reinterpret_cast<void*>(wide), p.wide.data(), (p.length+1)*2) != 0 ||
            !cache || std::memcmp(reinterpret_cast<void*>(cache), p.slots.data(), p.length+1) != 0 ||
            !e.bind_buffer(cache, p.length+1, uint32_t(current.plan),0,Life::Cache,wide)) e.fail(3);
        else ++e.stats[size_t(current.plan)].cache;
    }
    return result;
}
uintptr_t __fastcall queue_hook(uintptr_t self, void*, uintptr_t raster, uintptr_t x, uintptr_t y,
                               uintptr_t flag, uintptr_t last) {
    Guard guard;
    const auto caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    auto fn = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t)>(queue_gateway);
    const uintptr_t result = fn(self,raster,x,y,flag,last);
    if (guard.state && caller == 0x5CFDBB) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        if (auto* r = e.raster(raster)) {
            const auto w = word(raster+0x14), h = word(raster+0x18), bits = word(raster+0x1C);
            const auto pixels = word(raster+0x43C), stride = word(raster+0x448);
            if (bits != 16 || !w || w > stride || stride > 2048 || !h || h > 256 || !pixels) e.fail(4);
            else {
                r->width = w; r->height = h; r->pixels = pixels; r->stride = stride; r->hash = raster_hash(*r);
                if (e.render) {
                    e.colors.fill(0); uint32_t most = 0;
                    const auto* data = reinterpret_cast<const uint16_t*>(pixels);
                    for (size_t i = 0; i < size_t(stride)*h; ++i) {
                        const uint16_t value = data[i]&0x7FFF;
                        if (value != 0 && value != 0x7C1F &&
                            std::max({(value>>10)&31,(value>>5)&31,value&31}) >= 16) {
                            const auto n = ++e.colors[value]; if (n > most) {
                                most = n; r->rgb = {uint8_t((((value>>10)&31)*255+15)/31),
                                    uint8_t((((value>>5)&31)*255+15)/31),uint8_t(((value&31)*255+15)/31)};
                            }
                        }
                    }
                    uint32_t expected = 0;
                    for (uint32_t i = 0; i < e.pack.plans[r->plan].length; ++i)
                        expected += e.pack.plans[r->plan].wide[i] >= 128;
                    if (r->count != expected) e.fail(14);
                }
                ++e.stats[r->plan].raster;
                if (auto* v = e.trace(Life::RasterReady,r->plan,r->address,r->identity,r->generation,r->pixels)) {
                    v->raster_hash = r->hash; v->width = r->width; v->height = r->height; v->stride = r->stride;
                }
                uintptr_t found = 0;
                for (auto offset : {4, 0x10}) {
                    auto node = word(self+offset);
                    uint32_t remaining = 4096;
                    while (node && remaining--) {
                        if (word(node+8) == raster) {
                            if (found && found != node) { e.fail(5); break; }
                            found = node;
                        }
                        node = word(node+4);
                    }
                    if (node) e.fail(6);
                }
                if (!found) e.fail(7);
                else {
                    auto* q = e.queue(found);
                    if (!q) for (auto& item : e.queues) if (!item.address) { q = &item; break; }
                    if (!q) e.fail(8);
                    else {
                        *q = {found, raster, r->plan, ++e.generations, r->generation, 0};
                        q->identity = r->identity;
                        e.trace(Life::QueueBegin,q->plan,q->address,q->identity,q->generation,raster);
                        ++e.stats[r->plan].queue;
                        uint32_t live = 0; for (const auto& item : e.queues) live += item.address != 0;
                        e.max_queues = std::max(e.max_queues,live);
                    }
                }
            }
        }
    }
    return result;
}
uintptr_t __fastcall paint_hook(uintptr_t self, void*, uintptr_t widget) {
    Guard guard;
    const auto previous = paint_generation;
    if (guard.state) { Exclusive lock(guard.state->mutex); paint_generation = ++guard.state->generations; }
    const auto result = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t)>(paint_gateway)(self,widget);
    paint_generation = previous;
    return result;
}
uintptr_t __fastcall destroy_hook(uintptr_t self, void*) {
    Guard guard;
    if (guard.state) { Exclusive lock(guard.state->mutex); guard.state->retire(self); }
    return reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t)>(destroy_gateway)(self);
}
uintptr_t __cdecl free_hook(uintptr_t pointer) {
    Guard guard;
    if (guard.state) { Exclusive lock(guard.state->mutex); guard.state->retire(pointer); }
    return reinterpret_cast<uintptr_t(__cdecl*)(uintptr_t)>(free_gateway)(pointer);
}
uintptr_t __fastcall flip_hook(uintptr_t self, void*) {
    Guard guard;
    if (guard.state) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        DWORD zero = 0; e.render_thread.compare_exchange_strong(zero,GetCurrentThreadId());
        if (e.render_thread.load() != GetCurrentThreadId()) e.fail(15);
        ++e.flips;
        if (e.render) e.compose(self);
        for (const auto& q : e.queues) if (q.address && q.last_frame == e.frame) ++e.stats[q.plan].presentations;
    }
    const auto result = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t)>(flip_gateway)(self);
    if (guard.state) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        if (e.render && static_cast<int32_t>(result) < 0) e.surface.invalidate();
        ++e.frame; e.draw_list.clear(e.frame);
    }
    return result;
}
void WINAPI exit_hook(UINT code) {
    if (engine) engine->shutdown(false);
    exit_original(code);
}
struct CpuFrame { uint32_t edi, esi, ebp, esp, ebx, edx, ecx, eax, flags; };
extern "C" uintptr_t __cdecl dispatch(uint32_t stage, CpuFrame* f) noexcept {
    Guard guard; if (!guard.state) return 0;
    auto& e = *guard.state; Exclusive lock(e.mutex);
    if (stage == 0) {
        if (f->esi < f->eax || f->edi < f->eax) return 0;
        const auto source = f->esi-f->eax, dest = f->edi-f->eax;
        auto m = e.locate(source);
        const Binding inherited = m.binding ? *m.binding : Binding{};
        // Even a non-allowlisted complete overwrite retires the old destination.
        e.retire_buffer(dest);
        if (m.binding && m.offset == 0) {
            auto b = inherited; const auto& p = e.pack.plans[b.plan];
            if (f->eax != b.length || word(f->ebp+0xEC) != dest ||
                std::memcmp(reinterpret_cast<void*>(dest), p.slots.data(), b.length) != 0 ||
                !e.bind_buffer(dest, b.length, b.plan, b.identity,Life::Copy,source)) e.fail(9);
            else ++e.stats[b.plan].copies;
        }
    } else if (stage == 1 || stage == 2) {
        auto m = e.locate(stage == 1 ? f->ebp : f->edi);
        if (m.binding) {
            auto& stats = e.stats[m.binding->plan];
            if (stage == 1) ++stats.layout; else ++stats.bounds;
            if (e.render && e.pack.plans[m.binding->plan].wide[m.offset] >= 128) {
                const auto font = stage == 1 ? f->ecx : f->edx;
                const auto record = stage == 1 ? f->esi : f->ecx;
                const auto spacing = word(record+4);
                if (spacing >= 16) e.fail(16);
                else {
                    metric_header[0] = logical_metric(spacing);
                    f->eax = reinterpret_cast<uintptr_t>(metric_header.data())-font;
                    ++stats.width_overrides;
                }
            }
        }
    } else if (stage == 3) {
        const auto* s = reinterpret_cast<const uint32_t*>(f->esp+4);
        auto m = s[0] == 0x5C5D09 ? e.locate(s[9]) : Located{};
        if (m.binding) {
            const auto plan = m.binding->plan;
            ++e.stats[plan].glyph;
            const auto address = word(0x133393C);
            auto* r = e.raster(address);
            if (r && paint_generation && r->paint_generation != paint_generation) {
                e.retire(address); r = nullptr;
            }
            if (!r) for (auto& item : e.rasters) if (!item.address) {
                r = &item; *r = {}; r->address = address; r->plan = plan;
                r->generation = ++e.generations; r->identity = m.binding->identity;
                e.trace(Life::RasterBegin,plan,address,r->identity,r->generation,m.binding->base); break;
            }
            if (r) r->paint_generation = paint_generation;
            uint32_t live = 0; for (const auto& item : e.rasters) live += item.address != 0;
            e.max_rasters = std::max(e.max_rasters,live);
            if (!r || r->plan != plan || r->identity != m.binding->identity) e.fail(10);
            else if (e.render && e.pack.plans[plan].wide[m.offset] >= 128) {
                const auto spacing = word(f->ecx+4);
                if ((s[3]&255) != 0x7F || spacing >= 16 || r->count >= r->placements.size()) e.fail(17);
                else {
                    r->placements[r->count++] = {m.offset,int32_t(s[1]),int32_t(s[2])};
                    ++e.stats[plan].unicode_draws;
                    metric_header[0] = logical_metric(spacing);
                    f->eax = reinterpret_cast<uintptr_t>(metric_header.data());
                    return f->eax;
                }
            }
        }
    } else if (stage == 4) {
        const auto caller = word(f->esp+4);
        if (caller == 0x50913D || caller == 0x50915E || caller == 0x50917B || caller == 0x509193) {
            auto* q = e.queue(f->ebx);
            if (q && q->last_frame != e.frame) {
                const auto* r = e.raster(q->raster);
                if (!r || r->generation != q->raster_generation || word(q->address+8) != r->address ||
                    word(f->ecx) != 0x74FBB8 || raster_hash(*r) != r->hash) e.fail(11);
                else {
                    q->last_frame = e.frame; ++e.stats[q->plan].submissions;
                    if (e.render && !e.errors.load()) {
                        const auto width = word(f->ecx+0x44), height = word(f->ecx+0x48);
                        const float sx = *reinterpret_cast<const float*>(f->ebp+0x18);
                        const float sy = *reinterpret_cast<const float*>(f->ebp+0x1C);
                        const float x = *reinterpret_cast<const float*>(q->address+0x18);
                        const float y = *reinterpret_cast<const float*>(q->address+0x20);
                        const auto em = width == 800 && height == 600 ? 20U : width == 1600 && height == 1200 ? 40U : 0U;
                        const auto back = word(f->ecx+0x3FC3C4);
                        auto& list = e.draw_list;
                        if (!em || word(f->ecx+0x4C) != 32 || !std::isfinite(x) || !std::isfinite(y) ||
                            std::abs(x)>10000 || std::abs(y)>10000 ||
                            std::abs(sx-float(width)/640)>0.00001f || std::abs(sy-float(height)/480)>0.00001f ||
                            list.epoch != e.frame || (list.records && (list.backend != f->ecx || list.backbuffer != back))) e.fail(18);
                        else {
                            list.backend = f->ecx; list.backbuffer = back; list.width = width; list.height = height;
                            if (!list.add_record({q->address,r->address,q->generation,r->generation,q->plan})) e.fail(19);
                            const auto round = [](float v) { return static_cast<int32_t>(std::lround(v)); };
                            const auto clip = intersect({round(x*sx),round(y*sy),round((x+r->width)*sx),round((y+r->height)*sy)},
                                {0,0,int32_t(width),int32_t(height)});
                            for (uint32_t i = 0; i < r->count; ++i) {
                                const auto& p = r->placements[i]; const auto scalar = e.pack.plans[r->plan].wide[p.offset];
                                const auto* g = e.glyphs.get(scalar,em);
                                if (!g) { ++e.stats[r->plan].cache_misses; e.fail(20); break; }
                                ++e.stats[r->plan].cache_hits;
                                const int32_t left = round((x+p.x)*sx)+g->bearing_x;
                                const int32_t top = round((y+p.y)*sy)-g->bearing_y;
                                const auto bounds = intersect(clip,{left,top,left+int32_t(g->width),top+int32_t(g->height)});
                                if (!empty(bounds) && !list.add({g,left,top,bounds,r->rgb})) e.fail(21);
                            }
                        }
                    }
                }
            }
        }
    } else if (stage == 5) {
        // Actual repaint begins after allocation/early-return branches. Retire
        // an old raster identity even if the new text is outside the allowlist.
        e.retire(f->ebx);
    }
    return 0;
}
// Inline interiors preserve integer state, flags, x87 and SSE around C++.
// ESI holds the original PUSHAD frame after saving the game's ESI. FXSAVE's
// scratch area is aligned independently, then the exact stack is restored.
#define SAVE_FRAME __asm pushfd __asm pushad __asm mov esi, esp __asm sub esp, 528 __asm and esp, -16 __asm fxsave [esp]
#define CALL_STAGE(n) __asm push esi __asm push n __asm call dispatch __asm add esp, 8
#define RESTORE_FRAME __asm fxrstor [esp] __asm mov esp, esi __asm popad __asm popfd
__declspec(naked) void copy_hook() { SAVE_FRAME CALL_STAGE(0) RESTORE_FRAME __asm jmp dword ptr [copy_gateway] }
__declspec(naked) void layout_hook() {
    __asm mov eax, dword ptr [ecx+eax*8-0xF0]
    SAVE_FRAME CALL_STAGE(1) RESTORE_FRAME __asm jmp dword ptr [layout_after]
}
__declspec(naked) void bounds_hook() {
    __asm mov eax, dword ptr [edx+eax*8-0xF0]
    SAVE_FRAME CALL_STAGE(2) RESTORE_FRAME __asm jmp dword ptr [bounds_after]
}
__declspec(naked) void glyph_hook() {
    SAVE_FRAME CALL_STAGE(3)
    __asm test eax, eax
    __asm jz native_glyph
    RESTORE_FRAME __asm ret 12
native_glyph:
    RESTORE_FRAME __asm jmp dword ptr [glyph_gateway]
}
__declspec(naked) void raster_begin_hook() {
    __asm mov dword ptr ds:[0x133393C], ebx
    SAVE_FRAME CALL_STAGE(5) RESTORE_FRAME __asm jmp dword ptr [raster_begin_after]
}
__declspec(naked) void triangle_hook() { SAVE_FRAME CALL_STAGE(4) RESTORE_FRAME __asm jmp dword ptr [triangle_original] }
#undef SAVE_FRAME
#undef CALL_STAGE
#undef RESTORE_FRAME
DWORD WINAPI diagnostics_worker(void* arg) {
    auto& e = *static_cast<Engine*>(arg);
    while (WaitForSingleObject(e.stop.get(), 5000) == WAIT_TIMEOUT) e.snapshot("runtime_counters");
    return 0;
}
}
bool Engine::begin() noexcept {
    if (!accepting.load()) return false;
    active.fetch_add(1);
    if (!accepting.load()) { active.fetch_sub(1); return false; }
    entered.store(true); return true;
}
void Engine::fail(uint32_t code) noexcept {
    uint32_t zero = 0; first_error.compare_exchange_strong(zero, code); errors.fetch_add(1);
    if (render && zero == 0) {
        const auto thread = render_thread.load();
        PostThreadMessageW(thread ? thread : GetCurrentThreadId(),WM_QUIT,0,0);
    }
}
Located Engine::locate(uintptr_t source) noexcept {
    auto found = registry.locate(source);
    if (found.binding) {
        auto& b = *found.binding;
        if (std::memcmp(reinterpret_cast<void*>(b.base), pack.plans[b.plan].slots.data(), b.length) != 0) {
            retire_buffer(b.base); fail(12); return {};
        }
    }
    return found;
}
RasterBinding* Engine::raster(uintptr_t address) noexcept {
    for (auto& r : rasters) if (address && r.address == address) return &r;
    return nullptr;
}
QueueBinding* Engine::queue(uintptr_t address) noexcept {
    for (auto& q : queues) if (address && q.address == address) return &q;
    return nullptr;
}
void Engine::retire(uintptr_t address) noexcept {
    const auto found = registry.locate(address);
    if (found.binding && found.offset == 0) { ++stats[found.binding->plan].freed; retire_buffer(address); }
    if (auto* q = queue(address)) {
        trace(Life::QueueEnd,q->plan,q->address,q->identity,q->generation,q->raster);
        ++stats[q->plan].queue_retired; *q = {};
    }
    if (auto* r = raster(address)) {
        for (auto& q : queues) if (q.address && q.raster == address) {
            trace(Life::QueueEnd,q.plan,q.address,q.identity,q.generation,q.raster);
            ++stats[q.plan].queue_retired; q = {};
        }
        trace(Life::RasterEnd,r->plan,address,r->identity,r->generation,r->pixels);
        ++stats[r->plan].raster_retired;
        *r = {};
    }
}
LifeEvent* Engine::trace(Life kind, uint32_t plan, uintptr_t address, uint64_t identity, uint64_t generation, uintptr_t related) noexcept {
    if (life_count >= life_events.size()) { ++life_dropped; fail(27); return nullptr; }
    life_events[life_count++] = {++life_sequence,GetTickCount64(),identity,generation,address,related,plan,kind};
    return &life_events[life_count-1];
}
void Engine::retire_buffer(uintptr_t address) noexcept {
    const auto located = registry.locate(address);
    if (located.binding && located.offset == 0) {
        const auto b = *located.binding;
        trace(Life::BufferEnd,b.plan,address,b.identity,b.generation);
        registry.retire(address);
    }
}
Binding* Engine::bind_buffer(uintptr_t address, uint32_t length, uint32_t plan, uint64_t identity, Life kind, uintptr_t related) noexcept {
    retire_buffer(address);
    auto* b = registry.bind(address,length,plan,identity);
    if (b) trace(kind,plan,address,b->identity,b->generation,related);
    return b;
}
void Engine::compose(uintptr_t backend) noexcept {
    auto& list = draw_list;
    if (!list.count) return;
    max_frame_records = std::max(max_frame_records,list.records);
    if (errors.load()) { ++skipped_frames; return; }
    if (!list.current(frame,backend,word(backend+0x3FC3C4))) {
        ++skipped_frames; surface.invalidate(); return;
    }
    if (word(backend) != 0x74FBB8 ||
        word(backend+0x44) != list.width || word(backend+0x48) != list.height ||
        word(backend+0x4C) != 32 || *reinterpret_cast<const uint8_t*>(backend+0x3FC508)) {
        ++skipped_frames; fail(22); return;
    }
    if (*reinterpret_cast<const uint8_t*>(backend+0x3FC509)) { ++skipped_frames; surface.invalidate(); return; }
    const auto back = word(backend+0x3FC3C4);
    if (back != list.backbuffer) { ++skipped_frames; surface.invalidate(); return; }
    if (!back || word(back) != 0x18153838) { ++skipped_frames; fail(23); return; }
    const auto root = word(back+8), inner = root ? root+0xC : 0;
    if (!inner || word(inner) != 0x18152DF4) { ++skipped_frames; fail(24); return; }
    for (uint32_t i = 0; i < list.records; ++i) {
        const auto& source = list.sources[i]; const auto* q = queue(source.node); const auto* r = raster(source.raster);
        if (!q || !r || q->generation != source.queue_generation || r->generation != source.raster_generation ||
            q->last_frame != frame || q->raster_generation != r->generation || raster_hash(*r) != r->hash) {
            ++skipped_frames; return; // A verified native repaint/free made the command stale.
        }
    }
    Rect locked = list.commands[0].clip;
    for (uint32_t i = 1; i < list.count; ++i) {
        const auto r = list.commands[i].clip;
        locked = {std::min(locked.left,r.left),std::min(locked.top,r.top),
            std::max(locked.right,r.right),std::max(locked.bottom,r.bottom)};
    }
    locked = intersect(locked,{0,0,int32_t(list.width),int32_t(list.height)});
    if (empty(locked)) { ++skipped_frames; return; }
    auto lock = reinterpret_cast<SurfaceLock>(word(word(back)+0x64));
    auto unlock = reinterpret_cast<SurfaceUnlock>(word(word(back)+0x80));
    LARGE_INTEGER begin{},end{};
    QueryPerformanceCounter(&begin);
    uint32_t error = 0; bool composed = false;
    {
        // Acquire the disk-log exclusion BEFORE Lock. The worker never performs
        // I/O while this gate is held. No own heap/GDI/logging inside this block.
        Exclusive io(io_gate);
        const auto result = paint_surface({reinterpret_cast<void*>(back),backend,lock,unlock},locked,list,surface);
        pixel_writes += result.pixels;
        composed = result.status == PaintStatus::Painted;
        if (!composed) ++skipped_frames;
        if (result.status == PaintStatus::LockFailed) ++lock_failures;
        if (result.status == PaintStatus::InvalidDescriptor) error = 25;
        if (result.status == PaintStatus::UnlockFailed) { ++unlock_failures; error = 26; }
    }
    QueryPerformanceCounter(&end);
    const auto ticks = uint64_t(end.QuadPart-begin.QuadPart);
    compositor_ticks += ticks; compositor_max_ticks = std::max(compositor_max_ticks,ticks);
    if (composed) {
        ++composite_count; unicode_runs += list.records;
        for (uint32_t i = 0; i < list.records; ++i) ++stats[list.sources[i].plan].composites;
    }
    if (error) fail(error); // Controlled quit only AFTER Unlock and log-gate release.
}
void Engine::install(const Config& config, Logger& logger) {
    log = &logger; render = config.mode == Mode::Render;
    pack.load(config_path(config.allowlist_path), render);
    require(sha256(config_path(config.game_dir)/L"static"/L"text.flx") == pack.resource_hash,
            "allowlist resource hash mismatch");
    log->event("runtime_corpus", "\"mode\":\""+std::string(render?"render":"observe")+
        "\",\"resource_sha256\":\""+utf8(pack.resource_hash)+"\",\"entries\":"+std::to_string(pack.count));
    if (render) {
        glyphs.open(config_path(config.font_path));
        for (uint32_t i = 0; i < pack.count; ++i) for (uint32_t j = 0; j < pack.plans[i].length; ++j)
            if (pack.plans[i].wide[j] >= 128) for (auto em : {20U,40U}) glyphs.warm(pack.plans[i].wide[j],em);
        for (auto scalar : {0x4E2DU,0x6587U}) for (auto em : {20U,40U}) if (const auto* g = glyphs.get(scalar,em))
            log->event("glyph_cache_warm", "\"scalar\":"+std::to_string(scalar)+",\"em\":"+std::to_string(em)+
                ",\"index\":"+std::to_string(g->index)+",\"width\":"+std::to_string(g->width)+
                ",\"height\":"+std::to_string(g->height)+",\"advance\":"+std::to_string(g->advance)+
                ",\"coverage_sha256\":\""+utf8(sha256_bytes(g->alpha.data(),g->alpha.size()))+"\"");
    }
    draw_list.clear(frame);
    auto prepare = [&](const char* name, uintptr_t address, void* target,
                       std::initializer_list<uint8_t> bytes, std::initializer_list<uint8_t> lengths) {
        return hooks.prepare_inline(name, reinterpret_cast<void*>(address), target,
            {bytes.begin(),bytes.size()}, {lengths.begin(),lengths.size()});
    };
    ctor_gateway = prepare("constructor",0x615A10,ctor_hook,{0x6A,0xFF,0x68,0x26,0x46,0x73,0},{2,5});
    copy_gateway = prepare("full_copy",0x41BC61,copy_hook,{0x33,0xFF,0xC7,0x44,0x24,0x20,0x58,2,0,0},{2,8});
    prepare("layout_width",0x5C7BB3,layout_hook,{0x8B,0x84,0xC1,0x10,0xFF,0xFF,0xFF},{7});
    prepare("bounds_width",0x5C5F5B,bounds_hook,{0x8B,0x84,0xC2,0x10,0xFF,0xFF,0xFF},{7});
    glyph_gateway = prepare("glyph",0x5C5A80,glyph_hook,{0x8B,0x54,0x24,0x0C,0x80,0xFA,0x20},{4,3});
    paint_gateway = prepare("paint_cache",0x5CFCE0,paint_hook,{0x64,0xA1,0,0,0,0},{6});
    prepare("raster_repaint",0x5CFD50,raster_begin_hook,{0x89,0x1D,0x3C,0x39,0x33,1},{6});
    queue_gateway = prepare("raster_queue",0x508D50,queue_hook,{0x8A,0x44,0x24,0x10,0x53},{4,1});
    destroy_gateway = prepare("queue_destroy",0x5083F0,destroy_hook,{0x6A,0xFF,0x68,0xA8,0xE3,0x72,0},{2,5});
    free_gateway = prepare("engine_free",0x7108E0,free_hook,{0x8B,0x44,0x24,4,0x50},{4,1});
    flip_gateway = prepare("pre_flip",0x597B00,flip_hook,{0x56,0x8B,0xF1,0x8A,0x86,9,0xC5,0x3F,0},{1,2,6});
    wide_original = &WideCharToMultiByte;
    exit_original = &ExitProcess;
    hooks.prepare_pointer("wide_conversion",reinterpret_cast<uintptr_t*>(0x74010C),
                          reinterpret_cast<uintptr_t>(wide_original),reinterpret_cast<uintptr_t>(wide_hook));
    hooks.prepare_pointer("exit",reinterpret_cast<uintptr_t*>(0x74024C),
                          reinterpret_cast<uintptr_t>(exit_original),reinterpret_cast<uintptr_t>(exit_hook));
    hooks.prepare_pointer("native_submission",reinterpret_cast<uintptr_t*>(0x74FBB8+0x60),
                          reinterpret_cast<uintptr_t>(triangle_original),reinterpret_cast<uintptr_t>(triangle_hook));
    for (const auto& r : hooks.records()) {
        auto hex = [](const std::vector<uint8_t>& bytes) {
            constexpr char digits[] = "0123456789abcdef"; std::string out;
            for (auto b : bytes) { out += digits[b>>4]; out += digits[b&15]; } return out;
        };
        log->event("hook_manifest", "\"name\":\""+r.name+"\",\"va\":"+std::to_string(r.address)+
            ",\"rva\":"+std::to_string(r.address-0x400000)+",\"original\":\""+hex(r.original)+
            "\",\"replacement\":\""+hex(r.replacement)+"\",\"gateway\":"+
            std::to_string(reinterpret_cast<uintptr_t>(r.gateway)));
    }
    stop.reset(CreateEventW(nullptr, TRUE, FALSE, nullptr)); require(bool(stop), "worker stop event failed");
    started = GetTickCount64(); hooks.install(); accepting.store(true);
    worker.reset(CreateThread(nullptr,0,diagnostics_worker,this,0,nullptr));
    require(bool(worker), "diagnostics worker failed");
}
void Engine::snapshot(const char* event) noexcept {
    try {
        std::string fields;
        PROCESS_MEMORY_COUNTERS_EX memory{}; memory.cb = sizeof(memory);
        const bool memory_known = GetProcessMemoryInfo(GetCurrentProcess(),reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&memory),sizeof(memory)) != FALSE;
        LARGE_INTEGER frequency{}; QueryPerformanceFrequency(&frequency);
        { Exclusive lock(mutex);
          uint32_t live_rasters = 0, live_queues = 0;
          for (const auto& r : rasters) live_rasters += r.address != 0;
          for (const auto& q : queues) live_queues += q.address != 0;
          max_rasters = std::max(max_rasters,live_rasters); max_queues = std::max(max_queues,live_queues);
          fields = "\"milliseconds\":"+std::to_string(GetTickCount64()-started)+",\"frames\":"+std::to_string(flips)+
            ",\"active_calls\":"+std::to_string(active.load())+",\"errors\":"+std::to_string(errors.load())+
            ",\"first_error\":"+std::to_string(first_error.load())+",\"live_buffers\":"+std::to_string(registry.count())+
            ",\"max_buffers\":"+std::to_string(registry.maximum)+",\"live_rasters\":"+std::to_string(live_rasters)+
            ",\"live_queues\":"+std::to_string(live_queues)+",\"glyph_cache_entries\":"+std::to_string(glyphs.size())+
            ",\"max_rasters\":"+std::to_string(max_rasters)+",\"max_queues\":"+std::to_string(max_queues)+
            ",\"private_bytes\":"+std::to_string(memory_known?memory.PrivateUsage:0)+
            ",\"working_set_bytes\":"+std::to_string(memory_known?memory.WorkingSetSize:0)+
            ",\"qpc_frequency\":"+std::to_string(frequency.QuadPart)+
            ",\"cache_hits\":"+std::to_string(glyphs.hits)+",\"cache_misses\":"+std::to_string(glyphs.misses)+
            ",\"composite_frames\":"+std::to_string(composite_count)+",\"unicode_runs\":"+std::to_string(unicode_runs)+
            ",\"surface_generation\":"+std::to_string(surface.generation)+",\"lock_failures\":"+std::to_string(lock_failures)+
            ",\"unlock_failures\":"+std::to_string(unlock_failures)+",\"skipped_frames\":"+std::to_string(skipped_frames)+
            ",\"max_frame_records\":"+std::to_string(max_frame_records)+",\"pixel_writes\":"+std::to_string(pixel_writes)+
            ",\"compositor_ticks\":"+std::to_string(compositor_ticks)+",\"compositor_max_ticks\":"+std::to_string(compositor_max_ticks)+
            ",\"entries\":[";
          for (uint32_t i = 0; i < pack.count; ++i) {
              if (i) fields += ','; const auto& s = stats[i];
              fields += "{\"id\":"+std::to_string(pack.plans[i].entry);
#define FIELD(name) fields += ",\"" #name "\":"+std::to_string(s.name)
              FIELD(wide); FIELD(cache); FIELD(copies); FIELD(layout); FIELD(bounds); FIELD(glyph);
              FIELD(raster); FIELD(queue); FIELD(submissions); FIELD(presentations); FIELD(freed);
              FIELD(width_overrides); FIELD(unicode_draws); FIELD(composites); FIELD(cache_hits); FIELD(cache_misses);
              FIELD(raster_retired); FIELD(queue_retired);
#undef FIELD
              fields += '}';
          }
          fields += "],\"lifecycle_dropped\":"+std::to_string(life_dropped)+",\"lifecycle\":[";
          for (uint32_t i = 0; i < life_count; ++i) {
              const auto& v = life_events[i]; if (i) fields += ',';
              fields += "{\"seq\":"+std::to_string(v.sequence)+",\"tick_ms\":"+std::to_string(v.tick)+
                  ",\"kind\":"+std::to_string(static_cast<uint32_t>(v.kind))+
                  ",\"entry\":"+std::to_string(pack.plans[v.plan].entry)+",\"address\":"+std::to_string(v.address)+
                  ",\"related\":"+std::to_string(v.related)+",\"identity\":"+std::to_string(v.identity)+
                  ",\"generation\":"+std::to_string(v.generation)+",\"raster_hash_fnv1a64\":"+std::to_string(v.raster_hash)+
                  ",\"width\":"+std::to_string(v.width)+",\"height\":"+std::to_string(v.height)+
                  ",\"stride_pixels\":"+std::to_string(v.stride)+"}";
          }
          fields += ']'; life_count = 0;
        }
        Exclusive io(io_gate); log->event(event,fields);
        if (log->failures()) fail(28);
    } catch (...) { fail(13); }
}
bool Engine::shutdown(bool explicit_unload) noexcept {
    if (explicit_unload && entered.load()) return false; // No live hot-unload claim.
    accepting.store(false);
    if (stop) SetEvent(stop.get());
    if (worker && WaitForSingleObject(worker.get(),10000) != WAIT_OBJECT_0) return false;
    worker.reset(); stop.reset();
    const auto deadline = GetTickCount64()+10000;
    while (active.load() && GetTickCount64() < deadline) Sleep(1);
    if (active.load()) return false;
    trace(Life::Shutdown,0,0,0,0);
    // Retire only our metadata; native allocations are still owned by U9.
    // Shutdown event distinguishes this cleanup from native lifetime endings.
    for (const auto& r : rasters) if (r.address) retire(r.address);
    for (const auto& q : queues) if (q.address) retire(q.address);
    for (const auto& b : registry.bindings()) if (b.base) retire_buffer(b.base);
    draw_list.clear(frame);
    const bool restored = hooks.restore(explicit_unload);
    if (log) snapshot(restored ? "runtime_hooks_restored" : "runtime_restore_failed");
    const bool font_removed = glyphs.close();
    if (log) log->event("runtime_cleanup", "\"hooks_restored\":"+std::string(restored?"true":"false")+
        ",\"active_calls\":0,\"private_font_removed\":"+(font_removed?"true":"false")+
        ",\"worker_handles_closed\":true,\"gateways_retained\":"+
        (explicit_unload?"false":"true"));
    return restored && font_removed;
}
}
