#include "hook_manager.h"
#include "platform.h"
#include <algorithm>
#include <cstring>
#include <numeric>

namespace u9cht {
namespace {
void jump(uint8_t* out, uintptr_t from, uintptr_t to) {
    out[0] = 0xE9;
    const uint32_t displacement = static_cast<uint32_t>(to - (from + 5));
    std::memcpy(out + 1, &displacement, sizeof(displacement));
}
LONG64 value64(const std::array<uint8_t, 8>& bytes) {
    LONG64 value = 0; std::memcpy(&value, bytes.data(), 8); return value;
}
class Writable {
    void* address_;
    size_t size_;
    DWORD old_ = 0;
    bool restored_ = false;
public:
    Writable(uintptr_t address, size_t size) : address_(reinterpret_cast<void*>(address)), size_(size) {
        require(VirtualProtect(address_, size_, PAGE_EXECUTE_READWRITE, &old_), "hook protection change failed");
    }
    ~Writable() { if (!restored_) { DWORD ignored = 0; VirtualProtect(address_, size_, old_, &ignored); } }
    void finish() {
        DWORD ignored = 0;
        require(VirtualProtect(address_, size_, old_, &ignored), "hook protection restoration failed");
        restored_ = true;
        require(FlushInstructionCache(GetCurrentProcess(), address_, size_), "hook instruction flush failed");
    }
};
void change(HookRecord& record, bool install) {
    auto* site = reinterpret_cast<uint8_t*>(record.address);
    const auto& expected = install ? record.original : record.replacement;
    const auto& desired = install ? record.replacement : record.original;
    require(std::memcmp(site, expected.data(), expected.size()) == 0, "unexpected live hook bytes/pointer");
    if (record.pointer) {
        Writable writable(record.address, 4);
        uint32_t before = 0, after = 0;
        std::memcpy(&before, expected.data(), 4); std::memcpy(&after, desired.data(), 4);
        const auto observed = InterlockedCompareExchange(reinterpret_cast<volatile LONG*>(site),
                                                         static_cast<LONG>(after), static_cast<LONG>(before));
        require(static_cast<uint32_t>(observed) == before, "concurrent pointer modification");
        record.installed = install; writable.finish();
    } else {
        const size_t region_size = std::max<size_t>(8, record.address + expected.size() - record.atomic_address);
        Writable writable(record.atomic_address, region_size);
        const auto& before = install ? record.atomic_original : record.atomic_replacement;
        const auto& after = install ? record.atomic_replacement : record.atomic_original;
        // While E9 is installed, no valid execution falls through its NOP tail.
        // Restore that tail before atomically publishing the first five original
        // bytes. Gateways stay alive until startup rollback or process teardown.
        const uintptr_t tail = record.atomic_address + 8;
        if (record.address + desired.size() > tail) {
            const size_t offset = tail - record.address;
            std::memcpy(reinterpret_cast<void*>(tail), desired.data() + offset, desired.size() - offset);
        }
        const auto observed = InterlockedCompareExchange64(reinterpret_cast<volatile LONG64*>(record.atomic_address),
                                                           value64(after), value64(before));
        if (observed != value64(before) && record.address + desired.size() > tail) {
            const size_t offset = tail-record.address;
            std::memcpy(reinterpret_cast<void*>(tail), expected.data()+offset, expected.size()-offset);
        }
        require(observed == value64(before), "concurrent inline-prefix modification");
        record.installed = install; writable.finish();
    }
    require(std::memcmp(site, desired.data(), desired.size()) == 0, "hook byte verification failed");
}
}
HookManager::~HookManager() {
    // Never release a gateway while a live patch might still reference it.
    const bool active = std::any_of(records_.begin(), records_.end(), [](const auto& r) { return r.installed; });
    if (!active && !retain_gateways_)
        for (auto& r : records_) if (r.gateway) VirtualFree(r.gateway, 0, MEM_RELEASE);
}
void* HookManager::prepare_inline(const char* name, void* address, void* target,
                                 std::span<const uint8_t> expected, std::span<const uint8_t> lengths) {
    require(address && target && expected.size() >= 5 && expected.size() <= 32, "invalid inline span");
    const auto site = reinterpret_cast<uintptr_t>(address);
    require((site & 7) <= 3, "five-byte detour crosses atomic prefix boundary");
    size_t offset = 0;
    for (auto length : lengths) {
        require(length && offset + length <= expected.size(), "invalid instruction boundary metadata");
        const uint8_t opcode = expected[offset];
        require(opcode != 0xE8 && opcode != 0xE9 && opcode != 0xEB && opcode != 0xC2 && opcode != 0xC3 &&
                !(opcode >= 0x70 && opcode <= 0x7F) && !(opcode >= 0xE0 && opcode <= 0xE3) &&
                !(opcode == 0x0F && length >= 2 && expected[offset+1] >= 0x80 && expected[offset+1] <= 0x8F),
                "unsupported control transfer in gateway span");
        offset += length;
    }
    require(offset == expected.size(), "incomplete instruction metadata");
    require(std::memcmp(address, expected.data(), expected.size()) == 0, "inline baseline mismatch");
    const auto atomic = site & ~uintptr_t(7);
    for (const auto& r : records_)
        require(r.pointer || r.atomic_address != atomic, "overlapping inline atomic region");
    HookRecord record; record.name = name; record.address = site; record.atomic_address = atomic;
    record.original.assign(expected.begin(), expected.end());
    record.replacement.assign(expected.size(), 0x90);
    jump(record.replacement.data(), site, reinterpret_cast<uintptr_t>(target));
    std::memcpy(record.atomic_original.data(), reinterpret_cast<const void*>(atomic), 8);
    record.atomic_replacement = record.atomic_original;
    for (size_t i = 0; i < expected.size() && site+i < atomic+8; ++i)
        record.atomic_replacement[site+i-atomic] = record.replacement[i];
    record.gateway = VirtualAlloc(nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    require(record.gateway != nullptr, "gateway allocation failed");
    try {
        auto* code = static_cast<uint8_t*>(record.gateway);
        std::memcpy(code, expected.data(), expected.size());
        jump(code+expected.size(), reinterpret_cast<uintptr_t>(code)+expected.size(), site+expected.size());
        DWORD old = 0;
        require(VirtualProtect(code, 4096, PAGE_EXECUTE_READ, &old), "gateway RX protection failed");
        require(FlushInstructionCache(GetCurrentProcess(), code, expected.size()+5), "gateway cache flush failed");
        auto* result = record.gateway; records_.push_back(std::move(record)); return result;
    } catch (...) { VirtualFree(record.gateway, 0, MEM_RELEASE); throw; }
}
void HookManager::prepare_pointer(const char* name, uintptr_t* address, uintptr_t expected, uintptr_t target) {
    require(address && target && (reinterpret_cast<uintptr_t>(address) & 3) == 0, "unaligned pointer slot");
    require(*address == expected, "pointer baseline mismatch");
    HookRecord record; record.name = name; record.address = reinterpret_cast<uintptr_t>(address); record.pointer = true;
    record.original.resize(4); record.replacement.resize(4);
    std::memcpy(record.original.data(), &expected, 4); std::memcpy(record.replacement.data(), &target, 4);
    records_.push_back(std::move(record));
}
void HookManager::install() {
    try { for (auto& record : records_) change(record, true); }
    catch (...) { restore(true); throw; }
}
bool HookManager::restore(bool release_gateways) noexcept {
    bool ok = true;
    for (auto i = records_.rbegin(); i != records_.rend(); ++i) if (i->installed) {
        try { change(*i, false); } catch (...) { ok = false; }
    }
    ok = ok && originals_match();
    if (ok && release_gateways) {
        for (auto& r : records_) if (r.gateway) { VirtualFree(r.gateway, 0, MEM_RELEASE); r.gateway = nullptr; }
    }
    if (!release_gateways) retain_gateways_ = true;
    return ok;
}
bool HookManager::originals_match() const noexcept {
    for (const auto& r : records_)
        if (r.installed || std::memcmp(reinterpret_cast<void*>(r.address), r.original.data(), r.original.size()) != 0)
            return false;
    return true;
}
}
