#include "movie_graph.h"
#include <atomic>

namespace u9cht {
namespace {
std::atomic<long> g_created{0}, g_rendered{0}, g_render_failures{0}, g_completed{0}, g_stopped{0};
constexpr long EventComplete = 1; // EC_COMPLETE

class MovieGraph final : public IGraphBuilder, public IMediaControl, public IMediaEventEx, public IVideoWindow {
public:
    explicit MovieGraph(const MovieGraphConfig& config) : config_(config) { ++g_created; }
    ~MovieGraph() { player_.stop(); player_.destroy_window(); }

    // IUnknown
    STDMETHODIMP QueryInterface(REFIID riid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (riid == IID_IUnknown || riid == IID_IGraphBuilder || riid == IID_IFilterGraph) *out = static_cast<IGraphBuilder*>(this);
        else if (riid == IID_IMediaControl) *out = static_cast<IMediaControl*>(this);
        else if (riid == IID_IMediaEvent || riid == IID_IMediaEventEx) *out = static_cast<IMediaEventEx*>(this);
        else if (riid == IID_IVideoWindow) *out = static_cast<IVideoWindow*>(this);
        else return E_NOINTERFACE;
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
        if (!player_.open(file,error)) { ++g_render_failures; return VFW_E_UNSUPPORTED_STREAM; }
        player_.set_style(config_.style);
        player_.set_cues(config_.cues);
        ++g_rendered;
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
            if (w <= 0 || h <= 0) { RECT r{}; if (owner_) GetClientRect(owner_,&r); x = 0; y = 0; w = r.right ? r.right : 640; h = r.bottom ? r.bottom : 480; }
            if (!player_.create_window(owner_,x,y,w,h)) return E_FAIL;
            player_.set_notify(notify_,notify_message_,notify_param_);
            if (!visible_) player_.set_visible(false);
        }
        if (player_.paused()) player_.pause(false); else player_.play();
        return S_OK;
    }
    STDMETHODIMP Pause() override { player_.pause(true); return S_OK; }
    STDMETHODIMP Stop() override { player_.stop(); ++g_stopped; return S_OK; }
    STDMETHODIMP GetState(LONG, OAFilterState* state) override {
        if (!state) return E_POINTER;
        *state = player_.finished() || !player_.window() ? State_Stopped : player_.paused() ? State_Paused : State_Running;
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
            *code = EventComplete; *p1 = S_OK; *p2 = 0; return S_OK;
        }
        return E_ABORT; // no event pending
    }
    STDMETHODIMP WaitForCompletion(long, long* code) override { if (code) *code = player_.finished() ? EventComplete : 0; return player_.finished() ? S_OK : E_ABORT; }
    STDMETHODIMP CancelDefaultHandling(long) override { return S_OK; }
    STDMETHODIMP RestoreDefaultHandling(long) override { return S_OK; }
    STDMETHODIMP FreeEventParams(long, LONG_PTR, LONG_PTR) override { return S_OK; }
    STDMETHODIMP SetNotifyWindow(OAHWND hwnd, long message, LONG_PTR param) override {
        notify_ = reinterpret_cast<HWND>(hwnd); notify_message_ = UINT(message); notify_param_ = param;
        player_.set_notify(notify_,notify_message_,notify_param_);
        return S_OK;
    }
    STDMETHODIMP SetNotifyFlags(long) override { return S_OK; }
    STDMETHODIMP GetNotifyFlags(long* flags) override { if (flags) *flags = 0; return S_OK; }

