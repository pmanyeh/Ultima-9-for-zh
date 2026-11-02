#include "identity.h"
#include "platform.h"
#include <algorithm>
#include <cstring>
#include <fstream>

namespace u9cht {
void Pack::load(const std::filesystem::path& path, bool render) {
    count = glyph_count = 0; plans = {}; scalars = {}; has_names = false;
    resource_hash.clear(); typename_hash.clear();
    std::ifstream in(path, std::ios::binary);
    require(bool(in), "allowlist open failed");
    auto read = [&](void* out, size_t size) {
        in.read(static_cast<char*>(out), static_cast<std::streamsize>(size));
        require(bool(in), "truncated allowlist");
    };
    char magic[8]{}; uint32_t version = 0, requested = 0;
    read(magic, 8); read(&version, 4); read(&requested, 4);
    require(std::memcmp(magic, "U9CTP51\0", 8) == 0 && (version == 1 || ((version == 2 || version == 3) && render)) &&
            requested && requested <= (version == 1 ? 16 : MaxPlans),
            "invalid allowlist header");
    char hash[64]; read(hash, 64);
    resource_hash.clear();
    for (char c : hash) {
        require((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), "invalid resource hash");
        resource_hash += static_cast<wchar_t>(c);
    }
    if (version == 3) {
        read(hash,64);
        for (char c : hash) {
            require((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), "invalid typename hash");
            typename_hash += static_cast<wchar_t>(c);
        }
    }
    if (version >= 2) {
        read(&glyph_count,4);
        require(glyph_count && glyph_count <= MaxGlyphScalars, "invalid glyph allowlist capacity");
        for (uint32_t i = 0; i < glyph_count; ++i) {
            auto& s = scalars[i]; read(&s,4);
            require(((s >= 0x3000 && s <= 0x303F) || (s >= 0x3400 && s <= 0x9FFF) ||
                (s >= 0xFF01 && s <= 0xFF60)) && (!i || s > scalars[i-1]), "invalid/unsorted glyph scalar");
        }
    }
    std::array<bool,MaxGlyphScalars> used{};
    for (uint32_t i = 0; i < requested; ++i) {
        auto& p = plans[i]; read(&p.entry, 4); read(&p.length, 4);
        if (version == 3) {
            require(p.entry < 65536 || (p.entry & 0xFFFFE000) == NameDomain, "invalid resource domain/entry");
            if (p.is_name()) {
                has_names = true;
                p.marker[0] = 'U'; p.marker[1] = '9'; p.marker[2] = 'T';
                constexpr char hex[] = "0123456789ABCDEF";
                for (uint32_t j = 0; j < 4; ++j) p.marker[3+j] = hex[(p.entry >> ((3-j)*4)) & 15];
            }
        }
        require(p.length && p.length <= MaxText, "invalid allowlist text length");
        for (uint32_t j = 0; j < i; ++j) require(plans[j].entry != p.entry, "duplicate allowlist entry");
        read(p.wide.data(), size_t(p.length)*2);
        for (uint32_t j = 0; j < p.length; ++j) {
            auto c = p.wide[j];
            const auto begin = scalars.begin(), end = begin+glyph_count;
            const auto it = std::lower_bound(begin,end,uint32_t(c));
            const bool listed = version >= 2 && it != end && *it == c;
            require((c >= 32 && c < 127) || (version >= 2 && c == '\n' && !p.is_name()) ||
                    (render && (listed || (version == 1 && (c == 0x4E2D || c == 0x6587)))),
                    "unsupported scalar/control in bounded corpus");
            if (listed) used[size_t(it-begin)] = true;
            p.slots[j] = c < 128 ? static_cast<uint8_t>(c) : 0x7F;
        }
        for (uint32_t j = 0; j < i; ++j)
            require(p.is_name() || plans[j].is_name() || plans[j].length != p.length || std::memcmp(plans[j].wide.data(), p.wide.data(), p.length*2) != 0,
                    "ambiguous allowlist identity");
    }
    require(version == 1 || std::all_of(used.begin(),used.begin()+glyph_count,[](bool b) { return b; }),
            "unused glyph allowlist entry");
    require(in.peek() == std::char_traits<char>::eof(), "trailing allowlist bytes");
    require(version != 3 || has_names, "name pack has no selected names");
    count = requested;
}
int Pack::match(const wchar_t* text) const noexcept {
    if (!text) return -1;
    size_t length = 0;
    while (length <= MaxText && text[length]) ++length;
    for (uint32_t i = 0; i < count; ++i)
        if (!plans[i].is_name() && length == plans[i].length && std::memcmp(text, plans[i].wide.data(), length*2) == 0) return int(i);
    return -1;
}
int Pack::match_name(const char* text, uintptr_t caller) const noexcept {
    if (!has_names || !text || caller != NameCopyCaller) return -1;
    for (uint32_t i = 0; i < count; ++i)
        if (plans[i].is_name() && std::strncmp(text,plans[i].marker.data(),plans[i].marker.size()) == 0) return int(i);
    return -1;
}
Binding* Registry::bind(uintptr_t address, uint32_t length, uint32_t plan, uint64_t identity) noexcept {
    if (!address || !length || address+length < address || plan >= MaxPlans) return nullptr;
    retire(address); // A new allocation/copy at the same address is a new generation.
    for (const auto& b : buffers_)
        if (b.base && address < b.base+b.length && b.base < address+length) return nullptr;
    for (auto& b : buffers_) if (!b.base) {
        b = {address, length, plan, identity ? identity : ++identities_, ++next_};
        maximum = std::max(maximum, count()); return &b;
    }
    return nullptr;
}
Located Registry::locate(uintptr_t address) noexcept {
    for (auto& b : buffers_) if (b.base && address >= b.base && address < b.base+b.length-1)
        return {&b, static_cast<uint32_t>(address-b.base)};
    return {};
}
bool Registry::retire(uintptr_t address) noexcept {
    for (auto& b : buffers_) if (b.base == address && address) { b = {}; return true; }
    return false;
}
uint32_t Registry::count() const noexcept {
    uint32_t n = 0; for (const auto& b : buffers_) n += b.base != 0; return n;
}
}
