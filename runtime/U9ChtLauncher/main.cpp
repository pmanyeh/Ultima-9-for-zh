#include "platform.h"
#include "version_manifest.h"
#include <tlhelp32.h>
#include <iostream>
#include <map>

using namespace u9cht;
namespace {
uintptr_t remote_module(DWORD pid, const std::wstring& name, const std::filesystem::path* expected = nullptr) {
    Handle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid));
    require(static_cast<bool>(snapshot), "remote module snapshot failed");
    MODULEENTRY32W entry{}; entry.dwSize = sizeof(entry);
    if (Module32FirstW(snapshot.get(), &entry)) do {
        if (_wcsicmp(entry.szModule, name.c_str()) == 0) {
            if (expected) require(std::filesystem::equivalent(entry.szExePath, *expected), "remote module path mismatch");
            return reinterpret_cast<uintptr_t>(entry.modBaseAddr);
        }
    } while (Module32NextW(snapshot.get(), &entry));
    return 0;
}
uintptr_t remote_system_export(DWORD pid, const char* name) {
    auto address = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), name);
    require(address != nullptr, "system export unavailable");
    HMODULE owner = nullptr;
    require(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                              reinterpret_cast<LPCWSTR>(address), &owner), "system export owner unavailable");
    const auto path = std::filesystem::path(module_path(owner));
    auto base = remote_module(pid, path.filename(), &path);
    require(base != 0, "remote system module unavailable");
    return base + reinterpret_cast<uintptr_t>(address) - reinterpret_cast<uintptr_t>(owner);
}
DWORD remote_call(HANDLE process, uintptr_t entry, void* parameter) {
    Handle thread(CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(entry),
                                      parameter, 0, nullptr));
    require(static_cast<bool>(thread), "bootstrap remote thread failed");
    require(WaitForSingleObject(thread.get(), 30000) == WAIT_OBJECT_0, "bootstrap thread timeout");
    DWORD result = 0; require(GetExitCodeThread(thread.get(), &result), "bootstrap return unavailable");
    return result;
}
void write_remote(HANDLE process, void* address, const void* data, size_t size) {
    SIZE_T actual = 0;
    require(WriteProcessMemory(process, address, data, size, &actual) && actual == size,
            "bootstrap configuration write failed");
}
uintptr_t export_rva(const std::filesystem::path& dll, const char* name) {
    // Map only to resolve an export RVA. No local DLL code or DllMain executes.
    auto module = LoadLibraryExW(dll.c_str(), nullptr, DONT_RESOLVE_DLL_REFERENCES);
    require(module != nullptr, "runtime export map failed");
    auto entry = GetProcAddress(module, name);
    auto result = entry ? reinterpret_cast<uintptr_t>(entry) - reinterpret_cast<uintptr_t>(module) : 0;
    FreeLibrary(module); require(result != 0, "runtime export missing"); return result;
}
}
int wmain(int argc, wchar_t** argv) {
    Logger log;
    Handle process, primary;
    DWORD pid = 0;
    void* remote_data = nullptr;
    bool resumed = false;
    try {
        std::map<std::wstring, std::wstring> options;
        bool fail = false, validate = false, unload = false;
        for (int i = 1; i < argc; ++i) {
            std::wstring key(argv[i]);
            if (key == L"--force-init-failure") fail = true;
            else if (key == L"--validate-only") validate = true;
            else if (key == L"--verify-unload") unload = true;
            else {
                require(i + 1 < argc && (key == L"--game-dir" || key == L"--runtime" || key == L"--log" ||
                         key == L"--mode" || key == L"--font" || key == L"--allowlist"), "unknown/missing argument");
                require(options.emplace(key, argv[++i]).second, "duplicate option");
            }
        }
        require(options.count(L"--game-dir") && options.count(L"--log"), "--game-dir and fresh --log are required");
        const auto game = std::filesystem::canonical(options[L"--game-dir"]);
        const auto dll = std::filesystem::canonical(options.count(L"--runtime") ? options[L"--runtime"] :
                         (std::filesystem::path(module_path(nullptr)).parent_path() / L"U9ChtRuntime.dll").wstring());
        const auto log_path = std::filesystem::absolute(options[L"--log"]);
        require(std::filesystem::is_directory(log_path.parent_path()), "log directory must exist");
        require(sha256(game / L"u9.exe") == ExeHash && sha256(game / L"ddraw.dll") == WrapperHash,
                "STOP: executable/wrapper baseline mismatch");
        Config config;
        if (options.count(L"--mode")) {
            auto mode = options[L"--mode"];
            require(mode == L"bootstrap" || mode == L"observe" || mode == L"render", "unsupported mode");
            config.mode = mode == L"bootstrap" ? Mode::Bootstrap : mode == L"observe" ? Mode::Observe : Mode::Render;
        }
        copy_path(config.game_dir, game); copy_path(config.log_path, log_path);
        if (options.count(L"--font")) copy_path(config.font_path, std::filesystem::canonical(options[L"--font"]));
        if (options.count(L"--allowlist")) copy_path(config.allowlist_path, std::filesystem::canonical(options[L"--allowlist"]));
        config.flags = fail ? ForceFailure : 0;
        const auto init_rva = export_rva(dll, "U9ChtInitialize");
        const auto shutdown_rva = export_rva(dll, "U9ChtShutdown");
        log.open(log_path, true);
        log.event("launcher_validated", "\"runtime_version\":"+std::to_string(RuntimeVersion)+
            ",\"bits\":32,\"debugger\":false,\"runtime_sha256\":\""+utf8(sha256(dll))+"\"");
        if (validate) { log.event("validation_only"); return 0; }
        STARTUPINFOW startup{}; startup.cb = sizeof(startup);
        PROCESS_INFORMATION info{};
        require(CreateProcessW((game / L"u9.exe").c_str(), nullptr, nullptr, nullptr, FALSE, CREATE_SUSPENDED,
                                nullptr, game.c_str(), &startup, &info), "suspended game creation failed");
        process.reset(info.hProcess); primary.reset(info.hThread); pid = info.dwProcessId;
        log.event("game_created_suspended", "\"game_pid\":" + std::to_string(pid));
        initialize_loader(process.get());
        log.event("loader_initialized_primary_suspended");
        const auto dll_text = dll.wstring();
        const auto data_size = sizeof(Config) + (dll_text.size() + 1) * sizeof(wchar_t);
        remote_data = VirtualAllocEx(process.get(), nullptr, data_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        require(remote_data != nullptr, "bootstrap allocation failed");
        auto remote_path = static_cast<unsigned char*>(remote_data) + sizeof(Config);
        write_remote(process.get(), remote_path, dll_text.c_str(), (dll_text.size() + 1) * sizeof(wchar_t));
        const auto runtime = remote_call(process.get(), remote_system_export(pid, "LoadLibraryW"), remote_path);
        require(runtime && remote_module(pid, dll.filename(), &dll) == runtime, "runtime load/module validation failed");
        write_remote(process.get(), remote_data, &config, sizeof(config));
        auto ready = remote_call(process.get(), runtime + init_rva, remote_data);
        SIZE_T actual = 0;
        require(ReadProcessMemory(process.get(), remote_data, &config, sizeof(config), &actual) && actual == sizeof(config),
                "READY/FAIL handshake read failed");
        if (!ready || !valid_protocol(config) || config.state != State::Ready || config.process_id != pid) {
            log.event("handshake_fail", "\"error\":" + std::to_string(static_cast<uint32_t>(config.error)));
            require(remote_call(process.get(), runtime + shutdown_rva, nullptr) == 1, "initialization rollback failed");
            require(remote_call(process.get(), remote_system_export(pid, "FreeLibrary"), reinterpret_cast<void*>(runtime)),
                    "initialization unload failed");
            require(!remote_module(pid, dll.filename()), "runtime remained loaded after rollback");
            require(VirtualFreeEx(process.get(), remote_data, 0, MEM_RELEASE), "rollback configuration release failed");
            remote_data = nullptr;
            log.event("initialization_rollback_verified", "\"primary_resumed\":false,\"owned_allocation_released\":true");
            throw std::runtime_error("runtime initialization reported FAIL; game was not resumed");
        }
        log.event("handshake_ready", "\"game_pid\":" + std::to_string(pid) +
                   ",\"image_base\":" + std::to_string(config.image_base) +
                   ",\"wrapper_base\":" + std::to_string(config.wrapper_base));
        if (unload) {
            require(config.mode == Mode::Bootstrap, "hot unload is only valid for inert bootstrap");
            require(remote_call(process.get(), runtime + shutdown_rva, nullptr) == 1, "bootstrap shutdown failed");
            require(remote_call(process.get(), remote_system_export(pid, "FreeLibrary"), reinterpret_cast<void*>(runtime)),
                    "bootstrap unload failed");
            require(!remote_module(pid, dll.filename()), "bootstrap unload verification failed");
            log.event("bootstrap_unload_verified");
        }
        require(VirtualFreeEx(process.get(), remote_data, 0, MEM_RELEASE), "bootstrap allocation release failed");
        remote_data = nullptr;
        require(ResumeThread(primary.get()) == 1, "primary resume failed"); resumed = true;
        primary.reset(); log.event("game_resumed", "\"game_pid\":" + std::to_string(pid));
        std::cout << "READY game_pid=" << pid << " debugger=false\n" << std::flush;
        require(WaitForSingleObject(process.get(), INFINITE) == WAIT_OBJECT_0, "game process wait failed");
        DWORD code = 0; require(GetExitCodeProcess(process.get(), &code), "game exit status unavailable");
        log.event("game_exited", "\"exit_code\":" + std::to_string(code));
        std::cout << "EXIT game_pid=" << pid << " code=" << code << '\n';
        return code == 0 ? 0 : 3;
    } catch (const std::exception& error) {
        // The only process ever terminated here is this launcher's own child.
        if (process && !resumed) { TerminateProcess(process.get(), 2); WaitForSingleObject(process.get(), 10000); }
        log.event("launcher_fail", "\"primary_resumed\":" + std::string(resumed ? "true" : "false"));
        std::cerr << error.what() << '\n';
        return 2;
    }
}
