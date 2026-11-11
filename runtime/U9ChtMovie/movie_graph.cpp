#include "movie_graph.h"
#include <atomic>
#include <intrin.h>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

namespace u9cht {
namespace {
std::atomic<long> g_created{0}, g_rendered{0}, g_render_failures{0}, g_completed{0}, g_stopped{0};
constexpr long EventComplete = 1; // EC_COMPLETE

// Diagnostic trace (session 12: the moongate movie was created, rendered and stopped with no completion and
// nothing visible). Records the calls the game makes, their arguments and results, and the u9.exe return
// addresses for Run/Stop, so the path that ended the movie can be identified.
std::mutex g_trace_lock;
std::vector<std::string> g_trace;
constexpr size_t TraceLimit = 512;
std::atomic<long> g_trace_dropped{0};

std::string narrow(const wchar_t* text) {
    std::string out;
    if (!text) return out;
    for (; *text && out.size() < 120; ++text) {
        const wchar_t c = *text;
        if (c == L'\\' || c == L'"') { out += '\\'; out += char(c); }
        else if (c >= 0x20 && c < 0x7F) out += char(c);
        else out += '?';
    }
    return out;
}

void trace(const char* op, const std::string& fields) {
    char head[96];
    std::snprintf(head,sizeof(head),"\"op\":\"%s\",\"tick\":%lu",op,static_cast<unsigned long>(GetTickCount()));
    std::string entry = head;
    if (!fields.empty()) { entry += ','; entry += fields; }
    std::lock_guard<std::mutex> lock(g_trace_lock);
    if (g_trace.size() >= TraceLimit) { ++g_trace_dropped; return; }
    g_trace.push_back(std::move(entry));
}

std::string num(const char* key, long long value) { return std::string("\"")+key+"\":"+std::to_string(value); }
std::string rect(int x, int y, int w, int h) {
    return "\"rect\":["+std::to_string(x)+","+std::to_string(y)+","+std::to_string(w)+","+std::to_string(h)+"]";
}

// Return addresses inside the u9.exe image for the current call chain.
std::string callers_field() {
    void* frames[24]{};
    const USHORT n = CaptureStackBackTrace(1,24,frames,nullptr);
    std::string out = "\"callers\":[";
    int kept = 0;
    for (USHORT i = 0; i < n && kept < 8; ++i) {
        const auto a = reinterpret_cast<uintptr_t>(frames[i]);
        if (a < 0x400000 || a >= 0x1400000) continue;
        if (kept++) out += ',';
        out += std::to_string(a);
    }
    return out + ']';
}

// u9.exe is built without frame pointers, so CaptureStackBackTrace stops after one frame. Scan the raw stack for
// values that point into the movie code (0x584800..0x585200), which identifies the skip path (0x58516C key,
// 0x585189 input event) that called the stop routine 0x584E40.
std::string stack_scan_field() {
    std::string out = "\"stack_movie\":[";
    const auto* top = reinterpret_cast<const uintptr_t*>(_AddressOfReturnAddress());
    ULONG_PTR low = 0, high = 0;
    GetCurrentThreadStackLimits(&low,&high);
    int kept = 0;
    for (int i = 0; i < 2048 && kept < 8; ++i) {
        const auto slot = reinterpret_cast<uintptr_t>(top + i);
        if (slot + sizeof(uintptr_t) > high) break;
        const uintptr_t v = top[i];
        if (v < 0x584800 || v >= 0x585200) continue;
        if (kept++) out += ',';
        out += std::to_string(v);
    }
    return out + ']';
}

std::string guid_field(REFIID riid) {
    char text[64];
    std::snprintf(text,sizeof(text),"\"iid\":\"%08lX-%04X-%04X\"",static_cast<unsigned long>(riid.Data1),riid.Data2,riid.Data3);
    return text;
}

class MovieGraph final : public IGraphBuilder, public IMediaControl, public IMediaEventEx, public IVideoWindow {
public:
    explicit MovieGraph(const MovieGraphConfig& config) : config_(config) { ++g_created; trace("create",""); }
    ~MovieGraph() { trace("destroy",state_fields()); player_.stop(); player_.destroy_window(); }

    // IUnknown
    STDMETHODIMP QueryInterface(REFIID riid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (riid == IID_IUnknown || riid == IID_IGraphBuilder || riid == IID_IFilterGraph) *out = static_cast<IGraphBuilder*>(this);
        else if (riid == IID_IMediaControl) *out = static_cast<IMediaControl*>(this);
        else if (riid == IID_IMediaEvent || riid == IID_IMediaEventEx) *out = static_cast<IMediaEventEx*>(this);
        else if (riid == IID_IVideoWindow) *out = static_cast<IVideoWindow*>(this);
        else { trace("qi_miss",guid_field(riid)); return E_NOINTERFACE; }
        AddRef(); return S_OK;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return ULONG(++refs_); }
    STDMETHODIMP_(ULONG) Release() override { const long r = --refs_; if (!r) delete this; return ULONG(r); }

