#include "platform.h"
#include "version_manifest.h"
#include "engine.h"
#include <memory>

namespace {
u9cht::Logger log_file;
bool initialized = false;
}

extern "C" DWORD WINAPI U9ChtInitialize(void* argument) noexcept {
    auto* config = static_cast<u9cht::Config*>(argument);
    if (!config || !u9cht::valid_protocol(*config)) return 0;
    config->state = u9cht::State::Initializing;
    config->error = u9cht::Error::Initialization;
    try {
        u9cht::require(!initialized, "runtime already initialized");
        const auto game = u9cht::config_path(config->game_dir);
        log_file.open(u9cht::config_path(config->log_path), false);
        log_file.event("runtime_initializing", "\"version\":\"U9ChtRuntime/0.1.0-p5.1\",\"hooks\":0");
        config->process_id = GetCurrentProcessId();
        config->image_base = reinterpret_cast<uint32_t>(GetModuleHandleW(nullptr));
        config->error = u9cht::Error::ImageBase;
        u9cht::require(config->image_base == u9cht::GameBase, "unexpected game image base");
        config->error = u9cht::Error::Baseline;
        u9cht::require(u9cht::sha256(game / L"u9.exe") == u9cht::ExeHash, "executable hash mismatch");
        u9cht::require(u9cht::sha256(game / L"ddraw.dll") == u9cht::WrapperHash, "wrapper hash mismatch");
        u9cht::require(std::filesystem::equivalent(u9cht::module_path(nullptr), game / L"u9.exe"),
                       "running executable path mismatch");
        config->error = u9cht::Error::Configuration;
        u9cht::require(!IsDebuggerPresent(), "normal-launch gate requires no attached debugger");
        if (auto wrapper = GetModuleHandleW(L"ddraw.dll")) {
            config->error = u9cht::Error::WrapperBase;
            config->wrapper_base = reinterpret_cast<uint32_t>(wrapper);
            u9cht::require(config->wrapper_base == u9cht::WrapperBase &&
                           std::filesystem::equivalent(u9cht::module_path(wrapper), game / L"ddraw.dll"),
                           "unexpected loaded wrapper");
        }
        config->error = u9cht::Error::UnsupportedMode;
        if (config->mode != u9cht::Mode::Bootstrap) {
            config->error = u9cht::Error::Initialization;
            u9cht::engine = new u9cht::Engine;
            u9cht::engine->install(*config, log_file);
            config->hooks_installed = static_cast<uint32_t>(u9cht::engine->hooks.records().size());
        }
        config->error = u9cht::Error::ForcedFailure;
        u9cht::require(!(config->flags & u9cht::ForceFailure), "requested initialization failure test");
        initialized = true;
        config->state = u9cht::State::Ready; config->error = u9cht::Error::None;
        log_file.event("runtime_ready", "\"hooks\":"+std::to_string(config->hooks_installed)+
                       ",\"debugger_attached\":false,\"debugger_required\":false");
        return 1;
    } catch (...) {
        config->state = u9cht::State::Fail;
        if (u9cht::engine) {
            if (!u9cht::engine->shutdown(true)) config->error = u9cht::Error::Rollback;
            else { delete u9cht::engine; u9cht::engine = nullptr; config->hooks_installed = 0; }
        }
        log_file.event("runtime_fail", "\"error\":" + std::to_string(static_cast<uint32_t>(config->error)));
        initialized = false; log_file.close(); return 0;
    }
}
extern "C" DWORD WINAPI U9ChtShutdown(void*) noexcept {
    if (u9cht::engine) {
        if (!u9cht::engine->shutdown(true)) return 0;
        delete u9cht::engine; u9cht::engine = nullptr;
    }
    log_file.event("runtime_stopped", "\"hooks_restored\":0,\"active_calls\":0");
    initialized = false; log_file.close(); return 1;
}
BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
    // No initialization, waits, GDI, loader calls or logging under loader lock.
    if (reason == DLL_PROCESS_DETACH) log_file.close();
    return TRUE;
}
