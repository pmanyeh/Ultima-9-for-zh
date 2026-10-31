#include "platform.h"
#include "hook_manager.h"
#include <array>
#include <atomic>
#include <cstring>
#include <iostream>
#include <thread>

namespace {
int __cdecl replacement() { return 11; }
}
int main() {
    using namespace u9cht;
    auto* memory = static_cast<uint8_t*>(VirtualAlloc(nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE));
    if (!memory) return 1;
    try {
        std::memset(memory, 0x90, 4096);
        constexpr std::array<uint8_t, 7> original{0xB8,7,0,0,0,0x40,0x40};
        constexpr std::array<uint8_t, 3> lengths{5,1,1};
        auto* site = memory+0x43;
        std::memcpy(site, original.data(), original.size()); site[7] = 0xC3;
        using Function = int(__cdecl*)();
        auto function = reinterpret_cast<Function>(site);
        require(function() == 9, "fixture original function failed");
        HookManager hooks;
        auto gateway = reinterpret_cast<Function>(hooks.prepare_inline("fixture", site,
                      reinterpret_cast<void*>(replacement), original, lengths));
        require(gateway() == 9, "gateway changed original instruction behavior");
        hooks.install(); require(function() == 11, "detour did not route");
        std::atomic<bool> run{true}, bad{false};
        std::atomic<uint32_t> calls{0};
        std::thread caller([&] { while (run.load()) {
            auto value = function(); if (value != 9 && value != 11) bad = true; calls.fetch_add(1);
        } });
        while (calls.load() < 1000) SwitchToThread();
        const bool restored = hooks.restore(false);
        run = false; caller.join();
        require(restored && hooks.originals_match() && function() == 9 && !bad,
                "atomic-prefix restoration failed under concurrent calls");
        require(hooks.restore(true), "gateway release after quiescence failed");
        bool rejected = false;
        auto wrong = original; wrong[1] = 8;
        try { hooks.prepare_inline("wrong", site, reinterpret_cast<void*>(replacement), wrong, lengths); }
        catch (...) { rejected = true; }
        require(rejected && function() == 9, "unexpected original bytes were accepted");
        rejected = false;
        try { hooks.prepare_inline("unaligned", site+1, reinterpret_cast<void*>(replacement), original, lengths); }
        catch (...) { rejected = true; }
        require(rejected, "detour crossing atomic prefix boundary was accepted");
        alignas(4) uintptr_t slot = 0x12345678;
        HookManager pointers;
        pointers.prepare_pointer("pointer", &slot, slot, 0x23456789);
        pointers.install(); require(slot == 0x23456789, "pointer swap failed");
        require(pointers.restore(true) && slot == 0x12345678, "pointer rollback failed");
        // A later live-byte mismatch must roll back earlier installed patches.
        HookManager transaction;
        transaction.prepare_pointer("first", &slot, slot, 0x34567890);
        alignas(4) uintptr_t second = 8;
        transaction.prepare_pointer("second", &second, second, 9); second = 10;
        rejected = false; try { transaction.install(); } catch (...) { rejected = true; }
        require(rejected && slot == 0x12345678, "partial installation was not rolled back");
        VirtualFree(memory, 0, MEM_RELEASE);
        std::cout << "PASS: 10 native hook/gateway/rollback checks including concurrent restore\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; VirtualFree(memory,0,MEM_RELEASE); return 1; }
}