    // IDispatch (unused by u9.exe)
    STDMETHODIMP GetTypeInfoCount(UINT*) override { return E_NOTIMPL; }
    STDMETHODIMP GetTypeInfo(UINT, LCID, ITypeInfo**) override { return E_NOTIMPL; }
    STDMETHODIMP GetIDsOfNames(REFIID, LPOLESTR*, UINT, LCID, DISPID*) override { return E_NOTIMPL; }
    STDMETHODIMP Invoke(DISPID, REFIID, LCID, WORD, DISPPARAMS*, VARIANT*, EXCEPINFO*, UINT*) override { return E_NOTIMPL; }

    // IFilterGraph / IGraphBuilder
    STDMETHODIMP AddFilter(IBaseFilter*, LPCWSTR) override { return E_NOTIMPL; }
    STDMETHODIMP RemoveFilter(IBaseFilter*) override { return E_NOTIMPL; }
    STDMETHODIMP EnumFilters(IEnumFilters**) override { return E_NOTIMPL; }
    STDMETHODIMP FindFilterByName(LPCWSTR, IBaseFilter**) override { return E_NOTIMPL; }
    STDMETHODIMP ConnectDirect(IPin*, IPin*, const AM_MEDIA_TYPE*) override { return E_NOTIMPL; }
    STDMETHODIMP Reconnect(IPin*) override { return E_NOTIMPL; }
    STDMETHODIMP Disconnect(IPin*) override { return E_NOTIMPL; }
    STDMETHODIMP SetDefaultSyncSource() override { return S_OK; }
    STDMETHODIMP Connect(IPin*, IPin*) override { return E_NOTIMPL; }
    STDMETHODIMP Render(IPin*) override { return E_NOTIMPL; }
    STDMETHODIMP RenderFile(LPCWSTR file, LPCWSTR) override {
        if (!file) return E_POINTER;
        std::string error;
        if (!player_.open(file,error)) {
            ++g_render_failures;
            trace("render_file","\"file\":\""+narrow(file)+"\",\"error\":\""+error+"\",\"ok\":false");
            return VFW_E_UNSUPPORTED_STREAM;
        }
        player_.set_style(config_.style);
        player_.set_cues(config_.cues);
        ++g_rendered;
        trace("render_file","\"file\":\""+narrow(file)+"\",\"ok\":true,"+state_fields()+","+
              num("width",player_.video_width())+","+num("height",player_.video_height()));
        return S_OK;
    }
    STDMETHODIMP AddSourceFilter(LPCWSTR, LPCWSTR, IBaseFilter**) override { return E_NOTIMPL; }
    STDMETHODIMP SetLogFile(DWORD_PTR) override { return S_OK; }
    STDMETHODIMP Abort() override { return S_OK; }
    STDMETHODIMP ShouldOperationContinue() override { return S_OK; }

    // IMediaControl
    STDMETHODIMP Run() override {
        if (!player_.window()) {
            int x = x_, y = y_, w = w_, h = h_;
            if (w <= 0 || h <= 0) { x = 0; y = 0; w = ModeWidth; h = ModeHeight; }
            scale_to_owner(x,y,w,h);
            if (!player_.create_window(owner_,x,y,w,h)) {
                trace("run",std::string("\"window\":false,")+num("last_error",GetLastError())+","+rect(x,y,w,h)+","+callers_field());
                return E_FAIL;
            }
            player_.set_notify(notify_,notify_message_,notify_param_);
            if (!visible_) player_.set_visible(false);
            trace("run_window",rect(x,y,w,h)+",\"requested\":["+std::to_string(x_)+","+std::to_string(y_)+","+std::to_string(w_)+","+std::to_string(h_)+"],"+num("owner",reinterpret_cast<uintptr_t>(owner_))+","+
                  num("owner_visible",owner_ ? IsWindowVisible(owner_) : -1)+","+num("visible",visible_ ? 1 : 0));
        }
        const bool resume = player_.paused();
        if (resume) player_.pause(false); else player_.play();
        trace("run",num("resume",resume ? 1 : 0)+","+callers_field());
        return S_OK;
    }
    STDMETHODIMP Pause() override { trace("pause",callers_field()); player_.pause(true); return S_OK; }
    STDMETHODIMP Stop() override { trace("stop",state_fields()+","+callers_field()+","+stack_scan_field()); player_.stop(); ++g_stopped; return S_OK; }
    STDMETHODIMP GetState(LONG, OAFilterState* state) override {
        if (!state) return E_POINTER;
        *state = player_.finished() || !player_.window() ? State_Stopped : player_.paused() ? State_Paused : State_Running;
        if (*state != last_state_) { last_state_ = *state; trace("get_state",num("state",*state)+","+callers_field()); }
        return S_OK;
    }
    STDMETHODIMP RenderFile(BSTR file) override { return RenderFile(static_cast<LPCWSTR>(file),nullptr); }
    STDMETHODIMP AddSourceFilter(BSTR, IDispatch**) override { return E_NOTIMPL; }
    STDMETHODIMP get_FilterCollection(IDispatch**) override { return E_NOTIMPL; }
    STDMETHODIMP get_RegFilterCollection(IDispatch**) override { return E_NOTIMPL; }
    STDMETHODIMP StopWhenReady() override { return Stop(); }

