#pragma once
#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <span>

namespace u9cht {
inline constexpr size_t MaxPlans = 16, MaxText = 512;
struct Plan {
    uint32_t entry = 0, length = 0;
    std::array<char16_t, MaxText+1> wide{};
    std::array<uint8_t, MaxText+1> slots{};
};
struct Pack {
    uint32_t count = 0;
    std::wstring resource_hash;
    std::array<Plan, MaxPlans> plans{};
    void load(const std::filesystem::path& path, bool render);
    int match(const wchar_t* text) const noexcept;
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