    // IVideoWindow
    STDMETHODIMP put_Caption(BSTR) override { return S_OK; }
    STDMETHODIMP get_Caption(BSTR*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowStyle(long) override { return S_OK; } // the player window is always an input-transparent child
    STDMETHODIMP get_WindowStyle(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowStyleEx(long) override { return S_OK; }
    STDMETHODIMP get_WindowStyleEx(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_AutoShow(long) override { return S_OK; }
    STDMETHODIMP get_AutoShow(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_WindowState(long) override { return S_OK; }
    STDMETHODIMP get_WindowState(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_BackgroundPalette(long) override { return S_OK; }
    STDMETHODIMP get_BackgroundPalette(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_Visible(long visible) override { visible_ = visible != 0; player_.set_visible(visible_); return S_OK; }
    STDMETHODIMP get_Visible(long* visible) override { if (visible) *visible = visible_ ? -1 : 0; return S_OK; }
    STDMETHODIMP put_Left(long v) override { x_ = int(v); return reposition(); }
    STDMETHODIMP get_Left(long* v) override { if (v) *v = x_; return S_OK; }
    STDMETHODIMP put_Width(long v) override { w_ = int(v); return reposition(); }
    STDMETHODIMP get_Width(long* v) override { if (v) *v = w_; return S_OK; }
    STDMETHODIMP put_Top(long v) override { y_ = int(v); return reposition(); }
    STDMETHODIMP get_Top(long* v) override { if (v) *v = y_; return S_OK; }
    STDMETHODIMP put_Height(long v) override { h_ = int(v); return reposition(); }
    STDMETHODIMP get_Height(long* v) override { if (v) *v = h_; return S_OK; }
    STDMETHODIMP put_Owner(OAHWND owner) override { owner_ = reinterpret_cast<HWND>(owner); return S_OK; }
    STDMETHODIMP get_Owner(OAHWND* owner) override { if (owner) *owner = reinterpret_cast<OAHWND>(owner_); return S_OK; }
    STDMETHODIMP put_MessageDrain(OAHWND) override { return S_OK; }
    STDMETHODIMP get_MessageDrain(OAHWND*) override { return E_NOTIMPL; }
    STDMETHODIMP get_BorderColor(long*) override { return E_NOTIMPL; }
    STDMETHODIMP put_BorderColor(long) override { return S_OK; }
    STDMETHODIMP get_FullScreenMode(long* v) override { if (v) *v = 0; return S_OK; }
    STDMETHODIMP put_FullScreenMode(long) override { return S_OK; }
    STDMETHODIMP SetWindowForeground(long) override { return S_OK; }
    STDMETHODIMP NotifyOwnerMessage(OAHWND, long, LONG_PTR, LONG_PTR) override { return S_OK; }
    STDMETHODIMP SetWindowPosition(long x, long y, long w, long h) override { x_ = int(x); y_ = int(y); w_ = int(w); h_ = int(h); return reposition(); }
    STDMETHODIMP GetWindowPosition(long* x, long* y, long* w, long* h) override {
        if (x) *x = x_; if (y) *y = y_; if (w) *w = w_; if (h) *h = h_; return S_OK;
    }
    STDMETHODIMP GetMinIdealImageSize(long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP GetMaxIdealImageSize(long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP GetRestorePosition(long*, long*, long*, long*) override { return E_NOTIMPL; }
    STDMETHODIMP HideCursor(long) override { return S_OK; }
    STDMETHODIMP IsCursorHidden(long* v) override { if (v) *v = 0; return S_OK; }

private:
    HRESULT reposition() { if (player_.window() && w_ > 0 && h_ > 0) player_.set_position(x_,y_,w_,h_); return S_OK; }
    MovieGraphConfig config_;
    MoviePlayer player_;
    std::atomic<long> refs_{1};
    HWND owner_ = nullptr, notify_ = nullptr;
    UINT notify_message_ = 0;
    LONG_PTR notify_param_ = 0;
    int x_ = 0, y_ = 0, w_ = 0, h_ = 0;
    bool visible_ = true, complete_reported_ = false;
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

MovieGraphStats movie_graph_stats() noexcept {
    return {g_created.load(),g_rendered.load(),g_render_failures.load(),g_completed.load(),g_stopped.load()};
}
}
