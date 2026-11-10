#pragma once
// P10-1 M1: misctext UI marker bridge. Header-only, no game access: tested by misc_marker_tests.cpp.
//
// A misctext string object (constructed by the named-text factory 0x616120, constructor return 0x6161AB)
// carries `marker + slot string` in obj+0. UI code copies and concatenates those bytes inline; the paged
// text-flow initializer 0x5C7620 then strips every marker in place (the buffer only shrinks, ownership and
// the char** the flow keeps are unchanged) and records which slot bytes belong to which plan.
#include <array>
#include <cstdint>
#include <cstring>
#include <vector>

namespace u9cht {
// Must be >= 0x20: the draw-string routine 0x5C5C00 sends every byte above 0x0D to the glyph function 0x5C5A80,
// which returns NULL below 0x20 and the game then quits ("Invalid character encountered in print.", session-2).
// 0x8F is undefined in Windows-1252 (never produced from real text) and never appears in plan slots.
inline constexpr uint8_t MiscMarkerLead = 0x8F;
inline constexpr uint32_t MiscMarkerSize = 4;       // lead + three base-94 digits (0x21..0x7E)
inline constexpr uint32_t MiscMarkerLimit = 94*94*94;
inline constexpr uintptr_t MiscTextCtorReturn = 0x6161AB;
inline constexpr uint32_t DrawStringUnbounded = 0xFFFFFFFF;

inline bool encode_misc_marker(uint32_t plan, char* out) noexcept {
    if (plan >= MiscMarkerLimit) return false;
    out[0] = char(MiscMarkerLead);
    out[1] = char(0x21 + plan/(94*94)); out[2] = char(0x21 + plan/94%94); out[3] = char(0x21 + plan%94);
    return true;
}
inline bool decode_misc_marker(const uint8_t* p, uint32_t available, uint32_t& plan) noexcept {
    if (available < MiscMarkerSize || p[0] != MiscMarkerLead) return false;
    uint32_t v = 0;
    for (uint32_t i = 1; i < MiscMarkerSize; ++i) {
        if (p[i] < 0x21 || p[i] > 0x7E) return false;
        v = v*94 + uint32_t(p[i]-0x21);
    }
    plan = v; return true;
}
struct MiscSegment { uint32_t offset = 0, plan = 0, length = 0; };
struct MiscStrip { uint32_t markers = 0, invalid = 0, partial = 0, length = 0; std::vector<MiscSegment> segments; };
// `slots(plan, length)` returns the plan's slot bytes (nullptr for an unknown plan) and sets its length.
// Strips every well-formed marker from text[0..length) in place and keeps the NUL at the new end.
// A marker whose following bytes match only a prefix of the plan (a truncated copy) binds that prefix.
// A lead byte that does not form a valid marker is left untouched and counted as invalid.
template <class Slots>
MiscStrip strip_misc_markers(uint8_t* text, uint32_t length, Slots&& slots) {
    MiscStrip r;
    uint32_t write = 0;
    for (uint32_t read = 0; read < length;) {
        uint32_t plan = 0, plan_length = 0;
        const uint8_t* expected = nullptr;
        if (text[read] == MiscMarkerLead && decode_misc_marker(text+read,length-read,plan) &&
            (expected = slots(plan,plan_length)) != nullptr) {
            read += MiscMarkerSize; ++r.markers;
            uint32_t n = 0;
            while (n < plan_length && read+n < length && text[read+n] == expected[n]) ++n;
            if (n < plan_length) ++r.partial;
            if (n) r.segments.push_back({write,plan,n});
            std::memmove(text+write,text+read,n); write += n; read += n;
            continue;
        }
        if (text[read] == MiscMarkerLead) ++r.invalid;
        text[write++] = text[read++];
    }
    if (write < length) text[write] = 0;
    r.length = write;
    return r;
}
}