    // IMediaEvent / IMediaEventEx
    STDMETHODIMP GetEventHandle(OAEVENT*) override { return E_NOTIMPL; }
    STDMETHODIMP GetEvent(long* code, LONG_PTR* p1, LONG_PTR* p2, long) override {
        if (!code || !p1 || !p2) return E_POINTER;
        if (player_.finished() && !complete_reported_) {
            complete_reported_ = true; ++g_completed;
            trace("get_event",num("code",1)+","+state_fields());
            *code = EventComplete; *p1 = S_OK; *p2 = 0; return S_OK;
        }
        if (++get_event_polls_ <= 3) trace("get_event",num("code",0)+","+num("poll",get_event_polls_)+","+callers_field());
        return E_ABORT; // no event pending
    }
    STDMETHODIMP WaitForCompletion(long timeout, long* code) override {
        trace("wait_for_completion",num("timeout",timeout)+","+state_fields()+","+callers_field()); if (code) *code = player_.finished() ? EventComplete : 0; return player_.finished() ? S_OK : E_ABORT; }
    STDMETHODIMP CancelDefaultHandling(long) override { return S_OK; }
    STDMETHODIMP RestoreDefaultHandling(long) override { return S_OK; }
    STDMETHODIMP FreeEventParams(long, LONG_PTR, LONG_PTR) override { return S_OK; }
    STDMETHODIMP SetNotifyWindow(OAHWND hwnd, long message, LONG_PTR param) override {
        notify_ = reinterpret_cast<HWND>(hwnd); notify_message_ = UINT(message); notify_param_ = param;
        trace("set_notify_window",num("hwnd",hwnd)+","+num("message",message));
        player_.set_notify(notify_,notify_message_,notify_param_);
        return S_OK;
    }
    STDMETHODIMP SetNotifyFlags(long) override { return S_OK; }
    STDMETHODIMP GetNotifyFlags(long* flags) override { if (flags) *flags = 0; return S_OK; }

