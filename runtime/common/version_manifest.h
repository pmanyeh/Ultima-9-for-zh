#pragma once
#include <cstdint>
#include <string>
namespace u9cht {
inline constexpr wchar_t ExeHash[] = L"83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545";
// The Steam release (EA, app 3067560, 2026) is the GOG executable byte for byte plus an EA Authenticode signature:
// only the PE checksum, the security directory entry and the appended certificate differ (CONFIRMED 2026-11-12),
// none of which is mapped, so the loaded image and every hooked address are identical.
inline constexpr wchar_t SteamExeHash[] = L"339a5ba8683546363ab8b95c53d3e980dfbd959afe8719b11f2666c4dbd0e152";
inline bool known_exe(const std::wstring& hash) { return hash == ExeHash || hash == SteamExeHash; }
// "GOG", "Steam" or "" for an unsupported executable.
inline const wchar_t* exe_edition(const std::wstring& hash) { return hash == ExeHash ? L"GOG" : hash == SteamExeHash ? L"Steam" : L""; }
inline constexpr wchar_t WrapperHash[] = L"f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502";
inline constexpr wchar_t TextHash[] = L"378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0";
inline constexpr uintptr_t GameBase = 0x400000;
inline constexpr uintptr_t WrapperBase = 0x18000000;
inline constexpr char RuntimeName[] = "U9ChtRuntime/0.2.43-p11";
}
