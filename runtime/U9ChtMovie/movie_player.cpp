#include "movie_player.h"
#include <cstdio>
#include "pl_mpeg.h"
#include <algorithm>
#include <cmath>

namespace u9cht {
namespace {
constexpr wchar_t ClassName[] = L"U9ChtMovie";
constexpr double AudioLead = 0.15;

double now_seconds() {
    LARGE_INTEGER f, c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return double(c.QuadPart)/double(f.QuadPart);
}
void register_class() {
    static bool done = false;
    if (done) return;
    WNDCLASSEXW wc{sizeof wc};
    wc.style = CS_HREDRAW|CS_VREDRAW;
    wc.lpfnWndProc = [](HWND h, UINT m, WPARAM w, LPARAM l) -> LRESULT { return DefWindowProcW(h,m,w,l); };
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.hCursor = LoadCursorW(nullptr,IDC_ARROW);
    wc.lpszClassName = ClassName;
    RegisterClassExW(&wc);
    done = true;
}
// White text with a dark outline: the outline is the text drawn at every offset within `ring`.
void outlined_text(HDC dc, const std::u16string& text, RECT box, UINT format, int ring, COLORREF fill) {
    const auto* s = reinterpret_cast<const wchar_t*>(text.c_str());
    SetBkMode(dc,TRANSPARENT);
    SetTextColor(dc,RGB(0,0,0));
    for (int dy = -ring; dy <= ring; ++dy) for (int dx = -ring; dx <= ring; ++dx) {
        if (!dx && !dy) continue;
        RECT r = box; OffsetRect(&r,dx,dy);
        DrawTextW(dc,s,-1,&r,format);
    }
    SetTextColor(dc,fill);
    DrawTextW(dc,s,-1,&box,format);
}
}

MoviePlayer::~MoviePlayer() {
    stop();
    destroy_window();
    free_subtitle();
    if (plm_) { plm_destroy(plm_); plm_ = nullptr; }
}

bool MoviePlayer::open(const std::wstring& path, std::string& error) {
    FILE* f = nullptr;
    if (_wfopen_s(&f,path.c_str(),L"rb") || !f) { error = "cannot open movie file"; return false; }
    plm_ = plm_create_with_file(f,1);
    if (!plm_) { error = "not an MPEG-1 program stream"; return false; }
    if (!plm_probe(plm_,5000*1024) || !plm_get_num_video_streams(plm_)) { error = "no MPEG-1 video stream"; return false; }
    path_ = path;
    stem_ = movie_stem(std::u16string(reinterpret_cast<const char16_t*>(path.c_str())));
    width_ = plm_get_width(plm_); height_ = plm_get_height(plm_);
    samplerate_ = plm_get_samplerate(plm_);
    duration_ = plm_get_duration(plm_);
    plm_set_audio_enabled(plm_,plm_get_num_audio_streams(plm_) > 0);
    plm_set_audio_lead_time(plm_,AudioLead);
    plm_set_loop(plm_,0);
    frame_.assign(size_t(width_)*height_,0);
    staging_.assign(size_t(width_)*height_,0);
    plm_set_video_decode_callback(plm_,[](plm_t* p, plm_frame_t* f, void* u) { on_video(p,f,u); },this);
    plm_set_audio_decode_callback(plm_,[](plm_t* p, plm_samples_t* s, void* u) { on_audio(p,s,u); },this);
    return true;
}

void MoviePlayer::set_cues(std::vector<SubtitleCue> cues) { std::lock_guard l(frame_lock_); cues_ = std::move(cues); }
void MoviePlayer::set_reference(std::vector<SubtitleCue> cues) { std::lock_guard l(frame_lock_); reference_ = std::move(cues); }

bool MoviePlayer::create_window(HWND parent, int x, int y, int w, int h, const wchar_t* title) {
    register_class();
    child_ = parent != nullptr;
    const DWORD style = child_ ? (WS_CHILD|WS_VISIBLE|WS_DISABLED|WS_CLIPSIBLINGS) : (WS_OVERLAPPEDWINDOW|WS_VISIBLE);
    RECT r{x,y,x+w,y+h};
    if (!child_) AdjustWindowRect(&r,style,FALSE);
    hwnd_ = CreateWindowExW(child_ ? WS_EX_NOPARENTNOTIFY : 0,ClassName,title,style,
        child_ ? x : CW_USEDEFAULT, child_ ? y : CW_USEDEFAULT, r.right-r.left, r.bottom-r.top,
        parent,nullptr,GetModuleHandleW(nullptr),nullptr);
    if (!hwnd_) return false;
    SetWindowLongPtrW(hwnd_,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(this));
    SetWindowLongPtrW(hwnd_,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(&MoviePlayer::proc));
    return true;
}
void MoviePlayer::set_position(int x, int y, int w, int h) {
    if (hwnd_) SetWindowPos(hwnd_,HWND_TOP,x,y,w,h,SWP_NOACTIVATE);
}
void MoviePlayer::set_visible(bool visible) { if (hwnd_) ShowWindow(hwnd_,visible ? SW_SHOWNA : SW_HIDE); }
void MoviePlayer::destroy_window() {
    if (hwnd_) { SetWindowLongPtrW(hwnd_,GWLP_USERDATA,0); DestroyWindow(hwnd_); hwnd_ = nullptr; }
}

LRESULT CALLBACK MoviePlayer::proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    auto* self = reinterpret_cast<MoviePlayer*>(GetWindowLongPtrW(h,GWLP_USERDATA));
    switch (m) {
    case WM_NCHITTEST:
        if (self && self->child_) return HTTRANSPARENT; // the game keeps mouse and keyboard
        break;
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: {
        PAINTSTRUCT ps; HDC dc = BeginPaint(h,&ps);
        if (self) self->paint(dc);
        EndPaint(h,&ps);
        return 0;
    }
    case WM_KEYDOWN:
        if (self && self->key_handler_) { self->key_handler_(w); return 0; }
        break;
    case WM_CLOSE:
        if (self && !self->child_) { PostQuitMessage(0); return 0; }
        break;
    }
    return DefWindowProcW(h,m,w,l);
}

