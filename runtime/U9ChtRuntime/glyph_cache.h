#pragma once
#include "platform.h"
#include "version_manifest.h"
#include <array>
#include <vector>
#include <span>

namespace u9cht {
inline constexpr size_t GlyphCacheCapacity = 16384;
// P8-3: page textures (journal/books) take glyph pixels 1:1; a 16 px em equals the 16-unit logical cell.
inline constexpr uint32_t TextureEm = 16;
// P10-1: misctext UI text in small native fonts (font blob +4 = height) uses a smaller CJK em. Journal, book and
// sign text keep TextureEm. Heights seen in game: 15 (options labels, message box), 18 (books), 21 (messages).
inline constexpr uint32_t TextureSmallEm = 14, TextureTinyEm = 12;
inline constexpr uint32_t texture_em_for_height(uint32_t height) noexcept {
    return height >= 17 ? TextureEm : height >= 15 ? TextureSmallEm : TextureTinyEm;
}
// Logical advance of a CJK cell at a texture em (the 16-unit cell scaled to the em).
inline constexpr uint32_t texture_advance(uint32_t base, uint32_t em) noexcept { return base*em/TextureEm; }
static_assert(texture_em_for_height(21) == 16 && texture_em_for_height(18) == 16 && texture_em_for_height(17) == 16);
static_assert(texture_em_for_height(16) == 14 && texture_em_for_height(15) == 14 && texture_em_for_height(14) == 12);
static_assert(texture_advance(16,16) == 16 && texture_advance(16,14) == 14 && texture_advance(16,12) == 12);
// Offline layout assumes every CJK glyph advances exactly one cell (u9cht/l10n runtime contract).
inline constexpr uint32_t LayoutCellUnits = 16;
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
// Open-addressed scalar/em -> slot table. No allocation; load factor <= 25%.
class GlyphIndex {
    std::array<uint16_t,65536> slots_{}; // Stored value is slot+1; 0 means empty.
    static uint32_t home(uint32_t scalar, uint32_t em) noexcept { return ((scalar*0x9E3779B1U)^(em*0x85EBCA77U))>>16; }
public:
    template <class Keys>
    int find(uint32_t scalar, uint32_t em, const Keys& keys) const noexcept {
        for (uint32_t i = home(scalar,em);; i = (i+1)&0xFFFF) {
            const auto stored = slots_[i];
            if (!stored) return -1;
            const GlyphKey& k = keys[stored-1U];
            if (k.scalar == scalar && k.em == em) return stored-1;
        }
    }
    void insert(uint32_t scalar, uint32_t em, uint32_t slot) noexcept {
        auto i = home(scalar,em);
        while (slots_[i]) i = (i+1)&0xFFFF;
        slots_[i] = uint16_t(slot+1);
    }
    void clear() noexcept { slots_.fill(0); }
};
// P9-1: the CJK font is chosen by the player. Identity is the file's SHA-256 (checked again against
// the face GDI actually selects), and the family comes from the file's own OpenType name table.
std::wstring font_family_from_sfnt(std::span<const uint8_t> data);
class GlyphCache {
    std::filesystem::path path_;
    std::wstring hash_, family_;
    bool registered_ = false;
    std::array<Glyph,GlyphCacheCapacity> entries_;
    struct KeyView {
        const std::array<Glyph,GlyphCacheCapacity>& entries;
        const GlyphKey& operator[](size_t i) const noexcept { return entries[i].key; }
    };
    GlyphIndex index_;
    uint64_t alpha_bytes_ = 0;
    std::array<bool,257> verified_em_{};
    uint32_t size_ = 0;
public:
    uint64_t hits = 0, misses = 0;
    ~GlyphCache() { close(); }
    void open(const std::filesystem::path& font);
    const Glyph* get(uint32_t scalar, uint32_t em) noexcept;
    void warm(uint32_t scalar, uint32_t em);
    uint32_t size() const noexcept { return size_; }
    uint64_t alpha_bytes() const noexcept { return alpha_bytes_; }
    const std::wstring& font_sha256() const noexcept { return hash_; }
    const std::wstring& font_family() const noexcept { return family_; }
    bool close() noexcept;
};
}
