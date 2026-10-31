#pragma once
#include <windows.h>
#include <filesystem>
#include <string>
#include <vector>
#include <atomic>
#include "protocol.h"

namespace u9cht {
class Handle {
    HANDLE value_ = nullptr;
public:
    Handle() = default;
    explicit Handle(HANDLE h) : value_(h) {}
    ~Handle() { reset(); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    Handle(Handle&& h) noexcept : value_(h.release()) {}
    Handle& operator=(Handle&& h) noexcept { if (this != &h) reset(h.release()); return *this; }
    HANDLE get() const { return value_; }
    explicit operator bool() const { return value_ && value_ != INVALID_HANDLE_VALUE; }
    HANDLE release() { auto h = value_; value_ = nullptr; return h; }
    void reset(HANDLE h = nullptr) { if (*this) CloseHandle(value_); value_ = h; }
};
std::wstring sha256(const std::filesystem::path& path);
std::wstring sha256_bytes(const void* data, size_t size);
std::string utf8(const std::wstring& text);
std::wstring module_path(HMODULE module);
void require(bool condition, const char* message);
void initialize_loader(HANDLE process);
void copy_path(char16_t (&out)[PathCapacity], const std::filesystem::path& path);
std::filesystem::path config_path(const char16_t (&path)[PathCapacity]);
class Logger {
    Handle file_;
    mutable std::atomic<uint32_t> failures_{0};
public:
    void open(const std::filesystem::path& path, bool create);
    void event(const char* event, const std::string& fields = "") const noexcept;
    uint32_t failures() const noexcept { return failures_.load(); }
    void close() { file_.reset(); }
};
}
