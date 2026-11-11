#pragma once
// P11: replacement for the FilterGraph object u9.exe creates for its movies (CONFIRMED static, 0x584A70..0x5851A0):
// IGraphBuilder::RenderFile, IMediaControl::Run/Stop, IMediaEventEx::SetNotifyWindow/GetEvent/FreeEventParams,
// IVideoWindow::put_Owner/put_WindowStyle/SetWindowPosition/put_Visible. Every other method returns E_NOTIMPL.
#include "movie_player.h"
#include <dshow.h>

namespace u9cht {
struct MovieGraphConfig {
    std::vector<SubtitleCue> cues;
    MovieStyle style;
};
// Creates the graph object and returns the requested interface (S_OK) or E_NOINTERFACE.
HRESULT create_movie_graph(const MovieGraphConfig& config, REFIID riid, void** out);
// Counters for the runtime log.
struct MovieGraphStats { long created = 0, rendered = 0, render_failures = 0, completed = 0, stopped = 0; };
MovieGraphStats movie_graph_stats() noexcept;
}
