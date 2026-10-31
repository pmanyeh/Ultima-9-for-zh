#include "engine.h"
#include <intrin.h>
#include <algorithm>
#include <cstring>

namespace u9cht {
Engine* engine = nullptr;
namespace {
void* ctor_gateway = nullptr;
void* copy_gateway = nullptr;
void* layout_after = reinterpret_cast<void*>(0x5C7BBA);
void* bounds_after = reinterpret_cast<void*>(0x5C5F62);
void* glyph_gateway = nullptr;
void* paint_gateway = nullptr;
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
                if (!out || capacity < int(p.length+1)) { e.fail(1); return 0; }
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
            !e.registry.bind(cache, p.length+1, uint32_t(current.plan))) e.fail(3);
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
                ++e.stats[r->plan].raster;
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
                        ++e.stats[r->plan].queue;
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
        ++e.flips;
        for (const auto& q : e.queues) if (q.address && q.last_frame == e.frame) ++e.stats[q.plan].presentations;
    }
    const auto result = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t)>(flip_gateway)(self);
    if (guard.state) { Exclusive lock(guard.state->mutex); ++guard.state->frame; }
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
        if (m.binding && m.offset == 0) {
            auto b = *m.binding; const auto& p = e.pack.plans[b.plan];
            if (f->eax != b.length || word(f->ebp+0xEC) != dest ||
                std::memcmp(reinterpret_cast<void*>(dest), p.slots.data(), b.length) != 0 ||
                !e.registry.bind(dest, b.length, b.plan, b.identity)) e.fail(9);
            else ++e.stats[b.plan].copies;
        }
    } else if (stage == 1 || stage == 2) {
        auto m = e.locate(stage == 1 ? f->ebp : f->edi);
        if (m.binding) {
            auto& stats = e.stats[m.binding->plan];
            if (stage == 1) ++stats.layout; else ++stats.bounds;
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
                *r = {}; r->address = address; r->plan = plan; r->generation = ++e.generations;
                r->paint_generation = paint_generation;
            }
            if (!r) for (auto& item : e.rasters) if (!item.address) {
                r = &item; *r = {}; r->address = address; r->plan = plan; r->generation = ++e.generations; break;
            }
            if (r) r->paint_generation = paint_generation;
            if (!r || r->plan != plan) e.fail(10);
        }
    } else if (stage == 4) {
        const auto caller = word(f->esp+4);
        if (caller == 0x50913D || caller == 0x50915E || caller == 0x50917B || caller == 0x509193) {
            auto* q = e.queue(f->ebx);
            if (q && q->last_frame != e.frame) {
                const auto* r = e.raster(q->raster);
                if (!r || r->generation != q->raster_generation || word(q->address+8) != r->address ||
                    word(f->ecx) != 0x74FBB8 || raster_hash(*r) != r->hash) e.fail(11);
                else { q->last_frame = e.frame; ++e.stats[q->plan].submissions; }
            }
        }
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
__declspec(naked) void glyph_hook() { SAVE_FRAME CALL_STAGE(3) RESTORE_FRAME __asm jmp dword ptr [glyph_gateway] }
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
    // Observe remains byte-for-byte pass-through. Render's fatal-stop policy is
    // installed with the compositor; it is not enabled by this checkpoint.
}
Located Engine::locate(uintptr_t source) noexcept {
    auto found = registry.locate(source);
    if (found.binding) {
        auto& b = *found.binding;
        if (std::memcmp(reinterpret_cast<void*>(b.base), pack.plans[b.plan].slots.data(), b.length) != 0) {
            registry.retire(b.base); fail(12); return {};
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
    if (found.binding && found.offset == 0) { ++stats[found.binding->plan].freed; registry.retire(address); }
    if (auto* q = queue(address)) *q = {};
    if (auto* r = raster(address)) {
        for (auto& q : queues) if (q.raster == address) q = {};
        *r = {};
    }
}
void Engine::install(const Config& config, Logger& logger) {
    log = &logger; render = config.mode == Mode::Render;
    require(!render, "render gate not enabled before observe equivalence");
    pack.load(config_path(config.allowlist_path), render);
    require(sha256(config_path(config.game_dir)/L"static"/L"text.flx") == pack.resource_hash,
            "allowlist resource hash mismatch");
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
        { Exclusive lock(mutex);
          uint32_t live_rasters = 0, live_queues = 0;
          for (const auto& r : rasters) live_rasters += r.address != 0;
          for (const auto& q : queues) live_queues += q.address != 0;
          max_rasters = std::max(max_rasters,live_rasters); max_queues = std::max(max_queues,live_queues);
          fields = "\"milliseconds\":"+std::to_string(GetTickCount64()-started)+",\"frames\":"+std::to_string(flips)+
            ",\"active_calls\":"+std::to_string(active.load())+",\"errors\":"+std::to_string(errors.load())+
            ",\"first_error\":"+std::to_string(first_error.load())+",\"live_buffers\":"+std::to_string(registry.count())+
            ",\"max_buffers\":"+std::to_string(registry.maximum)+",\"live_rasters\":"+std::to_string(live_rasters)+
            ",\"live_queues\":"+std::to_string(live_queues)+",\"entries\":[";
          for (uint32_t i = 0; i < pack.count; ++i) {
              if (i) fields += ','; const auto& s = stats[i];
              fields += "{\"id\":"+std::to_string(pack.plans[i].entry);
#define FIELD(name) fields += ",\"" #name "\":"+std::to_string(s.name)
              FIELD(wide); FIELD(cache); FIELD(copies); FIELD(layout); FIELD(bounds); FIELD(glyph);
              FIELD(raster); FIELD(queue); FIELD(submissions); FIELD(presentations); FIELD(freed);
#undef FIELD
              fields += '}';
          }
          fields += ']';
        }
        Exclusive io(io_gate); log->event(event,fields);
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
    const bool restored = hooks.restore(explicit_unload);
    snapshot(restored ? "runtime_hooks_restored" : "runtime_restore_failed");
    return restored;
}
}
