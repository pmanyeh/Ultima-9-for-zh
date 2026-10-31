#include "identity.h"
#include "platform.h"
#include <algorithm>
#include <cstring>
#include <fstream>

namespace u9cht {
void Pack::load(const std::filesystem::path& path, bool render) {
    std::ifstream in(path, std::ios::binary);
    require(bool(in), "allowlist open failed");
    auto read = [&](void* out, size_t size) {
        in.read(static_cast<char*>(out), static_cast<std::streamsize>(size));
        require(bool(in), "truncated allowlist");
    };
    char magic[8]{}; uint32_t version = 0;
    read(magic, 8); read(&version, 4); read(&count, 4);
    require(std::memcmp(magic, "U9CTP51\0", 8) == 0 && version == 1 && count && count <= MaxPlans,
            "invalid allowlist header");
    char hash[64]; read(hash, 64);
    resource_hash.clear();
    for (char c : hash) {
        require((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), "invalid resource hash");
        resource_hash += static_cast<wchar_t>(c);
    }
    for (uint32_t i = 0; i < count; ++i) {
        auto& p = plans[i]; read(&p.entry, 4); read(&p.length, 4);
        require(p.length && p.length <= MaxText, "invalid allowlist text length");
        for (uint32_t j = 0; j < i; ++j) require(plans[j].entry != p.entry, "duplicate allowlist entry");
        read(p.wide.data(), size_t(p.length)*2);
        for (uint32_t j = 0; j < p.length; ++j) {
            auto c = p.wide[j];
            require(c >= 32 && (c < 127 || (render && (c == 0x4E2D || c == 0x6587))),
                    "unsupported scalar/control in bounded P5.1 corpus");
            p.slots[j] = c < 128 ? static_cast<uint8_t>(c) : 0x7F;
        }
        for (uint32_t j = 0; j < i; ++j)
            require(plans[j].length != p.length || std::memcmp(plans[j].wide.data(), p.wide.data(), p.length*2) != 0,
                    "ambiguous allowlist identity");
    }
    require(in.peek() == std::char_traits<char>::eof(), "trailing allowlist bytes");
}
int Pack::match(const wchar_t* text) const noexcept {
    if (!text) return -1;
    size_t length = 0;
    while (length <= MaxText && text[length]) ++length;
    for (uint32_t i = 0; i < count; ++i)
        if (length == plans[i].length && std::memcmp(text, plans[i].wide.data(), length*2) == 0) return int(i);
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
