#include "engine.h"
#include <intrin.h>
#include <algorithm>
#include <cstdio>
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
void* journal_word_after = reinterpret_cast<void*>(0x5C637F);
void* journal_trim_after = reinterpret_cast<void*>(0x5C6F61);
void* glyph_gateway = nullptr;
void* paint_gateway = nullptr;
void* raster_begin_after = reinterpret_cast<void*>(0x5CFD56);
void* queue_gateway = nullptr;
void* destroy_gateway = nullptr;
void* free_gateway = nullptr;
void* name_copy_gateway = nullptr;
void* name_destroy_gateway = nullptr;
void* flip_gateway = nullptr;
void* flow_gateway = nullptr;
void* triangle_original = reinterpret_cast<void*>(0x589F50);
decltype(&WideCharToMultiByte) wide_original = nullptr;
decltype(&ExitProcess) exit_original = nullptr;
struct Constructor { uintptr_t object = 0; int plan = -1; const wchar_t* wide = nullptr; };
thread_local std::array<Constructor, 16> constructors;
thread_local uint32_t constructor_depth = 0;
thread_local uint64_t paint_generation = 0;
thread_local uintptr_t paint_owner = 0, paint_widget = 0, paint_caller = 0;
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
    if (guard.state && reinterpret_cast<uintptr_t>(_ReturnAddress()) == 0x615DF7) {
        // Journal append conversion (0x615db0, only caller 0x42e0a6). P8-3 J2: an allowlisted entry is
        // written as the locale-independent marker U9J<entry>, which always fits the native wcslen+1 buffer.
        auto& e = *guard.state;
        const int plan = e.render && wide && length == -1 ? e.pack.match(wide) : -1;
        if (plan >= 0 && !e.pack.plans[size_t(plan)].is_name()) {
            const auto entry = e.pack.plans[size_t(plan)].entry;
            char marker[16]{};
            const int n = std::snprintf(marker, sizeof marker, "U9J%u", entry);
            JournalAppend v{};
            v.tick = GetTickCount64(); v.code_page = cp == CP_ACP ? GetACP() : cp; v.capacity = uint32_t(capacity);
            v.wide_length = uint32_t(wcsnlen(wide, 65536)); v.entry = int32_t(entry);
            if (out && n > 0 && capacity >= n+1) {
                std::memcpy(out, marker, size_t(n)+1);
                if (used) *used = FALSE;
                v.result = n+1; v.marker = true;
                Exclusive lock(e.mutex);
                ++e.journal_markers;
                if (e.journal_append_total < e.journal_appends.size()) e.journal_appends[size_t(e.journal_append_total)] = v;
                ++e.journal_append_total;
                return n+1;
            }
            Exclusive lock(e.mutex); ++e.journal_marker_short; // too short for a marker: native conversion below
        }
        SetLastError(0);
        const int result = wide_original(cp, flags, wide, length, out, capacity, fallback, used);
        const DWORD error = result ? 0 : GetLastError();
        JournalAppend v{};
        v.tick = GetTickCount64(); v.code_page = cp == CP_ACP ? GetACP() : cp;
        v.capacity = uint32_t(capacity); v.result = result; v.error = error;
        if (wide) {
            v.wide_length = uint32_t(wcsnlen(wide, 65536));
            const int matched = length == -1 ? e.pack.match(wide) : -1;
            v.entry = matched >= 0 ? int32_t(e.pack.plans[size_t(matched)].entry) : -1;
        }
        if (out && result > 0) for (int i = 0; i < result; ++i) v.high_bytes += static_cast<uint8_t>(out[i]) >= 0x80;
        { Exclusive lock(e.mutex);
          if (e.journal_append_total < e.journal_appends.size()) e.journal_appends[size_t(e.journal_append_total)] = v;
          ++e.journal_append_total; }
        SetLastError(error);
        return result;
    }
    if (guard.state && reinterpret_cast<uintptr_t>(_ReturnAddress()) == BookConvertReturn && length == -1 && wide) {
        // P9-4: the book reader 0x42E560 converts a BOM-marked UTF-16 body. An exactly matching book plan is
        // written as its slot string (CJK -> 0x7F); the next flow initializer maps each slot back to its scalar.
        auto& e = *guard.state;
        const auto n = wcsnlen(wide, MaxBookText+1);
        const int plan = e.render && n <= MaxBookText ? e.pack.match_book(wide, n) : -1;
        if (plan >= 0) {
            const auto& p = e.pack.plans[size_t(plan)];
            Exclusive lock(e.mutex);
            if (out && capacity >= int(p.length+1)) {
                std::memcpy(out, p.slots.data(), p.length+1);
                if (used) *used = FALSE;
                e.pending_book = plan; ++e.book_converts;
                return int(p.length+1);
            }
            ++e.book_short;
        }
    }
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
    const auto caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    if (constructor_depth >= constructors.size()) { e.fail(2); return fn(self,a,b,c); }
    constructors[constructor_depth++] = {self, -1, nullptr};
    const uintptr_t result = fn(self,a,b,c);
    const auto current = constructors[--constructor_depth];
    // P10-1 M1: a string from the misctext factory 0x616120 carries a marker instead of a bound cache.
    // On any failure it falls back to the ordinary binding below (visible native slots, never a quit).
    if (current.plan >= 0 && caller == MiscTextCtorReturn && e.render && e.texture_enabled &&
        word(self+8) == reinterpret_cast<uintptr_t>(current.wide) && e.mark_misc(self,uint32_t(current.plan))) {
        Exclusive lock(e.mutex); ++e.stats[size_t(current.plan)].cache; ++e.misc_marked;
        return result;
    }
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
struct FlowText { uintptr_t text = 0; uint32_t length = 0, high = 0; uint64_t hash = 14695981039346656037ULL; };
// Reads `*text_ref` under SEH: the caller passes a char** whose target is game-owned.
bool copy_guarded(uintptr_t source, char* out, uint32_t n) noexcept {
    __try { std::memcpy(out,reinterpret_cast<const void*>(source),n); return true; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
bool write_guarded(uintptr_t target, const void* data, uint32_t n) noexcept {
    __try { std::memcpy(reinterpret_cast<void*>(target),data,n); return true; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
bool read_flow_text(uintptr_t text_ref, FlowText& t) noexcept {
    __try {
        if (!text_ref) return true;
        t.text = word(text_ref);
        if (!t.text) return true;
        const auto* p = reinterpret_cast<const uint8_t*>(t.text);
        while (t.length < 0x10000 && p[t.length]) {
            t.high += p[t.length] >= 0x80; t.hash ^= p[t.length]; t.hash *= 1099511628211ULL; ++t.length;
        }
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
using NativeBlit = uintptr_t(__thiscall*)(uintptr_t,uintptr_t,int32_t,int32_t);
const auto native_blit = reinterpret_cast<NativeBlit>(0x5E20E0);
// P8-3 texture writer. For each covered pixel the raster clip (+4..+0x10, inclusive) is narrowed to that
// pixel and the native blit copies one solid ink pixel of a native glyph there. Pixel format, palette and
// auxiliary planes therefore stay the game's own. Returns pixels written, or UINT32_MAX on a fault.
uint32_t texture_glyph(uintptr_t raster, const InkProbe& ink, const uint8_t* alpha, uint32_t width, uint32_t height,
                       int32_t left, int32_t top) noexcept {
    int32_t clip[4]{};
    bool saved = false;
    uint32_t written = 0;
    __try {
        std::memcpy(clip,reinterpret_cast<const void*>(raster+4),sizeof clip);
        saved = true;
        auto* live = reinterpret_cast<int32_t*>(raster+4);
        for (uint32_t row = 0; row < height; ++row) for (uint32_t col = 0; col < width; ++col) {
            if (alpha[size_t(row)*width+col] < 112) continue;
            const int32_t x = left+int32_t(col), y = top+int32_t(row);
            if (x < clip[0] || y < clip[1] || x > clip[2] || y > clip[3]) continue;
            live[0] = x; live[1] = y; live[2] = x; live[3] = y;
            native_blit(raster,ink.glyph,x+ink.dx,y+ink.dy);
            ++written;
        }
        std::memcpy(reinterpret_cast<void*>(raster+4),clip,sizeof clip);
        return written;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        if (saved) std::memcpy(reinterpret_cast<void*>(raster+4),clip,sizeof clip);
        return UINT32_MAX;
    }
}
struct ProbeBuffers { uint16_t* a; uint16_t* b; uint16_t* aux; uint32_t size; };
uint32_t probe_value(const ProbeBuffers& q, bool sixteen, uint32_t x, uint32_t y, bool& solid) noexcept {
    const size_t i = size_t(y)*q.size+x;
    if (sixteen) { solid = q.a[i] == q.b[i]; return q.a[i]; }
    const auto* a8 = reinterpret_cast<const uint8_t*>(q.a); const auto* b8 = reinterpret_cast<const uint8_t*>(q.b);
    solid = a8[i] == b8[i]; return a8[i];
}
void fake_set(uint8_t* fake, size_t at, uintptr_t value) noexcept { std::memcpy(fake+at,&value,4); }
// Draws reference glyphs privately twice (different backgrounds). Pixels equal in both runs were written
// solidly; the most common written value at its most enclosed position becomes the ink sample.
bool probe_ink(uintptr_t raster, InkProbe& ink, const ProbeBuffers& q) noexcept {
    __try {
        uint8_t fake[0x44C];
        std::memcpy(fake,reinterpret_cast<const void*>(raster),sizeof fake);
        const auto address = reinterpret_cast<uintptr_t>(fake);
        const bool sixteen = ink.type == 2;
        const uint32_t size = q.size;
        fake_set(fake,4,0); fake_set(fake,8,0); fake_set(fake,0xC,size-1); fake_set(fake,0x10,size-1);
        fake_set(fake,0x14,size); fake_set(fake,0x18,size); fake_set(fake,0x448,size);
        const bool has_aux = word(raster+0x444) != 0;
        if (has_aux) fake_set(fake,0x444,reinterpret_cast<uintptr_t>(q.aux));
        const uint32_t refs[6] = {'I','l','H','M','E','1'};
        for (const uint32_t c : refs) {
            const auto offset = word(ink.blob+c*8-0xF0);
            if (!offset) continue;
            const auto glyph = ink.blob+offset;
            const auto w = word(glyph+4), h = word(glyph+8);
            if (!w || !h || w+8 > size || h+8 > size) continue;
            const int32_t X = int32_t(word(glyph+0xC))+4, Y = int32_t(word(glyph+0x10))+4;
            std::memset(q.a,0x00,size_t(size)*size*2);
            if (has_aux) std::memset(q.aux,0x00,size_t(size)*size*4);
            fake_set(fake,0x43C,reinterpret_cast<uintptr_t>(q.a)); native_blit(address,glyph,X,Y);
            std::memset(q.b,0xFF,size_t(size)*size*2);
            if (has_aux) std::memset(q.aux,0xFF,size_t(size)*size*4);
            fake_set(fake,0x43C,reinterpret_cast<uintptr_t>(q.b)); native_blit(address,glyph,X,Y);
            uint32_t values[32]{}, counts[32]{}, distinct = 0, written = 0;
            for (uint32_t y = 0; y < size; ++y) for (uint32_t x = 0; x < size; ++x) {
                bool solid = false; const auto v = probe_value(q,sixteen,x,y,solid);
                if (!solid) continue;
                ++written;
                uint32_t k = 0; while (k < distinct && values[k] != v) ++k;
                if (k == distinct) { if (distinct == 32) continue; values[distinct++] = v; }
                ++counts[k];
            }
            // P9-4: book fonts are anti-aliased; their glyphs carry several shades with light edge tones.
            // The ink is the darkest shade that recurs (luminance from 5-bit fields; the order is the same
            // for RGB555 and RGB565). A single-shade journal font yields its only value as before.
            const auto luma = [&](uint32_t v) { return sixteen ? 2*((v>>10)&31)+5*((v>>5)&31)+(v&31) : v; };
            int32_t pick = -1;
            for (uint32_t k = 0; k < distinct; ++k)
                if (counts[k] >= 2 && (pick < 0 || luma(values[k]) < luma(values[uint32_t(pick)]))) pick = int32_t(k);
            if (pick < 0) continue;
            const uint32_t best = uint32_t(pick);
            int32_t px = -1, py = -1; uint32_t enclosed = 0;
            for (uint32_t y = 1; y+1 < size; ++y) for (uint32_t x = 1; x+1 < size; ++x) {
                bool solid = false;
                if (probe_value(q,sixteen,x,y,solid) != values[best] || !solid) continue;
                uint32_t n = 0;
                for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
                    bool s2 = false; n += probe_value(q,sixteen,x+dx,y+dy,s2) == values[best] && s2;
                }
                if (px < 0 || n > enclosed) { px = int32_t(x); py = int32_t(y); enclosed = n; }
            }
            if (px < 0) continue;
            ink.glyph = glyph; ink.dx = X-px; ink.dy = Y-py; ink.value = values[best];
            ink.solid = enclosed; ink.written = written; ink.reference = c; ink.usable = true;
            return true;
        }
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
// P8-2 probe: paged text-flow initializer 0x5C7620 (thiscall, 4 args). Observe only.
uintptr_t __fastcall flow_hook(uintptr_t self, void*, uintptr_t widget, uintptr_t text_ref, uintptr_t a3, uintptr_t a4) {
    Guard guard;
    const auto caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    const auto fn = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t)>(flow_gateway);
    if (!guard.state) return fn(self,widget,text_ref,a3,a4);
    FlowText t;
    bool readable = read_flow_text(text_ref,t);
    // P8-3: the journal page loader passes &page+0xC8, a game-allocated copy of diary.txt.
    bool leading = false;
    std::array<int32_t,64> saved_leading{}; uint32_t records = 0; uintptr_t table = 0;
    if (guard.state->render && caller == 0x426648 && readable && t.text && t.length) {
        leading = guard.state->expand_journal(text_ref,t.text,t.length) && guard.state->journal_line;
        t = {}; readable = read_flow_text(text_ref,t);
    }
    // P10-1 M1: any other flow may hold copies of marked misctext strings; strip them in place.
    if (guard.state->render && guard.state->texture_enabled && caller != 0x426648 && readable && t.text && t.length) {
        guard.state->strip_misc(t.text,t.length);
        t = {}; readable = read_flow_text(text_ref,t);
    }
    {   // P9-4: a book converted just before this call (0x42E560 -> strdup -> 0x5C7620).
        int book = -1;
        { Exclusive lock(guard.state->mutex); book = guard.state->pending_book; guard.state->pending_book = -1; }
        if (book >= 0 && readable && t.text && t.length && guard.state->bind_book(t.text,t.length,uint32_t(book)))
            leading = leading || guard.state->journal_line;
    }
    // P9-2: line positions are computed inside this initializer (0x5C6B10) from font record +8 (extra line
    // spacing). Raise it for every font record only while the journal is laid out, then restore it.
    if (leading) {
        table = word(0x1325A60); records = uint32_t(word(0x1325A64));
        if (!table || records > saved_leading.size()) leading = false;
        else for (uint32_t i = 0; i < records; ++i) {
            auto* field = reinterpret_cast<int32_t*>(table+i*12+8);
            saved_leading[i] = *field; *field += int32_t(guard.state->journal_line);
        }
    }
    const auto result = fn(self,widget,text_ref,a3,a4);
    if (leading) {
        for (uint32_t i = 0; i < records; ++i) *reinterpret_cast<int32_t*>(table+i*12+8) = saved_leading[i];
        Exclusive lock(guard.state->mutex); ++guard.state->journal_leading_applied;
    }
    auto& e = *guard.state; Exclusive lock(e.mutex);
    FlowProbe* slot = nullptr;
    for (auto& f : e.flows) if (f.flow == self && f.caller == caller) { slot = &f; break; }
    if (!slot) for (auto& f : e.flows) if (!f.flow) { slot = &f; *slot = {}; slot->flow = self; slot->caller = caller; break; }
    if (!slot) { ++e.flow_overflow; return result; }
    // P9-4 observe: identify which flow callers carry readable books. A new (caller, text) pair logs its
    // length, hash and first bytes (local log only); output is unchanged.
    if (readable && t.text && t.length && (slot->calls == 0 || slot->text_hash != t.hash)) {
        char head[49]{}; const auto n = std::min<uint32_t>(t.length,48);
        if (copy_guarded(t.text,head,n)) {
            std::string shown;
            for (uint32_t i = 0; i < n; ++i) {
                const auto c = uint8_t(head[i]);
                if (c >= 32 && c < 127 && c != '"' && c != '\\') shown += char(c);
                else { char hex[8]; std::snprintf(hex,sizeof hex,"\\\\x%02X",c); shown += hex; }
            }
            e.log->event("flow_text","\"caller\":"+std::to_string(caller)+",\"length\":"+std::to_string(t.length)+
                ",\"high\":"+std::to_string(t.high)+",\"fnv1a64\":"+std::to_string(t.hash)+",\"head\":\""+shown+"\"");
        }
    }
    slot->widget = widget; slot->text = readable ? t.text : 0;
    slot->text_length = t.length; slot->text_high = t.high; slot->text_hash = readable ? t.hash : 0;
    slot->buffers[0] = word(self+0x34); slot->buffers[1] = word(self+0x38); slot->buffers[2] = word(self+0x3C);
    ++slot->calls; slot->last_tick = GetTickCount64();
    return result;
}
uintptr_t __fastcall queue_hook(uintptr_t self, void*, uintptr_t raster, uintptr_t x, uintptr_t y,
                               uintptr_t flag, uintptr_t last) {
    Guard guard;
    const auto caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    auto fn = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t)>(queue_gateway);
    const uintptr_t result = fn(self,raster,x,y,flag,last);
    if (guard.state) { Exclusive lock(guard.state->mutex); guard.state->count_caller(guard.state->queue_callers,caller); }
    if (guard.state && caller == 0x5CFDBB) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        if (auto* r = e.raster(raster)) {
            const auto w = word(raster+0x14), h = word(raster+0x18), bits = word(raster+0x1C);
            const auto pixels = word(raster+0x43C), stride = word(raster+0x448);
            if (bits != 16 || !w || w > stride || stride > 2048 || !h || h > 256 || !pixels) e.fail(4);
            else {
                r->width = w; r->height = h; r->pixels = pixels; r->stride = stride; r->hash = raster_hash(*r);
                if (e.render) {
                    uint32_t expected_total = 0;
                    for (const auto& run : r->runs.values()) {
                        uint32_t expected = 0;
                        const auto& p = e.pack.plans[run.plan];
                        for (uint32_t i = 0; i < p.length; ++i) expected += p.wide[i] >= 128;
                        if (run.drawn != expected) e.fail(14);
                        expected_total += expected;
                    }
                    if (r->count != expected_total) e.fail(14);
                }
                r->runs.seal();
                ++e.stats[r->plan].raster;
                if (auto* v = e.trace(Life::RasterReady,r->plan,r->address,r->identity,r->generation,r->pixels)) {
                    v->raster_hash = r->hash; v->width = r->width; v->height = r->height; v->stride = r->stride;
                }
                for (uint32_t i = 0; i < r->runs.size(); ++i) {
                    const auto& run = r->runs.at(i);
                    if (r->runs.size() > 1) {
                        if (auto* v = e.trace(Life::RasterRunReady,run.plan,r->address,run.identity,r->generation,run.source))
                            v->glyph_count = run.drawn;
                        if (i && r->runs.first_plan(i)) ++e.stats[run.plan].shared_rasters;
                    }
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
    const auto old_owner = paint_owner, old_widget = paint_widget, old_caller = paint_caller;
    paint_owner = self; paint_widget = widget;
    paint_caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    if (guard.state) {
        Exclusive lock(guard.state->mutex); paint_generation = ++guard.state->generations;
        guard.state->count_caller(guard.state->paint_callers,paint_caller);
    }
    const auto result = reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t,uintptr_t)>(paint_gateway)(self,widget);
    paint_generation = previous;
    paint_owner = old_owner; paint_widget = old_widget; paint_caller = old_caller;
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
uintptr_t __cdecl name_copy_hook(const char* text) {
    Guard guard;
    const auto fn = reinterpret_cast<uintptr_t(__cdecl*)(const char*)>(name_copy_gateway);
    const auto caller = reinterpret_cast<uintptr_t>(_ReturnAddress());
    const int plan = guard.state ? guard.state->pack.match_name(text,caller) : -1;
    if (plan < 0) return fn(text);
    auto& e = *guard.state;
    const auto& p = e.pack.plans[size_t(plan)];
    // The game still allocates/owns/frees the strdup result. Register before
    // constructor0x41ACE0 measures its newly copied label, never after return.
    const auto copy = fn(reinterpret_cast<const char*>(p.slots.data()));
    Exclusive lock(e.mutex);
    if (!copy || std::memcmp(reinterpret_cast<void*>(copy),p.slots.data(),p.length+1) != 0 ||
        !e.bind_buffer(copy,p.length+1,uint32_t(plan),0,Life::Cache,reinterpret_cast<uintptr_t>(text))) e.fail(29);
    else { ++e.stats[size_t(plan)].name_copies; ++e.stats[size_t(plan)].cache; }
    return copy;
}
uintptr_t __fastcall name_destroy_hook(uintptr_t self, void*) {
    Guard guard;
    if (guard.state) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        const auto copy = word(self+0x6C);
        const auto located = e.registry.locate(copy);
        if (located.binding && located.offset == 0 && e.pack.plans[located.binding->plan].is_name()) {
            ++e.stats[located.binding->plan].freed; e.retire_buffer(copy);
        }
    }
    return reinterpret_cast<uintptr_t(__thiscall*)(uintptr_t)>(name_destroy_gateway)(self);
}
uintptr_t __fastcall flip_hook(uintptr_t self, void*) {
    Guard guard;
    if (guard.state) {
        auto& e = *guard.state; Exclusive lock(e.mutex);
        DWORD zero = 0; e.render_thread.compare_exchange_strong(zero,GetCurrentThreadId());
        if (e.render_thread.load() != GetCurrentThreadId()) e.fail(15);
        ++e.flips;
        if (e.render) e.compose(self);
        for (const auto& q : e.queues) if (q.address && q.last_frame == e.frame)
            if (const auto* r = e.raster(q.raster)) for (uint32_t i = 0; i < r->runs.size(); ++i)
                if (r->runs.first_plan(i)) ++e.stats[r->runs.at(i).plan].presentations;
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
                const auto advance = e.pack.plans[m.binding->plan].advances[m.offset];
                if (!logical_metric(spacing,advance)) e.fail(16);
                else {
                    metric_header[0] = logical_metric(spacing,advance);
                    f->eax = reinterpret_cast<uintptr_t>(metric_header.data())-font;
                    ++stats.width_overrides;
                }
            }
        } else {
            // P9-4: book pages measure through these points; widths of verified book slots follow the journal rule.
            uint32_t offset = 0, lead = 0; uint8_t previous = 0;
            const auto source = stage == 1 ? f->ebp : f->edi;
            const int plan = e.render && e.texture_enabled ? e.journal_locate(source,offset,&previous) : -1;
            if (plan >= 0 && e.pack.plans[size_t(plan)].wide[offset] >= 128) {
                const auto font = stage == 1 ? f->ecx : f->edx;
                const auto record = stage == 1 ? f->esi : f->ecx;
                const auto metric = logical_metric(word(record+4),e.journal_advance(previous,e.pack.plans[size_t(plan)].advances[offset],lead));
                if (!metric) e.fail(16);
                else { metric_header[0] = metric; f->eax = reinterpret_cast<uintptr_t>(metric_header.data())-font; ++e.book_width_overrides; }
            } else e.probe_flow_source(source, stage);
        }
    } else if (stage == 6 || stage == 7) {
        // P9-2: journal line breaking (0x5C6B10). Stage 6 = word measure 0x5C6378 (text ESI, font ECX,
        // record EDX); stage 7 = overlong-word character trim 0x5C6F5A (text EBX, font EDX, record ECX).
        uint32_t offset = 0, lead = 0; uint8_t previous = 0;
        const auto source = stage == 6 ? f->esi : f->ebx;
        const int plan = e.render && e.texture_enabled ? e.journal_locate(source,offset,&previous) : -1;
        if (plan >= 0 && e.pack.plans[size_t(plan)].wide[offset] >= 128) {
            const auto font = stage == 6 ? f->ecx : f->edx;
            const auto record = stage == 6 ? f->edx : f->ecx;
            const auto metric = logical_metric(word(record+4),e.journal_advance(previous,e.pack.plans[size_t(plan)].advances[offset],lead));
            if (!metric) e.fail(16);
            else {
                metric_header[0] = metric;
                f->eax = reinterpret_cast<uintptr_t>(metric_header.data())-font;
                ++e.journal_width_overrides;
            }
        }
    } else if (stage == 3) {
        const auto* s = reinterpret_cast<const uint32_t*>(f->esp+4);
        e.count_caller(e.glyph_callers,s[0]);
        if ((s[3]&255) == MiscMarkerLead) ++e.misc_leaks; // a marked misctext string drawn outside a stripped flow
        uint32_t journal_offset = 0, journal_lead = 0; uint8_t journal_previous = 0;
        const int journal_plan = e.render && e.texture_enabled && s[0] == 0x5C5D09 ? e.journal_locate(s[9],journal_offset,&journal_previous) : -1;
        if (journal_plan >= 0) {
            // P8-3: a journal span drawn into a page raster. Chinese is written into the raster itself.
            const auto& p = e.pack.plans[size_t(journal_plan)];
            if (p.wide[journal_offset] < 128) return 0; // ASCII inside the entry stays native
            ++e.texture_glyphs;
            const auto metric = logical_metric(word(f->ecx+4),e.journal_advance(journal_previous,p.advances[journal_offset],journal_lead));
            const auto* g = e.glyphs.get(p.wide[journal_offset],TextureEm);
            const auto raster = word(0x133393C);
            const InkProbe* ink = (s[3]&255) == 0x7F && metric && g ? e.ink_for(f->ecx,raster) : nullptr;
            if ((s[3]&255) != 0x7F) ++e.texture_rejects[0];
            else if (!metric) ++e.texture_rejects[1];
            else if (!g) ++e.texture_rejects[2];
            else if (!ink) ++e.texture_rejects[3];
            if (!ink) return 0; // visible native fallback, never a forced quit
            const auto drawn = texture_glyph(raster,*ink,g->alpha.data(),g->width,g->height,
                int32_t(s[1])+int32_t(journal_lead)+g->bearing_x,int32_t(s[2])-g->bearing_y);
            if (drawn == UINT32_MAX) ++e.texture_faults; else e.texture_pixels += drawn;
            metric_header[0] = metric;
            f->eax = reinterpret_cast<uintptr_t>(metric_header.data());
            return f->eax;
        }
        auto m = s[0] == 0x5C5D09 ? e.locate(s[9]) : Located{};
        if (!m.binding && s[0] == 0x5C5D09) e.probe_flow_source(s[9],3);
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
            auto* run = r ? r->runs.acquire({paint_generation,paint_owner,paint_widget,paint_caller},
                                           plan,m.binding->identity,m.binding->base) : nullptr;
            if (!r || !run) {
                // Bounded CPU-only evidence; snapshot logs it outside the paint/Lock path.
                if (e.raster_fault_count < e.raster_faults.size()) {
                    auto& v = e.raster_faults[e.raster_fault_count++];
                    v.tick = GetTickCount64(); v.frame = e.frame; v.paint = paint_generation;
                    v.identity = m.binding->identity; v.source = m.binding->base;
                    v.raster = address; v.paint_owner = paint_owner; v.widget = paint_widget;
                    v.paint_caller = paint_caller; v.plan = plan; v.offset = m.offset;
                    if (address) { v.native_width = word(address+0x14); v.native_height = word(address+0x18); }
                    v.bound = r != nullptr;
                    if (r) {
                        v.prior_plan = r->plan; v.prior_count = r->count;
                        v.prior_identity = r->identity; v.prior_generation = r->generation;
                        v.prior_paint = r->paint_generation;
                    }
                }
                e.fail(10);
            }
            else if (e.render && e.pack.plans[plan].wide[m.offset] >= 128) {
                const auto spacing = word(f->ecx+4);
                const auto advance = e.pack.plans[plan].advances[m.offset];
                if ((s[3]&255) != 0x7F || !logical_metric(spacing,advance) || r->count >= r->placements.size()) e.fail(17);
                else {
                    // The font in use, not the raster, decides color: labels sharing a raster stay independent.
                    r->placements[r->count++] = {m.offset,int32_t(s[1]),int32_t(s[2]),r->runs.index(run),e.font_style(f->ecx).rgb};
                    ++run->drawn;
                    ++e.stats[plan].unicode_draws;
                    metric_header[0] = logical_metric(spacing,advance);
                    f->eax = reinterpret_cast<uintptr_t>(metric_header.data());
                    return f->eax;
                }
            }
        }
    } else if (stage == 4) {
        const auto caller = word(f->esp+4);
        if (caller == 0x50913D || caller == 0x50915E || caller == 0x50917B || caller == 0x509193) {
            auto* q = e.queue(f->ebx);
            if (!q && e.render && !e.errors.load() && e.draw_list.count && word(f->ecx) == 0x74FBB8) {
                // Painter's order: native UI drawn over pending Chinese must land above it (cursor, panels).
                const auto* a = reinterpret_cast<const uint32_t*>(f->esp+8);
                float left = 1e9f, top = 1e9f, right = -1e9f, bottom = -1e9f;
                bool valid = true;
                for (uint32_t i = 0; i < 3; ++i) {
                    const float vx = *reinterpret_cast<const float*>(a[i]), vy = *reinterpret_cast<const float*>(a[i]+8);
                    if (!std::isfinite(vx) || !std::isfinite(vy)) { valid = false; break; }
                    left = std::min(left,vx); right = std::max(right,vx);
                    top = std::min(top,vy); bottom = std::max(bottom,vy);
                }
                if (valid && std::abs(left) < 10000 && std::abs(right) < 10000 && std::abs(top) < 10000 && std::abs(bottom) < 10000) {
                    const Rect area{int32_t(std::floor(left)),int32_t(std::floor(top)),int32_t(std::ceil(right)),int32_t(std::ceil(bottom))};
                    if (e.draw_list.overlaps(area))
                        e.add_occluder(f->ebx,area,caller,*reinterpret_cast<const float*>(f->ebp+0x18),*reinterpret_cast<const float*>(f->ebp+0x1C));
                }
            }
            if (q && q->last_frame != e.frame) {
                const auto* r = e.raster(q->raster);
                if (!r || r->generation != q->raster_generation || word(q->address+8) != r->address ||
                    word(f->ecx) != 0x74FBB8 || raster_hash(*r) != r->hash) e.fail(11);
                else {
                    q->last_frame = e.frame;
                    for (uint32_t i = 0; i < r->runs.size(); ++i) if (r->runs.first_plan(i))
                        ++e.stats[r->runs.at(i).plan].submissions;
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
                            // P9-3: native label rasters are sized for the English font. CJK descends further below
                            // the baseline, so the bottom edge may extend by up to a quarter em (never sideways/up).
                            const auto clip = intersect({round(x*sx),round(y*sy),round((x+r->width)*sx),
                                round((y+r->height)*sy)+int32_t(em/4)},{0,0,int32_t(width),int32_t(height)});
                            for (uint32_t i = 0; i < r->count; ++i) {
                                const auto& p = r->placements[i]; const auto plan = r->runs.at(p.run).plan;
                                const auto scalar = e.pack.plans[plan].wide[p.offset];
                                const auto* g = e.glyphs.get(scalar,em);
                                if (!g) { ++e.stats[plan].cache_misses; e.fail(20); break; }
                                ++e.stats[plan].cache_hits;
                                const int32_t left = round((x+p.x)*sx)+g->bearing_x;
                                const int32_t top = round((y+p.y)*sy)-g->bearing_y;
                                const auto bounds = intersect(clip,{left,top,left+int32_t(g->width),top+int32_t(g->height)});
                                if (!empty(bounds) && !list.add({g,left,top,bounds,p.rgb})) e.fail(21);
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
__declspec(naked) void journal_word_hook() {
    __asm mov eax, dword ptr [ecx+eax*8-0xF0]
    SAVE_FRAME CALL_STAGE(6) RESTORE_FRAME __asm jmp dword ptr [journal_word_after]
}
__declspec(naked) void journal_trim_hook() {
    __asm mov eax, dword ptr [edx+eax*8-0xF0]
    SAVE_FRAME CALL_STAGE(7) RESTORE_FRAME __asm jmp dword ptr [journal_trim_after]
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
const InkProbe* Engine::ink_for(uintptr_t record, uintptr_t raster) noexcept {
    const auto blob = record ? word(record) : 0;
    if (!blob || !raster) return nullptr;
    const auto type = uint32_t(word(raster+0x20));
    for (uint32_t i = 0; i < ink_count; ++i)
        if (inks[i].blob == blob && inks[i].type == type) return inks[i].usable ? &inks[i] : nullptr;
    if (ink_count == inks.size()) return nullptr;
    auto& ink = inks[ink_count++];
    ink = {}; ink.blob = blob; ink.type = type;
    if (!probe_ink(raster,ink,{probe_a.data(),probe_b.data(),sample_aux.data(),SampleSize})) { ink.usable = false; ++texture_faults; }
    return ink.usable ? &ink : nullptr;
}
int Engine::plan_for_entry(uint32_t entry) const noexcept {
    for (uint32_t i = 0; i < pack.count; ++i) if (pack.plans[i].entry == entry && !pack.plans[i].is_name()) return int(i);
    return -1;
}
// P9-2: Chinese in the journal gets player letter spacing (centred in the cell) and, after a visible ASCII
// glyph, a small lead so the game's italic overhang (for example a closing parenthesis) stays clear of it.
inline constexpr uint32_t JournalAsciiGap = 3;
uint32_t Engine::journal_advance(uint8_t previous, uint32_t base, uint32_t& lead) const noexcept {
    const uint32_t gap = previous > 0x20 && previous < 0x7F ? JournalAsciiGap : 0;
    lead = journal_letter/2 + gap;
    return base + journal_letter + gap;
}
int Engine::journal_locate(uintptr_t source, uint32_t& offset, uint8_t* previous) noexcept {
    for (auto& b : journal_buffers) {
        if (!b.base || source < b.base || source >= b.base+b.size) continue;
        const auto at = uint32_t(source-b.base);
        auto it = std::upper_bound(b.segments.begin(),b.segments.end(),at,
            [](uint32_t v, const JournalSegment& g) { return v < g.offset; });
        if (it == b.segments.begin()) return -1;
        const auto& g = *--it;
        if (at >= g.offset+g.length) return -1;
        const auto& p = pack.plans[g.plan];
        offset = g.plan_offset+(at-g.offset);
        if (*reinterpret_cast<const uint8_t*>(source) != p.slots[offset]) { ++journal_stale; b = {}; return -1; }
        if (previous) *previous = at ? *reinterpret_cast<const uint8_t*>(source-1) : 0;
        return int(g.plan);
    }
    return -1;
}
// J2 display side: replaces each `U9J<entry>` line ending with the plan's slot string, in a new buffer from
// the game allocator; the old copy is freed with the game's free. Called without the engine lock held.
// P9-4: maps the k-th 0x7F slot of a converted book's flow text to the k-th non-ASCII scalar of its plan.
// The game's markup pass only compacts bytes, so order is preserved; a count mismatch binds nothing.
bool Engine::bind_book(uintptr_t text, uint32_t length, uint32_t plan) noexcept {
    try {
        const auto& p = pack.plans[plan];
        std::vector<JournalSegment> segments; segments.reserve(p.length);
        std::vector<uint32_t> wides;
        for (uint32_t i = 0; i < p.length; ++i) if (p.wide[i] >= 128) wides.push_back(i);
        std::vector<char> copy(length);
        if (!copy_guarded(text,copy.data(),length)) return false;
        for (uint32_t i = 0, k = 0; i < length; ++i) if (uint8_t(copy[i]) == 0x7F) {
            if (k >= wides.size()) { Exclusive lock(mutex); ++book_mismatch; return false; }
            segments.push_back({i,plan,wides[k++],1});
        }
        if (segments.size() != wides.size()) { Exclusive lock(mutex); ++book_mismatch; return false; }
        Exclusive lock(mutex);
        auto& b = journal_buffers[journal_next++ % journal_buffers.size()];
        b = {}; b.base = text; b.size = length+1; b.entries = 1; b.segments = std::move(segments);
        ++book_bound;
        return true;
    } catch (...) { Exclusive lock(mutex); ++journal_alloc_failures; return false; }
}
bool Engine::expand_journal(uintptr_t text_ref, uintptr_t text, uint32_t length) noexcept {
    try {
        const auto* s = reinterpret_cast<const char*>(text);
        std::string out; out.reserve(size_t(length)+512);
        std::vector<JournalSegment> segments; uint32_t count = 0, unknown = 0, dropped = 0, kept = 0;
        for (uint32_t i = 0; i < length;) {
            if ((i == 0 || s[i-1] == ' ' || s[i-1] == '\n') && i+3 < length && s[i] == 'U' && s[i+1] == '9' && s[i+2] == 'J') {
                uint32_t j = i+3, id = 0, digits = 0;
                while (j < length && s[j] >= '0' && s[j] <= '9' && digits < 6) { id = id*10+uint32_t(s[j]-'0'); ++j; ++digits; }
                if (digits && digits <= 5 && (j == length || s[j] == '\n' || s[j] == '\r')) {
                    const int plan = plan_for_entry(id);
                    if (plan >= 0) {
                        const auto& p = pack.plans[size_t(plan)];
                        for (uint32_t k = 0; k < p.length;) {
                            if (p.slots[k] == 0x0A) {
                                // A break between two ASCII words stood for a space (for example inside a mantra).
                                const uint8_t before = k ? p.slots[k-1] : 0, after = k+1 < p.length ? p.slots[k+1] : 0;
                                if (before > 0x20 && before < 0x7F && after > 0x20 && after < 0x7F) { out += ' '; ++kept; }
                                ++dropped; ++k; continue;
                            }
                            uint32_t end = k; while (end < p.length && p.slots[end] != 0x0A) ++end;
                            segments.push_back({uint32_t(out.size()),uint32_t(plan),k,end-k});
                            out.append(reinterpret_cast<const char*>(p.slots.data())+k,end-k);
                            k = end;
                        }
                        ++count; i = j; continue;
                    }
                    ++unknown;
                }
            }
            out += s[i++];
        }
        if (!count) { if (unknown) { Exclusive lock(mutex); journal_unknown_markers += unknown; } return false; }
        auto* copy = reinterpret_cast<char*(__cdecl*)(size_t)>(0x7108F0)(out.size()+1);
        if (!copy) { Exclusive lock(mutex); ++journal_alloc_failures; return false; }
        std::memcpy(copy,out.data(),out.size()); copy[out.size()] = 0;
        *reinterpret_cast<uintptr_t*>(text_ref) = reinterpret_cast<uintptr_t>(copy);
        reinterpret_cast<void(__cdecl*)(uintptr_t)>(0x7108E0)(text);
        Exclusive lock(mutex);
        auto& b = journal_buffers[journal_next++ % journal_buffers.size()];
        b = {}; b.base = reinterpret_cast<uintptr_t>(copy); b.size = uint32_t(out.size()+1); b.entries = count;
        b.segments = std::move(segments);
        ++journal_expansions; journal_spans += count; journal_unknown_markers += unknown; journal_breaks_dropped += dropped; journal_spaces_kept += kept;
        return true;
    } catch (...) { Exclusive lock(mutex); ++journal_alloc_failures; }
    return false;
}
// P10-1 M1: replace the constructed misctext cache obj+0 with `marker + slots` from the game allocator.
// Called without the engine lock: the native free below re-enters free_hook.
bool Engine::mark_misc(uintptr_t object, uint32_t plan) noexcept {
    const auto& p = pack.plans[plan];
    const auto cache = word(object), wide = word(object+8);
    char marker[MiscMarkerSize];
    if (p.is_name() || p.is_book() || !cache || !wide || !encode_misc_marker(plan,marker) ||
        std::memcmp(reinterpret_cast<void*>(wide),p.wide.data(),(size_t(p.length)+1)*2) != 0 ||
        std::memcmp(reinterpret_cast<void*>(cache),p.slots.data(),size_t(p.length)+1) != 0) {
        Exclusive lock(mutex); ++misc_mark_failures; return false;
    }
    auto* copy = reinterpret_cast<char*(__cdecl*)(size_t)>(0x7108F0)(size_t(MiscMarkerSize)+p.length+1);
    if (!copy) { Exclusive lock(mutex); ++misc_mark_failures; return false; }
    std::memcpy(copy,marker,MiscMarkerSize);
    std::memcpy(copy+MiscMarkerSize,p.slots.data(),size_t(p.length)+1);
    *reinterpret_cast<uintptr_t*>(object) = reinterpret_cast<uintptr_t>(copy);
    reinterpret_cast<void(__cdecl*)(uintptr_t)>(0x7108E0)(cache);
    return true;
}
// P10-1 M1: strips markers from a flow text in place (the buffer only shrinks) and records the plan segments
// for the journal/book width and texture glyph path. Called without the engine lock.
void Engine::strip_misc(uintptr_t text, uint32_t length) noexcept {
    try {
        std::vector<uint8_t> copy(size_t(length)+1);
        if (!copy_guarded(text,reinterpret_cast<char*>(copy.data()),length+1)) return;
        if (std::find(copy.begin(),copy.begin()+length,MiscMarkerLead) == copy.begin()+length) return;
        const auto r = strip_misc_markers(copy.data(),length,[&](uint32_t plan, uint32_t& n) -> const uint8_t* {
            if (plan >= pack.count) return nullptr;
            const auto& p = pack.plans[plan];
            if (p.is_name() || p.is_book()) return nullptr;
            n = p.length; return p.slots.data();
        });
        if (r.markers && !write_guarded(text,copy.data(),r.length+1)) { Exclusive lock(mutex); ++misc_mark_failures; return; }
        Exclusive lock(mutex);
        misc_stripped += r.markers; misc_invalid += r.invalid; misc_partial += r.partial;
        if (r.segments.empty()) return;
        for (auto& b : journal_buffers) if (b.base == text) b = {};
        auto& b = journal_buffers[journal_next++ % journal_buffers.size()];
        b = {}; b.base = text; b.size = r.length+1; b.entries = r.markers;
        b.segments.reserve(r.segments.size());
        for (const auto& g : r.segments) b.segments.push_back({g.offset,g.plan,0,g.length});
        ++misc_buffers;
    } catch (...) { Exclusive lock(mutex); ++journal_alloc_failures; }
}
void Engine::count_caller(std::array<CallerCount,32>& table, uintptr_t caller) noexcept {
    for (auto& c : table) {
        if (c.caller == caller) { ++c.count; return; }
        if (!c.caller) { c.caller = caller; c.count = 1; return; }
    }
    ++caller_overflow;
}
// Attributes a non-allowlisted layout/bounds/glyph source byte to a recorded text flow buffer.
void Engine::probe_flow_source(uintptr_t source, uint32_t stage) noexcept {
    if (!source) return;
    static constexpr uintptr_t sizes[3] = {0x1000, 0x10000, 0x8000};
    for (auto& f : flows) {
        if (!f.flow) continue;
        int range = -1;
        if (f.text && source >= f.text && source <= f.text+f.text_length) range = 0;
        else for (int i = 0; i < 3; ++i) if (f.buffers[i] && source >= f.buffers[i] && source < f.buffers[i]+sizes[i]) { range = i+1; break; }
        if (range < 0) continue;
        if (stage == 1) ++f.layout[range];
        else if (stage == 2) ++f.bounds[range];
        else {
            ++f.glyph[range];
            if (!paint_generation) ++f.glyph_outside_paint;
            f.glyph_paint_caller = paint_caller; f.glyph_paint_owner = paint_owner; f.glyph_paint_widget = paint_widget;
            const auto raster = word(0x133393C);
            f.glyph_raster = raster;
            if (raster) { f.glyph_raster_width = uint32_t(word(raster+0x14)); f.glyph_raster_height = uint32_t(word(raster+0x18)); }
        }
        return;
    }
}
void Engine::retire(uintptr_t address) noexcept {
    for (auto& b : journal_buffers) if (address && b.base == address) b = {};
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
        ++skipped_frames; ++skip_reasons[0]; surface.invalidate(); return;
    }
    if (word(backend) != 0x74FBB8 ||
        word(backend+0x44) != list.width || word(backend+0x48) != list.height ||
        word(backend+0x4C) != 32 || *reinterpret_cast<const uint8_t*>(backend+0x3FC508)) {
        ++skipped_frames; fail(22); return;
    }
    if (*reinterpret_cast<const uint8_t*>(backend+0x3FC509)) { ++skipped_frames; ++skip_reasons[1]; surface.invalidate(); return; }
    const auto back = word(backend+0x3FC3C4);
    if (back != list.backbuffer) { ++skipped_frames; ++skip_reasons[2]; surface.invalidate(); return; }
    if (!back || word(back) != 0x18153838) { ++skipped_frames; fail(23); return; }
    const auto root = word(back+8), inner = root ? root+0xC : 0;
    if (!inner || word(inner) != 0x18152DF4) { ++skipped_frames; fail(24); return; }
    for (uint32_t i = 0; i < list.records; ++i) {
        const auto& source = list.sources[i]; const auto* q = queue(source.node); const auto* r = raster(source.raster);
        if (!q || !r || q->generation != source.queue_generation || r->generation != source.raster_generation ||
            q->last_frame != frame || q->raster_generation != r->generation || raster_hash(*r) != r->hash) {
            ++skipped_frames; ++skip_reasons[3]; return; // A verified native repaint/free made the command stale.
        }
    }
    Rect locked = list.commands[0].clip;
    for (uint32_t i = 1; i < list.count; ++i) {
        const auto r = list.commands[i].clip;
        locked = {std::min(locked.left,r.left),std::min(locked.top,r.top),
            std::max(locked.right,r.right),std::max(locked.bottom,r.bottom)};
    }
    locked = intersect(locked,{0,0,int32_t(list.width),int32_t(list.height)});
    if (empty(locked)) { ++skipped_frames; ++skip_reasons[4]; return; }
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
        for (uint32_t i = 0; i < list.records; ++i) if (const auto* r = raster(list.sources[i].raster))
            for (uint32_t j = 0; j < r->runs.size(); ++j) if (r->runs.first_plan(j))
                ++stats[r->runs.at(j).plan].composites;
    }
    if (error) fail(error); // Controlled quit only AFTER Unlock and log-gate release.
}
// Text stays composed at flip: in session-defects-2 text painted by a mid-frame Lock vanished once
// later native draws ran. So an occluder is read, never drawn out of order. A node's raster is
// not tracked by us and may be stale, hence the fault guard and field checks.
namespace {
struct OccluderProbe {
    std::array<uint32_t,5> fields{}; // tiles, width, height, bits, stride
    uint32_t type = 0, opaque = 0, rule = 0, corner = 0, alpha1555 = 0, alpha4444 = 0;
    bool usable = false;
};
// The first rule leaving between 1/256 and 3/5 of the texels opaque wins; a cursor is mostly clear.
bool read_occluder(uintptr_t raster, OccluderMask& mask, OccluderProbe& p) noexcept {
    __try {
        p.fields[1] = word(raster+0x14); p.fields[2] = word(raster+0x18); p.fields[3] = word(raster+0x1C); p.fields[4] = word(raster+0x448);
        p.type = word(raster+0x20);
        const auto pixels = reinterpret_cast<const uint16_t*>(word(raster+0x43C));
        const auto w = p.fields[1], h = p.fields[2], stride = p.fields[4];
        p.usable = p.fields[3] == 16 && w && w <= MaskMaxSide && h && h <= MaskMaxSide && w <= stride && stride <= 2048 && pixels;
        if (!p.usable) return true;
        const auto corner = pixels[size_t(h-1)*stride+w-1];
        p.corner = corner;
        for (uint32_t y = 0; y < h; ++y) for (uint32_t x = 0; x < w; ++x) {
            const auto t = pixels[size_t(y)*stride+x];
            p.alpha1555 += (t&0x8000) != 0; p.alpha4444 += (t>>12) >= 8;
        }
        for (const auto rule : {MaskRule::Key,MaskRule::Alpha1555,MaskRule::Alpha4444,MaskRule::Corner}) {
            p.opaque = build_mask(mask,pixels,stride,w,h,rule,corner);
            p.rule = uint32_t(rule);
            if (uint64_t(p.opaque)*256 >= uint64_t(w)*h && uint64_t(p.opaque)*5 <= uint64_t(w)*h*3) break;
        }
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
}
void Engine::add_occluder(uintptr_t node, Rect area, uint32_t caller, float sx, float sy) noexcept {
    auto& list = draw_list;
    for (uint32_t i = 0; i < list.mask_count; ++i) if (list.masks[i].node == node) return;
    last_occluder = area; last_occluder_caller = caller;
    if (list.mask_count == list.masks.size()) { ++occluder_rejects[0]; return; }
    last_occluder_raster = {}; last_occluder_opaque = last_occluder_rule = last_occluder_corner = 0;
    last_occluder_type = last_occluder_alpha1555 = last_occluder_alpha4444 = 0;
    const auto tiles = word(node+0x10);
    last_occluder_raster[0] = tiles;
    if (tiles != 1) { ++occluder_rejects[1]; return; }
    auto& mask = list.masks[list.mask_count];
    OccluderProbe probe;
    const bool read = read_occluder(word(node+8),mask,probe);
    last_occluder_raster = probe.fields; last_occluder_raster[0] = tiles;
    last_occluder_type = probe.type; last_occluder_rule = probe.rule; last_occluder_corner = probe.corner;
    last_occluder_alpha1555 = probe.alpha1555; last_occluder_alpha4444 = probe.alpha4444;
    if (!read) { ++occluder_rejects[4]; return; }
    if (!probe.usable) { ++occluder_rejects[2]; return; }
    const auto opaque = probe.opaque;
    last_occluder_opaque = opaque;
    const auto w = mask.width, h = mask.height;
    if (std::abs(float(area.right-area.left)-float(w)*sx) > 2*sx || std::abs(float(area.bottom-area.top)-float(h)*sy) > 2*sy) { ++occluder_rejects[3]; return; }
    if (uint64_t(opaque)*5 > uint64_t(w)*h*3) { ++occluder_rejects[5]; return; } // A panel, not a cursor.
    mask.node = node; mask.area = area; mask.covers = list.count;
    ++list.mask_count; ++occluder_masks;
}
const FontStyle& Engine::font_style(uintptr_t record) noexcept {
    static const FontStyle fallback{};
    const auto blob = word(record);
    if (!blob) return fallback;
    for (uint32_t i = 0; i < font_count; ++i) if (fonts[i].blob == blob) { ++fonts[i].uses; return fonts[i]; }
    if (font_count == fonts.size()) { ++font_overflow; return fallback; }
    auto& style = fonts[font_count++];
    style.blob = blob; style.uses = 1;
    const auto live = word(0x133393C);
    // Run the native glyph blit on a private copy of the live raster descriptor.
    if (live && word(live+0x1C) == 16) {
        std::array<uint8_t,0x44C> fake;
        std::memcpy(fake.data(),reinterpret_cast<const void*>(live),fake.size());
        const auto set = [&](size_t at, uintptr_t value) { std::memcpy(fake.data()+at,&value,4); };
        const auto address = reinterpret_cast<uintptr_t>(fake.data());
        set(4,0); set(8,0); set(0xC,SampleSize-1); set(0x10,SampleSize-1);
        set(0x14,SampleSize); set(0x18,SampleSize);
        set(0x43C,reinterpret_cast<uintptr_t>(sample.data())); set(0x448,SampleSize);
        if (word(live+0x444)) set(0x444,reinterpret_cast<uintptr_t>(sample_aux.data()));
        using Blit = uintptr_t(__thiscall*)(uintptr_t,uintptr_t,int32_t,int32_t);
        for (const uint32_t c : {'E','H','A','M','O'}) {
            const auto offset = word(blob+c*8-0xF0);
            if (!offset) continue;
            const auto glyph = blob+offset;
            if (!word(glyph+4) || word(glyph+4) > SampleSize || !word(glyph+8) || word(glyph+8) > SampleSize) continue;
            sample.fill(SampleTransparent); sample_aux.fill(0);
            reinterpret_cast<Blit>(0x5E20E0)(address,glyph,int32_t(word(glyph+0xC)),int32_t(word(glyph+0x10)));
            if (dominant_color(sample,style.rgb)) { style.sampled = true; style.reference = c; break; }
        }
    }
    return style;
}
void Engine::install(const Config& config, Logger& logger) {
    log = &logger; render = config.mode == Mode::Render;
    require(config.journal_letter_spacing <= MaxJournalLetterSpacing && config.journal_line_spacing <= MaxJournalLineSpacing,
            "journal spacing outside supported range");
    journal_letter = config.journal_letter_spacing; journal_line = config.journal_line_spacing;
    log->event("journal_settings","\"letter_spacing\":"+std::to_string(journal_letter)+",\"line_spacing\":"+std::to_string(journal_line));
    const auto load_started = GetTickCount64();
    pack.load(config_path(config.allowlist_path), render);
    require(sha256(config_path(config.game_dir)/L"static"/L"text.flx") == pack.resource_hash,
            "allowlist resource hash mismatch");
    if (pack.has_names) require(sha256(config_path(config.game_dir)/L"static"/L"TYPENAME.FLX") == pack.typename_hash,
                                "allowlist typename hash mismatch");
    if (pack.has_books) require(sha256(config_path(config.game_dir)/L"static"/L"BOOKS-EN.FLX") == pack.books_hash,
                                "allowlist books hash mismatch");
    log->event("runtime_corpus", "\"mode\":\""+std::string(render?"render":"observe")+
        "\",\"resource_sha256\":\""+utf8(pack.resource_hash)+"\",\"entries\":"+std::to_string(pack.count));
    if (render) {
        glyphs.open(config_path(config.font_path));
        log->event("runtime_font","\"family\":\""+utf8(glyphs.font_family())+"\",\"sha256\":\""+utf8(glyphs.font_sha256())+
            "\",\"file\":\""+utf8(config_path(config.font_path).filename().wstring())+"\"");
        // v1 historical packs carry no explicit glyph list. v2 lists are exact
        // and validated by Pack::load. In either case prewarm before hooks/READY.
        if (!pack.glyph_count) {
            for (uint32_t i = 0; i < pack.count; ++i) for (uint32_t j = 0; j < pack.plans[i].length; ++j) {
                const uint32_t s = pack.plans[i].wide[j];
                if (s >= 128 && std::find(pack.scalars.begin(),pack.scalars.begin()+pack.glyph_count,s) ==
                    pack.scalars.begin()+pack.glyph_count) {
                    require(pack.glyph_count < MaxGlyphScalars,"glyph scalar capacity");
                    pack.scalars[pack.glyph_count++] = s;
                }
            }
        }
        require(pack.glyph_count*2 <= GlyphCacheCapacity,"prewarm capacity exceeded");
        for (uint32_t i = 0; i < pack.glyph_count; ++i) for (auto em : {20U,40U}) glyphs.warm(pack.scalars[i],em);
        for (uint32_t i = 0; i < pack.count; ++i) for (uint32_t j = 0; j < pack.plans[i].length; ++j) {
            const uint32_t s = pack.plans[i].wide[j];
            if (s < 128) continue;
            const auto* a = glyphs.get(s,20); const auto* b = glyphs.get(s,40);
            require(a && b && a->advance*16/20 == b->advance*16/40,"inconsistent engine advances");
            // P9-1: text was wrapped offline with every CJK glyph one 16-unit cell wide. A font that disagrees
            // would silently break line layout, so it is refused before READY (the game is not resumed).
            require(b->advance*16/40 == int32_t(LayoutCellUnits),"font glyph advance differs from the 16-unit layout cell");
            pack.plans[i].advances[j] = uint16_t(b->advance*16/40);
        }
        // P8-3: page textures need a third size. Disabled, never fatal, when capacity or metrics disagree.
        texture_enabled = pack.glyph_count*3 <= GlyphCacheCapacity;
        if (texture_enabled) for (uint32_t i = 0; i < pack.glyph_count; ++i) {
            glyphs.warm(pack.scalars[i],TextureEm);
            const auto* t = glyphs.get(pack.scalars[i],TextureEm); const auto* b = glyphs.get(pack.scalars[i],40);
            if (!t || !b || t->advance*16/int32_t(TextureEm) != b->advance*16/40) texture_enabled = false;
        }
        log->event("texture_glyphs","\"enabled\":"+std::string(texture_enabled?"true":"false")+",\"em\":"+std::to_string(TextureEm));
        for (uint32_t i = 0; i < pack.glyph_count; ++i) for (auto em : {20U,40U,TextureEm}) if (const auto* g = glyphs.get(pack.scalars[i],em))
        { const auto scalar = pack.scalars[i];
            log->event("glyph_cache_warm", "\"scalar\":"+std::to_string(scalar)+",\"em\":"+std::to_string(em)+
                ",\"index\":"+std::to_string(g->index)+",\"width\":"+std::to_string(g->width)+
                ",\"height\":"+std::to_string(g->height)+",\"advance\":"+std::to_string(g->advance)+
                ",\"coverage_sha256\":\""+utf8(sha256_bytes(g->alpha.data(),g->alpha.size()))+"\"");
        }
    }
    log->event("runtime_capacity", "\"plans\":"+std::to_string(pack.count)+",\"glyphs\":"+std::to_string(pack.glyph_count)+
        ",\"rasters\":"+std::to_string(glyphs.size())+",\"alpha_bytes\":"+std::to_string(glyphs.alpha_bytes())+
        ",\"load_prewarm_ms\":"+std::to_string(GetTickCount64()-load_started));
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
    prepare("journal_word_width",0x5C6378,journal_word_hook,{0x8B,0x84,0xC1,0x10,0xFF,0xFF,0xFF},{7});
    prepare("journal_trim_width",0x5C6F5A,journal_trim_hook,{0x8B,0x84,0xC2,0x10,0xFF,0xFF,0xFF},{7});
    glyph_gateway = prepare("glyph",0x5C5A80,glyph_hook,{0x8B,0x54,0x24,0x0C,0x80,0xFA,0x20},{4,3});
    paint_gateway = prepare("paint_cache",0x5CFCE0,paint_hook,{0x64,0xA1,0,0,0,0},{6});
    prepare("raster_repaint",0x5CFD50,raster_begin_hook,{0x89,0x1D,0x3C,0x39,0x33,1},{6});
    queue_gateway = prepare("raster_queue",0x508D50,queue_hook,{0x8A,0x44,0x24,0x10,0x53},{4,1});
    destroy_gateway = prepare("queue_destroy",0x5083F0,destroy_hook,{0x6A,0xFF,0x68,0xA8,0xE3,0x72,0},{2,5});
    free_gateway = prepare("engine_free",0x7108E0,free_hook,{0x8B,0x44,0x24,4,0x50},{4,1});
    if (pack.has_names) {
        name_copy_gateway = prepare("name_copy",0x714CD0,name_copy_hook,{0x53,0x56,0x8B,0x74,0x24,0x0C},{1,1,4});
        name_destroy_gateway = prepare("name_destroy",0x41AE40,name_destroy_hook,{0x56,0x8B,0xF1,0x8B,0x46,0x6C},{1,2,3});
    }
    flow_gateway = prepare("text_flow_init",0x5C7620,flow_hook,{0x8B,0x44,0x24,0x08,0x53},{4,1});
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
        // A failed pack load rolls back through here with no plans loaded.
        const auto entry_of = [&](uint32_t plan) { return plan < pack.plans.size() ? pack.plans[plan].entry : 0U; };
        const EntryStats untouched{};
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
            ",\"occluder_masks\":"+std::to_string(occluder_masks)+",\"occluder_rejects\":["+std::to_string(occluder_rejects[0])+","+std::to_string(occluder_rejects[1])+","+
            std::to_string(occluder_rejects[2])+","+std::to_string(occluder_rejects[3])+","+std::to_string(occluder_rejects[4])+","+std::to_string(occluder_rejects[5])+
            "],\"skip_reasons\":["+std::to_string(skip_reasons[0])+","+std::to_string(skip_reasons[1])+","+std::to_string(skip_reasons[2])+","+std::to_string(skip_reasons[3])+","+std::to_string(skip_reasons[4])+
            "],\"last_occluder_opaque\":"+std::to_string(last_occluder_opaque)+",\"last_occluder_rule\":"+std::to_string(last_occluder_rule)+
            ",\"last_occluder_corner\":"+std::to_string(last_occluder_corner)+",\"last_occluder_type\":"+std::to_string(last_occluder_type)+
            ",\"last_occluder_alpha1555\":"+std::to_string(last_occluder_alpha1555)+",\"last_occluder_alpha4444\":"+std::to_string(last_occluder_alpha4444)+",\"last_occluder_raster\":["+std::to_string(last_occluder_raster[0])+","+std::to_string(last_occluder_raster[1])+","+
            std::to_string(last_occluder_raster[2])+","+std::to_string(last_occluder_raster[3])+","+std::to_string(last_occluder_raster[4])+
            "],\"last_occluder_caller\":"+std::to_string(last_occluder_caller)+
            ",\"last_occluder\":["+std::to_string(last_occluder.left)+","+std::to_string(last_occluder.top)+","+
            std::to_string(last_occluder.right)+","+std::to_string(last_occluder.bottom)+"],\"font_overflow\":"+std::to_string(font_overflow)+
            ",\"font_styles\":[";
          for (uint32_t i = 0; i < font_count; ++i) {
              const auto& v = fonts[i]; if (i) fields += ',';
              fields += "{\"blob\":"+std::to_string(v.blob)+",\"rgb\":["+std::to_string(v.rgb[0])+","+std::to_string(v.rgb[1])+","+std::to_string(v.rgb[2])+
                  "],\"sampled\":"+(v.sampled?"true":"false")+",\"reference\":"+std::to_string(v.reference)+",\"uses\":"+std::to_string(v.uses)+"}";
          }
          fields += "],\"plans\":"+std::to_string(pack.count)+",\"entries\":[";
          // Only plans with activity: a full corpus would otherwise log megabytes every 5s.
          bool first_entry = true;
          for (uint32_t i = 0; i < pack.count; ++i) {
              const auto& s = stats[i];
              if (std::memcmp(&s,&untouched,sizeof(EntryStats)) == 0) continue;
              if (!first_entry) fields += ',';
              first_entry = false;
              fields += "{\"id\":"+std::to_string(pack.plans[i].entry);
#define FIELD(name) fields += ",\"" #name "\":"+std::to_string(s.name)
              FIELD(wide); FIELD(cache); FIELD(copies); FIELD(layout); FIELD(bounds); FIELD(glyph);
              FIELD(raster); FIELD(queue); FIELD(submissions); FIELD(presentations); FIELD(freed);
              FIELD(width_overrides); FIELD(unicode_draws); FIELD(composites); FIELD(cache_hits); FIELD(cache_misses);
              FIELD(raster_retired); FIELD(queue_retired);
              FIELD(shared_rasters); FIELD(name_copies);
#undef FIELD
              fields += '}';
          }
          fields += "],\"lifecycle_dropped\":"+std::to_string(life_dropped)+",\"lifecycle\":[";
          for (uint32_t i = 0; i < life_count; ++i) {
              const auto& v = life_events[i]; if (i) fields += ',';
              fields += "{\"seq\":"+std::to_string(v.sequence)+",\"tick_ms\":"+std::to_string(v.tick)+
                  ",\"kind\":"+std::to_string(static_cast<uint32_t>(v.kind))+
                  ",\"entry\":"+std::to_string(entry_of(v.plan))+",\"address\":"+std::to_string(v.address)+
                  ",\"related\":"+std::to_string(v.related)+",\"identity\":"+std::to_string(v.identity)+
                  ",\"generation\":"+std::to_string(v.generation)+",\"raster_hash_fnv1a64\":"+std::to_string(v.raster_hash)+
                  ",\"width\":"+std::to_string(v.width)+",\"height\":"+std::to_string(v.height)+
                  ",\"stride_pixels\":"+std::to_string(v.stride)+",\"glyph_count\":"+std::to_string(v.glyph_count)+"}";
          }
          fields += "],\"raster_faults\":[";
          for (uint32_t i = 0; i < raster_fault_count; ++i) {
              const auto& v = raster_faults[i]; if (i) fields += ',';
              fields += "{\"entry\":"+std::to_string(entry_of(v.plan));
#define FAULT_FIELD(name) fields += ",\"" #name "\":"+std::to_string(v.name)
              FAULT_FIELD(tick); FAULT_FIELD(frame); FAULT_FIELD(paint); FAULT_FIELD(identity);
              FAULT_FIELD(source); FAULT_FIELD(raster); FAULT_FIELD(paint_owner);
              FAULT_FIELD(widget); FAULT_FIELD(paint_caller); FAULT_FIELD(offset);
              FAULT_FIELD(native_width); FAULT_FIELD(native_height); FAULT_FIELD(prior_count);
              FAULT_FIELD(prior_identity); FAULT_FIELD(prior_generation); FAULT_FIELD(prior_paint);
#undef FAULT_FIELD
              fields += ",\"bound\":"+std::string(v.bound?"true":"false")+
                  ",\"prior_entry\":"+std::to_string(v.bound?entry_of(v.prior_plan):0)+"}";
          }
          fields += "],\"journal_probe\":{\"acp\":"+std::to_string(GetACP())+
              ",\"append_total\":"+std::to_string(journal_append_total)+",\"appends\":[";
          for (uint64_t i = 0; i < std::min<uint64_t>(journal_append_total,journal_appends.size()); ++i) {
              const auto& v = journal_appends[size_t(i)]; if (i) fields += ',';
              fields += "{\"tick_ms\":"+std::to_string(v.tick)+",\"entry\":"+std::to_string(v.entry)+
                  ",\"code_page\":"+std::to_string(v.code_page)+",\"wide_length\":"+std::to_string(v.wide_length)+
                  ",\"capacity\":"+std::to_string(v.capacity)+",\"result\":"+std::to_string(v.result)+
                  ",\"error\":"+std::to_string(v.error)+",\"high_bytes\":"+std::to_string(v.high_bytes)+
                  ",\"marker\":"+(v.marker?"true":"false")+"}";
          }
          fields += "],\"flow_overflow\":"+std::to_string(flow_overflow)+",\"flows\":[";
          bool first_flow = true;
          for (const auto& v : flows) {
              if (!v.flow) continue;
              if (!first_flow) fields += ',';
              first_flow = false;
              const auto quad = [&](const uint64_t (&a)[4]) {
                  return "["+std::to_string(a[0])+","+std::to_string(a[1])+","+std::to_string(a[2])+","+std::to_string(a[3])+"]";
              };
              fields += "{\"flow\":"+std::to_string(v.flow)+",\"caller\":"+std::to_string(v.caller)+
                  ",\"widget\":"+std::to_string(v.widget)+",\"calls\":"+std::to_string(v.calls)+
                  ",\"last_tick_ms\":"+std::to_string(v.last_tick)+",\"text_length\":"+std::to_string(v.text_length)+
                  ",\"text_high\":"+std::to_string(v.text_high)+",\"text_fnv1a64\":"+std::to_string(v.text_hash)+
                  ",\"layout\":"+quad(v.layout)+",\"bounds\":"+quad(v.bounds)+",\"glyph\":"+quad(v.glyph)+
                  ",\"glyph_outside_paint\":"+std::to_string(v.glyph_outside_paint)+
                  ",\"glyph_paint_caller\":"+std::to_string(v.glyph_paint_caller)+
                  ",\"glyph_paint_owner\":"+std::to_string(v.glyph_paint_owner)+
                  ",\"glyph_paint_widget\":"+std::to_string(v.glyph_paint_widget)+
                  ",\"glyph_raster\":"+std::to_string(v.glyph_raster)+
                  ",\"glyph_raster_size\":["+std::to_string(v.glyph_raster_width)+","+std::to_string(v.glyph_raster_height)+"]}";
          }
          const auto callers = [&](const char* name, const std::array<CallerCount,32>& table) {
              fields += ",\""+std::string(name)+"\":[";
              bool first = true;
              for (const auto& c : table) if (c.caller) {
                  if (!first) fields += ',';
                  first = false;
                  fields += "["+std::to_string(c.caller)+","+std::to_string(c.count)+"]";
              }
              fields += ']';
          };
          fields += ']';
          callers("glyph_callers",glyph_callers); callers("paint_callers",paint_callers); callers("queue_callers",queue_callers);
          fields += ",\"caller_overflow\":"+std::to_string(caller_overflow)+"}";
          fields += ",\"texture\":{\"enabled\":"+std::string(texture_enabled?"true":"false")+
              ",\"markers\":"+std::to_string(journal_markers)+",\"marker_short\":"+std::to_string(journal_marker_short)+
              ",\"expansions\":"+std::to_string(journal_expansions)+",\"spans\":"+std::to_string(journal_spans)+",\"width_overrides\":"+std::to_string(journal_width_overrides)+",\"breaks_dropped\":"+std::to_string(journal_breaks_dropped)+",\"book_converts\":"+std::to_string(book_converts)+",\"book_short\":"+std::to_string(book_short)+
              ",\"book_bound\":"+std::to_string(book_bound)+",\"book_mismatch\":"+std::to_string(book_mismatch)+
              ",\"book_width_overrides\":"+std::to_string(book_width_overrides)+",\"spaces_kept\":"+std::to_string(journal_spaces_kept)+",\"leading_applied\":"+std::to_string(journal_leading_applied)+
              ",\"unknown_markers\":"+std::to_string(journal_unknown_markers)+",\"stale\":"+std::to_string(journal_stale)+
              ",\"alloc_failures\":"+std::to_string(journal_alloc_failures)+",\"glyphs\":"+std::to_string(texture_glyphs)+
              ",\"pixels\":"+std::to_string(texture_pixels)+",\"faults\":"+std::to_string(texture_faults)+
              ",\"rejects\":["+std::to_string(texture_rejects[0])+","+std::to_string(texture_rejects[1])+","+
              std::to_string(texture_rejects[2])+","+std::to_string(texture_rejects[3])+"]"+
              ",\"misc\":{\"marked\":"+std::to_string(misc_marked)+",\"mark_failures\":"+std::to_string(misc_mark_failures)+
              ",\"stripped\":"+std::to_string(misc_stripped)+",\"buffers\":"+std::to_string(misc_buffers)+
              ",\"invalid\":"+std::to_string(misc_invalid)+",\"partial\":"+std::to_string(misc_partial)+
              ",\"leaks\":"+std::to_string(misc_leaks)+"},\"inks\":[";
          for (uint32_t i = 0; i < ink_count; ++i) {
              const auto& v = inks[i]; if (i) fields += ',';
              fields += "{\"blob\":"+std::to_string(v.blob)+",\"type\":"+std::to_string(v.type)+
                  ",\"usable\":"+(v.usable?"true":"false")+",\"reference\":"+std::to_string(v.reference)+
                  ",\"value\":"+std::to_string(v.value)+",\"solid\":"+std::to_string(v.solid)+
                  ",\"written\":"+std::to_string(v.written)+",\"dx\":"+std::to_string(v.dx)+",\"dy\":"+std::to_string(v.dy)+"}";
          }
          fields += "]}";
          life_count = 0; raster_fault_count = 0;
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