void MoviePlayer::free_subtitle() {
    if (sub_bitmap_) { DeleteObject(sub_bitmap_); sub_bitmap_ = nullptr; }
    sub_rect_ = RECT{};
}

// Renders the outlined subtitle once. Transparent pixels use SubtitleKey (near-black); antialiased edges blend
// toward the black outline, so any non-key fringe pixel is near-black and reads as part of the outline.
void MoviePlayer::render_subtitle(HDC target, const std::u16string& text, int px, int cw, int ch, int picture_bottom) {
    HDC dc = CreateCompatibleDC(target);
    HFONT font = CreateFontW(-px,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,
                             ANTIALIASED_QUALITY,DEFAULT_PITCH,style_.font_family.c_str());
    auto* of = SelectObject(dc,font);
    const int ring = std::max(1,px/14);
    RECT box{px/2,0,cw-px/2,ch};
    DrawTextW(dc,reinterpret_cast<const wchar_t*>(text.c_str()),-1,&box,DT_CENTER|DT_WORDBREAK|DT_CALCRECT);
    const int th = box.bottom-box.top, tw = box.right-box.left;
    const int bar = ch-picture_bottom;
    const int top = bar >= th+px/2 ? picture_bottom+(bar-th)/2 : picture_bottom-th-px/2;
    const int bw = tw+2*ring, bh = th+2*ring;
    sub_bitmap_ = CreateCompatibleBitmap(target,bw,bh);
    if (sub_bitmap_) {
        auto* ob = SelectObject(dc,sub_bitmap_);
        RECT all{0,0,bw,bh};
        HBRUSH key = CreateSolidBrush(SubtitleKey);
        FillRect(dc,&all,key); DeleteObject(key);
        RECT r{ring,ring,ring+tw,ring+th};
        outlined_text(dc,text,r,DT_CENTER|DT_WORDBREAK,ring,RGB(255,255,255));
        SelectObject(dc,ob);
        sub_rect_ = RECT{(cw-tw)/2-ring,top-ring,(cw-tw)/2-ring+bw,top-ring+bh};
    }
    SelectObject(dc,of); DeleteObject(font); DeleteDC(dc);
}

