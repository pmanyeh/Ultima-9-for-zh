#pragma once
// P11 movie player: MPEG-1 PS (video + MP2) via pl_mpeg, GDI presentation, waveOut audio, Chinese subtitles.
// Used by the standalone review tool (U9ChtMovieViewer) and by the runtime's FilterGraph replacement.
#include "subtitles.h"
#include <windows.h>
#include <mmsystem.h>
#include <atomic>
#include <deque>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

typedef struct plm_t plm_t;

namespace u9cht {
struct MovieStyle {
    std::wstring font_family = L"Microsoft JhengHei";
    uint32_t subtitle_px_at_480 = 26;  // subtitle em at a 480-pixel tall window, scaled with the window
    bool review = false;               // review tool: time/cue line and the reference (English) cues
};

class MoviePlayer {
public:
    MoviePlayer() = default;
    MoviePlayer(const MoviePlayer&) = delete;
    MoviePlayer& operator=(const MoviePlayer&) = delete;
    ~MoviePlayer();

    // Opens the file; `stem` selects the cues. Returns false with `error` set.
    bool open(const std::wstring& path, std::string& error);
    void set_cues(std::vector<SubtitleCue> cues);
    void set_reference(std::vector<SubtitleCue> cues);
    void set_style(const MovieStyle& style) { style_ = style; }
    // Creates the presentation window: a top-level window (parent null) or an input-transparent child.
    bool create_window(HWND parent, int x, int y, int w, int h, const wchar_t* title = L"");
    void set_position(int x, int y, int w, int h);
    void set_visible(bool visible);
    void set_notify(HWND hwnd, UINT message, LONG_PTR param) { notify_hwnd_ = hwnd; notify_message_ = message; notify_param_ = param; }
    void set_key_handler(std::function<void(WPARAM)> handler) { key_handler_ = std::move(handler); }

    void play();
    void pause(bool paused);
    bool paused() const noexcept { return paused_.load(); }
    void stop();                       // stops decoding and audio; the window stays until destroy_window()
    void seek(double seconds);
    void destroy_window();

    bool finished() const noexcept { return finished_.load(); }
    double time() const noexcept { return time_.load(); }
    double duration() const noexcept { return duration_; }
    int video_width() const noexcept { return width_; }
    int video_height() const noexcept { return height_; }
    const std::string& stem() const noexcept { return stem_; }
    HWND window() const noexcept { return hwnd_; }
    const std::vector<SubtitleCue>& cues() const noexcept { return cues_; }

private:
    static LRESULT CALLBACK proc(HWND, UINT, WPARAM, LPARAM);
    void paint(HDC dc);
    void run();
    void open_audio();
    void close_audio();
    void reclaim_audio(bool all);
    static void on_video(plm_t*, void* frame, void* self);
    static void on_audio(plm_t*, void* samples, void* self);

    plm_t* plm_ = nullptr;
    std::mutex decoder_;               // plm_ and the audio queue
    std::wstring path_;
    std::string stem_;
    int width_ = 0, height_ = 0, samplerate_ = 0;
    double duration_ = 0;
    std::vector<SubtitleCue> cues_, reference_;
    MovieStyle style_;

    HWND hwnd_ = nullptr;
    bool child_ = false;
    HWND notify_hwnd_ = nullptr;
    UINT notify_message_ = 0;
    LONG_PTR notify_param_ = 0;
    std::function<void(WPARAM)> key_handler_;

    std::mutex frame_lock_;
    std::vector<uint32_t> frame_, staging_;
    bool has_frame_ = false;

    HWAVEOUT wave_ = nullptr;
    struct Block { WAVEHDR header{}; std::vector<int16_t> data; };
    std::deque<Block*> blocks_;

    std::thread thread_;
    std::atomic<bool> running_{false}, paused_{false}, finished_{false}, notified_{false};
    std::atomic<double> time_{0};
};
}
