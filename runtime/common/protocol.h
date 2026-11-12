#pragma once
#include <cstdint>
#include <cstddef>
#include <type_traits>

namespace u9cht {
inline constexpr uint32_t ProtocolMagic = 0x31484355;
inline constexpr uint32_t ProtocolVersion = 3;
inline constexpr uint32_t RuntimeVersion = 0x00020000;
enum class Mode : uint32_t { Bootstrap, Observe, Render };
enum class State : uint32_t { Empty, Initializing, Ready, Fail, Stopped };
enum class Error : uint32_t {
    None, Protocol, Version, Baseline, ImageBase, WrapperBase, Configuration,
    ForcedFailure, UnsupportedMode, Initialization, Rollback
};
inline constexpr uint32_t ForceFailure = 1;
inline constexpr size_t PathCapacity = 1024;
// Protocol 3: player-selectable enhancements ([features] in the settings INI, the front page's switches).
inline constexpr uint32_t FeatureHoverNames = 1, FeatureWheelPages = 2, FeatureWheelZoom = 4,
                          FeatureMovieSubtitles = 8, FeatureInputProbe = 16;
inline constexpr uint32_t AllFeatures = 31;
inline constexpr uint32_t DefaultFeatures = FeatureHoverNames | FeatureWheelPages | FeatureWheelZoom | FeatureMovieSubtitles;
inline constexpr uint32_t MinHoverDelayMs = 100, MaxHoverDelayMs = 2000, DefaultHoverDelayMs = 250;
// Only fixed-width integers and UTF-16 arrays cross the x86 process boundary.
struct Config {
    uint32_t magic = ProtocolMagic;
    uint32_t size = sizeof(Config);
    uint32_t protocol = ProtocolVersion;
    uint32_t runtime_version = RuntimeVersion;
    Mode mode = Mode::Bootstrap;
    uint32_t flags = 0;
    State state = State::Empty;
    Error error = Error::None;
    uint32_t process_id = 0;
    uint32_t image_base = 0;
    uint32_t wrapper_base = 0;
    uint32_t hooks_installed = 0;
    char16_t game_dir[PathCapacity]{};
    char16_t log_path[PathCapacity]{};
    char16_t font_path[PathCapacity]{};
    char16_t allowlist_path[PathCapacity]{};
    // P9-2 player settings ([journal] in the settings INI); validated by the launcher and the runtime.
    uint32_t journal_letter_spacing = 0;
    uint32_t journal_line_spacing = 0;
    uint32_t features = DefaultFeatures;
    uint32_t hover_delay_ms = DefaultHoverDelayMs;
};
inline constexpr uint32_t MaxJournalLetterSpacing = 8;
inline constexpr uint32_t MaxJournalLineSpacing = 16;
static_assert(sizeof(void*) == 4, "runtime ABI is x86 only");
static_assert(sizeof(char16_t) == 2 && sizeof(wchar_t) == 2);
static_assert(std::is_trivially_copyable_v<Config>);
static_assert(sizeof(Config) == 8256);
inline bool valid_protocol(const Config& c) {
    return c.magic == ProtocolMagic && c.size == sizeof(Config) &&
           c.protocol == ProtocolVersion && c.runtime_version == RuntimeVersion &&
           c.mode <= Mode::Render && (c.flags & ~ForceFailure) == 0 &&
           c.journal_letter_spacing <= MaxJournalLetterSpacing && c.journal_line_spacing <= MaxJournalLineSpacing &&
           (c.features & ~AllFeatures) == 0 && c.hover_delay_ms >= MinHoverDelayMs && c.hover_delay_ms <= MaxHoverDelayMs;
}
}
