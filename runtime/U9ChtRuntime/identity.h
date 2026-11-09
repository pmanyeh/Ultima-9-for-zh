#pragma once
#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <span>
#include <vector>

namespace u9cht {
// Full-corpus bound: 7390 editable text.flx + 2032 TYPENAME entries < MaxPlans.
inline constexpr size_t MaxPlans = 16384, MaxText = 512, MaxGlyphScalars = 8192;
inline constexpr uint32_t NameDomain = 0x10000000;
// P9-4: BOOKS-EN bodies stored as UTF-16 (the game's own BOM format) and identified at conversion time.
inline constexpr uint32_t BookDomain = 0x20000000;
inline constexpr size_t MaxBookText = 8192;
inline constexpr uintptr_t BookConvertReturn = 0x42E64A;
inline constexpr uintptr_t NameCopyCaller = 0x41AD54;
struct Plan {
    uint32_t entry = 0, length = 0;
    // Each holds length+1 elements; the last is the NUL terminator.
    std::vector<char16_t> wide;
    std::vector<uint8_t> slots;
    std::vector<uint16_t> advances;
    std::array<char,8> marker{};
    bool is_name() const noexcept { return (entry & 0xF0000000) == NameDomain; }
    bool is_book() const noexcept { return (entry & 0xF0000000) == BookDomain; }
};
struct PlanIndex { uint32_t hash = 0, plan = 0; };
struct Pack {
    uint32_t count = 0;
    std::wstring resource_hash;
    std::wstring typename_hash;
    std::wstring books_hash;
    bool has_names = false, has_books = false;
    std::vector<Plan> plans;
    uint32_t glyph_count = 0;
    std::array<uint32_t, MaxGlyphScalars> scalars{};
    void load(const std::filesystem::path& path, bool render);
    int match(const wchar_t* text) const noexcept;
    int match_name(const char* text, uintptr_t caller) const noexcept;
    int match_book(const wchar_t* text, size_t length) const noexcept;
private:
    // Sorted by hash at load; lookups never allocate or scan every plan.
    std::vector<PlanIndex> text_index_, name_index_, book_index_;
};
struct Binding {
    uintptr_t base = 0;
    uint32_t length = 0, plan = 0;
    uint64_t identity = 0, generation = 0;
};
struct Located { Binding* binding = nullptr; uint32_t offset = 0; };
// No allocations or game reads: callers validate exact live bytes separately.
class Registry {
    std::array<Binding, 512> buffers_{};
    uint64_t next_ = 0, identities_ = 0;
public:
    uint32_t maximum = 0;
    Binding* bind(uintptr_t address, uint32_t length, uint32_t plan, uint64_t identity = 0) noexcept;
    Located locate(uintptr_t address) noexcept;
    bool retire(uintptr_t address) noexcept;
    uint32_t count() const noexcept;
    std::span<const Binding> bindings() const noexcept { return buffers_; }
    void clear() noexcept { for (auto& b : buffers_) b = {}; }
};
}
