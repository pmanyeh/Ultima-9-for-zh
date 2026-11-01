#pragma once
#include "platform.h"
#include "version_manifest.h"
#include <array>
#include <vector>
#include <span>

namespace u9cht {
inline constexpr size_t GlyphCacheCapacity = 1024;
struct GlyphKey {
    std::array<wchar_t,65> font{};
    uint32_t scalar = 0, em = 0, mode = 0;
    bool operator==(const GlyphKey&) const = default;
};
struct Glyph {
    GlyphKey key;
    uint32_t index = 0, width = 0, height = 0;
    int32_t bearing_x = 0, bearing_y = 0, advance = 0;
    std::vector<uint8_t> alpha;
};
const Glyph* find_glyph(std::span<const Glyph> cache, const GlyphKey& key) noexcept;
class GlyphCache {
    std::filesystem::path path_;
    bool registered_ = false;
    std::array<Glyph,GlyphCacheCapacity> entries_;
    std::array<bool,257> verified_em_{};
    uint32_t size_ = 0;
public:
    uint64_t hits = 0, misses = 0;
    ~GlyphCache() { close(); }
    void open(const std::filesystem::path& font);
    const Glyph* get(uint32_t scalar, uint32_t em) noexcept;
    void warm(uint32_t scalar, uint32_t em);
    uint32_t size() const noexcept { return size_; }
    bool close() noexcept;
};
}
