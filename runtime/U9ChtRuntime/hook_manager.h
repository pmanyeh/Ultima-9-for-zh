#pragma once
#include <windows.h>
#include <array>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace u9cht {
struct HookRecord {
    std::string name;
    uintptr_t address = 0;
    std::vector<uint8_t> original;
    std::vector<uint8_t> replacement;
    void* gateway = nullptr;
    bool installed = false;
    bool pointer = false;
    uintptr_t atomic_address = 0;
    std::array<uint8_t, 8> atomic_original{};
    std::array<uint8_t, 8> atomic_replacement{};
};
// Fixed-baseline patcher, not a disassembler or general detour framework.
// Callers supply already reviewed complete instruction spans. Relative/control
// transfer instructions in copied spans are rejected; no silent relocation.
class HookManager {
    std::vector<HookRecord> records_;
    bool retain_gateways_ = false;
public:
    HookManager() = default;
    ~HookManager();
    HookManager(const HookManager&) = delete;
    HookManager& operator=(const HookManager&) = delete;
    void* prepare_inline(const char* name, void* address, void* target,
                         std::span<const uint8_t> expected, std::span<const uint8_t> lengths);
    void prepare_pointer(const char* name, uintptr_t* address, uintptr_t expected, uintptr_t target);
    void install();
    bool restore(bool release_gateways) noexcept;
    bool originals_match() const noexcept;
    const std::vector<HookRecord>& records() const { return records_; }
};
}