    // IVideoWindow
    STDMETHODIMP put_Caption(BSTR) override { return S_OK; }
    STDMETHODIMP get_Caption(BSTR*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowStyle(long style) override { trace("put_window_style",num("style",style)); return S_OK; } // the player window is always an input-transparent child
    STDMETHODIMP get_WindowStyle(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowStyleEx(long) override { return S_OK; }
    STDMETHODIMP get_WindowStyleEx(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_AutoShow(long) override { return S_OK; }
    STDMETHODIMP get_AutoShow(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowState(long) override { return S_OK; }
    STDMETHODIMP get_WindowState(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_BackgroundPalette(long) override { return S_OK; }
    STDMETHODIMP get_BackgroundPalette(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_Visible(long visible) override { trace("put_visible",num("visible",visible)); visible_ = visible != 0; player_.set_visible(visible_); return S_OK; }
    STDMETHODIMP get_Visible(long* visible) override { if (visible) *visible = visible_ ? -1 : 0; return S_OK; }
    STDMETHODIMP put_Left(long v) override { x_ = int(v); return reposition(); }
    STDMETHODIMP get_Left(long* v) override { if (v) *v = x_; return S_OK; }
    STDMETHODIMP put_Width(long v) override { w_ = int(v); return reposition(); }
    STDMETHODIMP get_Width(long* v) override { if (v) *v = w_; return S_OK; }
    STDMETHODIMP put_Top(long v) override { y_ = int(v); return reposition(); }
    STDMETHODIMP get_Top(long* v) override { if (v) *v = y_; return S_OK; }
    STDMETHODIMP put_Height(long v) override { h_ = int(v); return reposition(); }
    STDMETHODIMP get_Height(long* v) override { if (v) *v = h_; return S_OK; }
    STDMETHODIMP put_Owner(OAHWND owner) override {
        owner_ = reinterpret_cast<HWND>(owner);
        RECT r{}; if (owner_) GetClientRect(owner_,&r);
        trace("put_owner",num("owner",owner)+","+num("client_w",r.right)+","+num("client_h",r.bottom));
        return S_OK;
    }
    STDMETHODIMP get_Owner(OAHWND* owner) override { if (owner) *owner = reinterpret_cast<OAHWND>(owner_); return S_OK; }
    STDMETHODIMP put_MessageDrain(OAHWND) override { return S_OK; }
    STDMETHODIMP get_MessageDrain(OAHWND*) override { return E_NOTIMPL; }
    STDMETHODIMP get_BorderColor(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_BorderColor(long) override { return S_OK; }
    STDMETHODIMP get_FullScreenMode(long* v) override { if (v) *v = 0; return S_OK; }
    STDMETHODIMP put_FullScreenMode(long) override { return S_OK; }
    STDMETHODIMP SetWindowForeground(long) override { return S_OK; }
    STDMETHODIMP NotifyOwnerMessage(OAHWND, long, LONG_PTR, LONG_PTR) override { return S_OK; }
    STDMETHODIMP SetWindowPosition(long x, long y, long w, long h) override { trace("set_window_position",rect(x,y,w,h)); x_ = int(x); y_ = int(y); w_ = int(w); h_ = int(h); return reposition(); }
    STDMETHODIMP GetWindowPosition(long* x, long* y, long* w, long* h) override {
        if (x) *x = x_; if (y) *y = y_; if (w) *w = w_; if (h) *h = h_; return S_OK;
    }
    STDMETHODIMP GetMinIdealImageSize(long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP GetMaxIdealImageSize(long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP GetRestorePosition(long*, long*, long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP HideCursor(long) override { return S_OK; }
    STDMETHODIMP IsCursorHidden(long* v) override { if (v) *v = 0; return S_OK; }

private:
    std::string state_fields() const {
        char text[160];
        std::snprintf(text,sizeof(text),"\"time\":%.3f,\"duration\":%.3f,\"finished\":%s,\"window\":%s,\"paused\":%s",
            player_.time(),player_.duration(),player_.finished()?"true":"false",player_.window()?"true":"false",
            player_.paused()?"true":"false");
        return text;
    }
    // u9.exe switches to a 640x480 movie mode and positions the video inside it (CONFIRMED session 14:
    // SetWindowPosition(0,80,640,320)). The GOG ddraw wrapper presents that mode in a larger window, and the player
    // itself centres the 640x320 picture in a 4:3 area with the subtitles in the bottom bar. So the player window
    // covers the owner's whole client area (the full movie screen), as the original black movie screen does;
    // the requested rectangle only describes the picture's place inside that screen (session 15: using the scaled
    // 2:1 rectangle shrank the picture a second time and left the game visible above and below).
    static constexpr int ModeWidth = 640, ModeHeight = 480;
    void scale_to_owner(int& x, int& y, int& w, int& h) const {
        RECT r{};
        if (!owner_ || !GetClientRect(owner_,&r) || r.right <= 0 || r.bottom <= 0) return;
        x = 0; y = 0; w = r.right; h = r.bottom;
    }
    HRESULT reposition() {
        if (player_.window() && w_ > 0 && h_ > 0) {
            int x = x_, y = y_, w = w_, h = h_;
            scale_to_owner(x,y,w,h);
            player_.set_position(x,y,w,h);
        }
        return S_OK;
    }
    MovieGraphConfig config_;
    MoviePlayer player_;
    std::atomic<long> refs_{1};
    HWND owner_ = nullptr, notify_ = nullptr;
    UINT notify_message_ = 0;
    LONG_PTR notify_param_ = 0;
    int x_ = 0, y_ = 0, w_ = 0, h_ = 0;
    bool visible_ = true, complete_reported_ = false;
    OAFilterState last_state_ = OAFilterState(-1);
    long get_event_polls_ = 0;
};
}

HRESULT create_movie_graph(const MovieGraphConfig& config, REFIID riid, void** out) {
    if (!out) return E_POINTER;
    *out = nullptr;
    auto* graph = new (std::nothrow) MovieGraph(config);
    if (!graph) return E_OUTOFMEMORY;
    const HRESULT hr = graph->QueryInterface(riid,out);
    graph->Release();
    return hr;
}

std::vector<std::string> drain_movie_trace() {
    std::vector<std::string> out;
    { std::lock_guard<std::mutex> lock(g_trace_lock); out.swap(g_trace); }
    if (const long dropped = g_trace_dropped.exchange(0)) out.push_back("\"op\":\"dropped\","+num("count",dropped));
    return out;
}

MovieGraphStats movie_graph_stats() noexcept {
    return {g_created.load(),g_rendered.load(),g_render_failures.load(),g_completed.load(),g_stopped.load()};
}
}
