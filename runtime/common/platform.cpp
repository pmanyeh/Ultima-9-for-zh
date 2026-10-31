#include "platform.h"
#include <bcrypt.h>
#include <array>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace u9cht {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
namespace {
class Hash {
    BCRYPT_ALG_HANDLE algorithm_ = nullptr;
    BCRYPT_HASH_HANDLE hash_ = nullptr;
    std::vector<unsigned char> object_;
public:
    Hash() {
        require(BCryptOpenAlgorithmProvider(&algorithm_, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0,
                "SHA-256 provider unavailable");
        DWORD length = 0, actual = 0;
        if (BCryptGetProperty(algorithm_, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&length),
                              sizeof(length), &actual, 0) < 0) {
            BCryptCloseAlgorithmProvider(algorithm_, 0); algorithm_ = nullptr;
            throw std::runtime_error("SHA-256 object size unavailable");
        }
        object_.resize(length);
        if (BCryptCreateHash(algorithm_, &hash_, object_.data(), length, nullptr, 0, 0) < 0) {
            BCryptCloseAlgorithmProvider(algorithm_, 0); algorithm_ = nullptr;
            throw std::runtime_error("SHA-256 initialization failed");
        }
    }
    ~Hash() {
        if (hash_) BCryptDestroyHash(hash_);
        if (algorithm_) BCryptCloseAlgorithmProvider(algorithm_, 0);
    }
    void add(const void* p, size_t n) {
        require(n <= std::numeric_limits<ULONG>::max(), "hash input too large");
        require(BCryptHashData(hash_, reinterpret_cast<PUCHAR>(const_cast<void*>(p)),
                               static_cast<ULONG>(n), 0) >= 0, "SHA-256 update failed");
    }
    std::wstring finish() {
        std::array<unsigned char, 32> bytes{};
        require(BCryptFinishHash(hash_, bytes.data(), static_cast<ULONG>(bytes.size()), 0) >= 0,
                "SHA-256 finalization failed");
        constexpr wchar_t hex[] = L"0123456789abcdef";
        std::wstring result; result.reserve(64);
        for (auto b : bytes) { result += hex[b >> 4]; result += hex[b & 15]; }
        return result;
    }
};
}
std::wstring sha256(const std::filesystem::path& path) {
    Handle h(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                          FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, nullptr));
    require(static_cast<bool>(h), "cannot open baseline file read-only");
    Hash hash; std::array<unsigned char, 65536> buffer{};
    for (;;) {
        DWORD count = 0;
        require(ReadFile(h.get(), buffer.data(), static_cast<DWORD>(buffer.size()), &count, nullptr),
                "baseline read failed");
        if (!count) break;
        hash.add(buffer.data(), count);
    }
    return hash.finish();
}
std::wstring sha256_bytes(const void* data, size_t size) { Hash h; h.add(data, size); return h.finish(); }
void initialize_loader(HANDLE process) {
    // A new suspended process has not populated its loader module lists. A
    // standard remote thread runs process/DLL loader initialization before its
    // user thread procedure. This own x86 stdcall procedure only returns zero.
    // It does not enter the game's suspended primary thread or alter its EIP.
    constexpr unsigned char worker[] = {0x33, 0xC0, 0xC2, 0x04, 0x00};
    auto* memory = VirtualAllocEx(process, nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    require(memory != nullptr, "loader-worker allocation failed");
    bool running = false;
    try {
        SIZE_T actual = 0; DWORD old = 0;
        require(WriteProcessMemory(process, memory, worker, sizeof(worker), &actual) && actual == sizeof(worker),
                "loader-worker write failed");
        require(VirtualProtectEx(process, memory, 4096, PAGE_EXECUTE_READ, &old), "loader-worker RX protection failed");
        require(FlushInstructionCache(process, memory, sizeof(worker)), "loader-worker cache flush failed");
        Handle thread(CreateRemoteThread(process, nullptr, 0,
                        reinterpret_cast<LPTHREAD_START_ROUTINE>(memory), nullptr, 0, nullptr));
        require(static_cast<bool>(thread), "loader-worker thread failed"); running = true;
        require(WaitForSingleObject(thread.get(), 30000) == WAIT_OBJECT_0, "loader-worker timeout");
        running = false; DWORD code = 1;
        require(GetExitCodeThread(thread.get(), &code) && code == 0, "loader-worker did not return normally");
        require(VirtualFreeEx(process, memory, 0, MEM_RELEASE), "loader-worker release failed");
    } catch (...) {
        // Never free code while a thread may execute it. The owner aborts its
        // own unresumed child on failure; OS process teardown releases the page.
        if (!running) VirtualFreeEx(process, memory, 0, MEM_RELEASE);
        throw;
    }
}
std::string utf8(const std::wstring& text) {
    if (text.empty()) return {};
    const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
                                        static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    require(size > 0, "invalid UTF-16 diagnostic");
    std::string result(size, '\0');
    require(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()),
                                result.data(), size, nullptr, nullptr) == size, "UTF-8 conversion failed");
    return result;
}
std::wstring module_path(HMODULE module) {
    std::wstring result(32768, L'\0');
    const DWORD size = GetModuleFileNameW(module, result.data(), static_cast<DWORD>(result.size()));
    require(size > 0 && size < result.size(), "module path unavailable");
    result.resize(size); return result;
}
void copy_path(char16_t (&out)[PathCapacity], const std::filesystem::path& path) {
    const auto text = path.wstring(); require(text.size() < PathCapacity, "configuration path too long");
    std::copy(text.begin(), text.end(), out); out[text.size()] = 0;
}
std::filesystem::path config_path(const char16_t (&path)[PathCapacity]) {
    const auto end = std::find(std::begin(path), std::end(path), u'\0');
    require(end != std::end(path) && end != std::begin(path), "unterminated/empty configuration path");
    return std::wstring(reinterpret_cast<const wchar_t*>(path), static_cast<size_t>(end - std::begin(path)));
}
void Logger::open(const std::filesystem::path& path, bool create) {
    file_.reset(CreateFileW(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             nullptr, create ? CREATE_NEW : OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
    require(static_cast<bool>(file_), "cannot open fresh local log");
}
void Logger::event(const char* name, const std::string& fields) const noexcept {
    if (!file_) return;
    try {
        const auto line = std::string("{\"event\":\"") + name + "\",\"pid\":" +
            std::to_string(GetCurrentProcessId()) + ",\"tick_ms\":" + std::to_string(GetTickCount64()) +
            (fields.empty() ? "" : "," + fields) + "}\n";
        DWORD written = 0;
        WriteFile(file_.get(), line.data(), static_cast<DWORD>(line.size()), &written, nullptr);
    } catch (...) { /* Diagnostics must never throw across an engine boundary. */ }
}
}
