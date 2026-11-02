#pragma once
#include "identity.h"

namespace u9cht {
struct PaintScope {
    uint64_t generation = 0;
    uintptr_t owner = 0, widget = 0, caller = 0;
    bool operator==(const PaintScope&) const = default;
};
struct TextRun {
    uint32_t plan = 0, drawn = 0;
    uint64_t identity = 0;
    uintptr_t source = 0;
};
// Measured native response widget: one cache repaint can draw several labels.
// A new identity is admitted only before sealing and inside this exact paint
// scope/caller. Other routes retain the historical single-identity contract.
class RasterRuns {
    PaintScope scope_{};
    std::array<TextRun,8> runs_{};
    uint32_t count_ = 0;
    bool sealed_ = false;
public:
    static constexpr uintptr_t SharedCaller = 0x5C4E6D;
    TextRun* acquire(PaintScope scope, uint32_t plan, uint64_t identity, uintptr_t source) noexcept {
        if (sealed_ || plan >= MaxPlans || !identity || !source) return nullptr;
        if (count_ && scope != scope_) return nullptr;
        for (uint32_t i = 0; i < count_; ++i)
            if (runs_[i].plan == plan && runs_[i].identity == identity) return &runs_[i];
        if (count_ && (!scope.generation || !scope.owner || !scope.widget || scope.caller != SharedCaller))
            return nullptr;
        if (count_ == runs_.size()) return nullptr;
        if (!count_) scope_ = scope;
        auto& run = runs_[count_++]; run = {plan,0,identity,source}; return &run;
    }
    uint32_t size() const noexcept { return count_; }
    uint32_t index(const TextRun* run) const noexcept { return uint32_t(run-runs_.data()); }
    std::span<const TextRun> values() const noexcept { return {runs_.data(),count_}; }
    const TextRun& at(uint32_t index) const noexcept { return runs_[index]; }
    bool first_plan(uint32_t index) const noexcept {
        for (uint32_t i = 0; i < index; ++i) if (runs_[i].plan == runs_[index].plan) return false;
        return true;
    }
    void seal() noexcept { sealed_ = true; }
};
}
