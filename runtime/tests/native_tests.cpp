#include "platform.h"
#include "version_manifest.h"
#include <iostream>
#include <algorithm>

int wmain(int argc, wchar_t** argv) {
    if (argc == 3 && std::wstring(argv[1]) == L"--child") {
        u9cht::Handle event(OpenEventW(EVENT_MODIFY_STATE, FALSE, argv[2]));
        return event && SetEvent(event.get()) ? 0 : 1;
    }
    try {
        using namespace u9cht;
        Config c;
        require(valid_protocol(c), "valid protocol rejected");
        c.protocol++; require(!valid_protocol(c), "wrong protocol accepted"); c.protocol--;
        c.size--; require(!valid_protocol(c), "wrong ABI size accepted"); c.size++;
        c.flags = 8; require(!valid_protocol(c), "unknown flags accepted"); c.flags = 0;
        c.mode = static_cast<Mode>(99); require(!valid_protocol(c), "unknown mode accepted");
        require(sha256_bytes("abc", 3) == L"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "SHA-256 known vector failed");
        require(GameBase == 0x400000 && WrapperBase == 0x18000000, "baseline manifest changed");
        char16_t invalid[PathCapacity]; std::fill(std::begin(invalid), std::end(invalid), u'x');
        bool rejected = false;
        try { (void)config_path(invalid); } catch (...) { rejected = true; }
        require(rejected, "unterminated path accepted");
        // Asset-free process integration: the loader worker must complete while
        // the fixture's actual primary entry point remains suspended.
        const auto event_name = L"Local\\U9ChtFixture-" + std::to_wstring(GetCurrentProcessId());
        Handle event(CreateEventW(nullptr, TRUE, FALSE, event_name.c_str()));
        require(static_cast<bool>(event), "fixture event creation failed");
        auto executable = module_path(nullptr);
        auto command = L"\"" + executable + L"\" --child " + event_name;
        STARTUPINFOW si{}; si.cb = sizeof(si); PROCESS_INFORMATION pi{};
        require(CreateProcessW(executable.c_str(), command.data(), nullptr, nullptr, FALSE,
                              CREATE_SUSPENDED | CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi),
                "fixture process creation failed");
        Handle process(pi.hProcess), primary(pi.hThread);
        try {
            initialize_loader(process.get());
            require(WaitForSingleObject(event.get(), 0) == WAIT_TIMEOUT,
                    "loader worker prematurely executed fixture primary");
            require(ResumeThread(primary.get()) == 1, "fixture suspend count changed");
            require(WaitForSingleObject(event.get(), 10000) == WAIT_OBJECT_0,
                    "fixture primary failed after explicit resume");
            require(WaitForSingleObject(process.get(), 10000) == WAIT_OBJECT_0, "fixture did not exit");
            DWORD code = 1; require(GetExitCodeProcess(process.get(), &code) && code == 0, "fixture failed");
        } catch (...) { TerminateProcess(process.get(), 1); WaitForSingleObject(process.get(), 10000); throw; }
        std::cout << "PASS: 8 bootstrap checks + loader/primary isolation integration\n"; return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
