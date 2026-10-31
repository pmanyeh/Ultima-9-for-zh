#pragma once
#include <cstdint>

namespace u9cht {
inline constexpr wchar_t ExeHash[] = L"83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545";
inline constexpr wchar_t WrapperHash[] = L"f045795c50eb1e5bf93853a32ca00ebe58d47b94da61842558aeecd3f755a502";
inline constexpr wchar_t TextHash[] = L"378d0bf949a832ea564546159a7a2596d9d5a2512d7ace7441e52550b33e9fa0";
inline constexpr wchar_t FontHash[] = L"dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4";
inline constexpr uintptr_t GameBase = 0x400000;
inline constexpr uintptr_t WrapperBase = 0x18000000;
inline constexpr char RuntimeName[] = "U9ChtRuntime/0.1.0-p5.1";
}