void MoviePlayer::paint(HDC target) {
    RECT client; GetClientRect(hwnd_,&client);
    const int cw = client.right, ch = client.bottom;
    if (cw <= 0 || ch <= 0) return;
    HDC dc = CreateCompatibleDC(target);
    HBITMAP bmp = CreateCompatibleBitmap(target,cw,ch);
    auto* old = SelectObject(dc,bmp);
    FillRect(dc,&client,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
    // The picture keeps its aspect: 640x320 movies sit in the middle of a 4:3 area, leaving letterbox bars.
    const double fit = std::min(double(cw)/width_, double(ch)/(width_*3.0/4.0)); // a 4:3 area, as in the game
    const int vw = int(width_*fit), vh = int(height_*fit);
    const int vx = (cw-vw)/2, vy = (ch-vh)/2;
    std::vector<const SubtitleCue*> now, ref;
    const auto ms = uint32_t(std::max(0.0,time())*1000.0);
    {
        std::lock_guard l(frame_lock_);
        if (has_frame_) {
            BITMAPINFO bi{}; bi.bmiHeader.biSize = sizeof bi.bmiHeader;
            bi.bmiHeader.biWidth = width_; bi.bmiHeader.biHeight = -height_;
            bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
            SetStretchBltMode(dc,HALFTONE);
            StretchDIBits(dc,vx,vy,vw,vh,0,0,width_,height_,frame_.data(),&bi,DIB_RGB_COLORS,SRCCOPY);
        }
    }   // the decoder thread waits on frame_lock_; text drawing happens outside it
    {
        now = active_cues(cues_,stem_,ms);
        if (style_.review) ref = active_cues(reference_,stem_,ms);
        // Subtitles: centred in the bottom bar when it is tall enough, otherwise over the bottom of the picture.
        // The outlined text (one DrawText per outline offset) is rendered once per cue/size change into a cached
        // bitmap and only blitted per frame (session 16: per-frame rendering at 1600x1200 made the movie lag).
        const int px = std::max(12,int(style_.subtitle_px_at_480*ch/480));
        std::u16string text;
        for (const auto* c : now) { if (!text.empty()) text += u'\n'; text += c->text; }
        if (text != sub_text_ || cw != sub_cw_ || ch != sub_ch_) {
            free_subtitle();
            sub_text_ = text; sub_cw_ = cw; sub_ch_ = ch;
            if (!text.empty()) render_subtitle(target,text,px,cw,ch,vy+vh);
        }
        if (sub_bitmap_) {
            HDC sdc = CreateCompatibleDC(target);
            auto* so = SelectObject(sdc,sub_bitmap_);
            TransparentBlt(dc,sub_rect_.left,sub_rect_.top,sub_rect_.right-sub_rect_.left,sub_rect_.bottom-sub_rect_.top,
                           sdc,0,0,sub_rect_.right-sub_rect_.left,sub_rect_.bottom-sub_rect_.top,SubtitleKey);
            SelectObject(sdc,so); DeleteDC(sdc);
        }
        if (style_.review) {
            const int small = std::max(11,px*2/3);
            HFONT info = CreateFontW(-small,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,
                                     ANTIALIASED_QUALITY,DEFAULT_PITCH,style_.font_family.c_str());
            auto* oi = SelectObject(dc,info);
            std::u16string reftext;
            for (const auto* c : ref) { if (!reftext.empty()) reftext += u'\n'; reftext += c->text; }
            if (!reftext.empty()) {
                RECT r{small,small/2,cw-small,vy > small*2 ? vy : ch/3};
                outlined_text(dc,reftext,r,DT_CENTER|DT_WORDBREAK,1,RGB(200,200,200));
            }
            wchar_t line[160];
            int index = -1; uint32_t k = 0;
            for (const auto& c : cues_) if (c.movie == stem_) { if (c.start_ms <= ms) index = int(k); ++k; }
            swprintf_s(line,L"%S  %02u:%02u.%03u / %02u:%02u   cue %d/%u%s", stem_.c_str(), ms/60000, ms/1000%60, ms%1000,
                       unsigned(duration_)/60, unsigned(duration_)%60, index+1, k, paused() ? L"   [paused]" : L"");
            RECT r{6,ch-small-6,cw-6,ch-2};
            outlined_text(dc,std::u16string(reinterpret_cast<const char16_t*>(line)),r,DT_LEFT|DT_SINGLELINE,1,RGB(255,220,120));
            SelectObject(dc,oi); DeleteObject(info);
        }
    }
    BitBlt(target,0,0,cw,ch,dc,0,0,SRCCOPY);
    SelectObject(dc,old); DeleteObject(bmp); DeleteDC(dc);
}

void MoviePlayer::on_video(plm_t*, void* frame, void* user) {
    auto* self = static_cast<MoviePlayer*>(user);
    plm_frame_to_bgra(static_cast<plm_frame_t*>(frame),reinterpret_cast<uint8_t*>(self->staging_.data()),self->width_*4);
    { std::lock_guard l(self->frame_lock_); self->frame_.swap(self->staging_); self->has_frame_ = true; }
    if (self->hwnd_) InvalidateRect(self->hwnd_,nullptr,FALSE);
}

void MoviePlayer::on_audio(plm_t*, void* samples, void* user) {
    auto* self = static_cast<MoviePlayer*>(user);
    if (!self->wave_) return;
    const auto* s = static_cast<plm_samples_t*>(samples);
    auto* b = new Block;
    b->data.resize(size_t(s->count)*2);
    for (size_t i = 0; i < b->data.size(); ++i)
        b->data[i] = int16_t(std::lround(std::clamp(s->interleaved[i],-1.0f,1.0f)*32767.0f));
    b->header.lpData = reinterpret_cast<LPSTR>(b->data.data());
    b->header.dwBufferLength = DWORD(b->data.size()*sizeof(int16_t));
    if (waveOutPrepareHeader(self->wave_,&b->header,sizeof b->header) != MMSYSERR_NOERROR) { delete b; return; }
    if (waveOutWrite(self->wave_,&b->header,sizeof b->header) != MMSYSERR_NOERROR) {
        waveOutUnprepareHeader(self->wave_,&b->header,sizeof b->header); delete b; return;
    }
    self->blocks_.push_back(b);
}

void MoviePlayer::open_audio() {
    if (wave_ || !samplerate_ || !plm_get_num_audio_streams(plm_)) return;
    WAVEFORMATEX f{}; f.wFormatTag = WAVE_FORMAT_PCM; f.nChannels = 2; f.nSamplesPerSec = DWORD(samplerate_);
    f.wBitsPerSample = 16; f.nBlockAlign = 4; f.nAvgBytesPerSec = f.nSamplesPerSec*4;
    if (waveOutOpen(&wave_,WAVE_MAPPER,&f,0,0,CALLBACK_NULL) != MMSYSERR_NOERROR) {
        wave_ = nullptr; plm_set_audio_enabled(plm_,0); // silent playback rather than none
    }
}
void MoviePlayer::reclaim_audio(bool all) {
    while (!blocks_.empty()) {
        auto* b = blocks_.front();
        if (!all && !(b->header.dwFlags & WHDR_DONE)) break;
        waveOutUnprepareHeader(wave_,&b->header,sizeof b->header);
        delete b; blocks_.pop_front();
    }
}
void MoviePlayer::close_audio() {
    if (!wave_) return;
    waveOutReset(wave_);
    reclaim_audio(true);
    waveOutClose(wave_); wave_ = nullptr;
}

void MoviePlayer::play() {
    if (!plm_ || running_.exchange(true)) return;
    finished_ = false; notified_ = false; paused_ = false;
    { std::lock_guard l(decoder_); open_audio(); }
    thread_ = std::thread([this] { run(); });
}

void MoviePlayer::run() {
    double last = now_seconds();
    while (running_.load()) {
        const double t = now_seconds();
        double elapsed = t-last; last = t;
        if (elapsed > 0.25) elapsed = 0.25; // never jump after a stall
        bool ended = false;
        {
            std::lock_guard l(decoder_);
            if (!paused_.load() && !plm_has_ended(plm_)) plm_decode(plm_,elapsed);
            if (wave_) reclaim_audio(false);
            time_ = plm_get_time(plm_);
            ended = plm_has_ended(plm_) && blocks_.empty();
        }
        if (ended && !finished_.exchange(true) && notify_hwnd_ && !notified_.exchange(true))
            PostMessageW(notify_hwnd_,notify_message_,0,notify_param_);
        if (ended && hwnd_) InvalidateRect(hwnd_,nullptr,FALSE);
        Sleep(ended ? 20 : 4);
    }
}

void MoviePlayer::pause(bool paused) {
    if (paused_.exchange(paused) == paused) return;
    std::lock_guard l(decoder_);
    if (wave_) { if (paused) waveOutPause(wave_); else waveOutRestart(wave_); }
    if (hwnd_) InvalidateRect(hwnd_,nullptr,FALSE);
}

void MoviePlayer::seek(double seconds) {
    if (!plm_) return;
    std::lock_guard l(decoder_);
    seconds = std::clamp(seconds,0.0,std::max(0.0,duration_-0.05));
    if (wave_) { waveOutReset(wave_); reclaim_audio(true); if (paused_.load()) waveOutPause(wave_); }
    plm_seek(plm_,seconds,0);
    time_ = plm_get_time(plm_);
    finished_ = false; notified_ = false;
    if (hwnd_) InvalidateRect(hwnd_,nullptr,FALSE);
}

void MoviePlayer::stop() {
    if (running_.exchange(false) && thread_.joinable()) thread_.join();
    std::lock_guard l(decoder_);
    close_audio();
}
}
