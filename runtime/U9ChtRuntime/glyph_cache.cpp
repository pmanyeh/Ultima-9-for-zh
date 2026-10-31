#include "glyph_cache.h"
#include <algorithm>

namespace u9cht {
namespace {
GlyphKey key(uint32_t scalar, uint32_t em) {
    GlyphKey k; std::copy(std::begin(FontHash),std::end(FontHash),k.font.begin());
    k.scalar = scalar; k.em = em; k.mode = GGO_GRAY8_BITMAP|GGO_GLYPH_INDEX; return k;
}
struct Context {
    HDC dc = nullptr;
    HFONT font = nullptr;
    HGDIOBJ previous = nullptr;
    ~Context() {
        if (dc && previous && previous != HGDI_ERROR) SelectObject(dc,previous);
        if (font) DeleteObject(font);
        if (dc) DeleteDC(dc);
    }
};
}
void GlyphCache::open(const std::filesystem::path& font) {
    require(!registered_ && sha256(font) == FontHash, "font baseline mismatch");
    path_ = font;
    require(AddFontResourceExW(path_.c_str(),FR_PRIVATE,nullptr) > 0, "private font registration failed");
    registered_ = true;
}
const Glyph* find_glyph(std::span<const Glyph> cache, const GlyphKey& k) noexcept {
    for (const auto& g : cache) if (g.key == k) return &g;
    return nullptr;
}
const Glyph* GlyphCache::get(uint32_t scalar, uint32_t em) noexcept {
    if (const auto* g = find_glyph({entries_.data(),size_},key(scalar,em))) { ++hits; return g; }
    ++misses; return nullptr;
}
void GlyphCache::warm(uint32_t scalar, uint32_t em) {
    if (get(scalar,em)) return;
    require(registered_ && size_ < entries_.size() && scalar <= 0xFFFF &&
        !(scalar >= 0xD800 && scalar <= 0xDFFF) && em && em <= 256, "invalid glyph key/capacity");
    // The DC and all selected GDI objects are created/deleted in this same
    // initializer thread. Only CPU coverage survives its normal thread exit.
    Context c; c.dc = CreateCompatibleDC(nullptr);
    c.font = CreateFontW(-int(em),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Noto Sans CJK TC");
    require(c.dc && c.font, "GDI font/DC creation failed");
    c.previous = SelectObject(c.dc,c.font);
    require(c.previous && c.previous != HGDI_ERROR, "GDI font selection failed");
    wchar_t face[128]{};
    require(GetTextFaceW(c.dc,128,face) && std::wstring(face) == L"Noto Sans CJK TC", "font substitution detected");
    const auto font_size = GetFontData(c.dc,0,0,nullptr,0);
    require(font_size && font_size != GDI_ERROR && font_size <= 32*1024*1024, "selected font data unavailable");
    std::vector<uint8_t> selected(font_size);
    require(GetFontData(c.dc,0,0,selected.data(),font_size) == font_size &&
        sha256_bytes(selected.data(),selected.size()) == FontHash, "selected face differs from explicit font file");
    wchar_t text[] = {static_cast<wchar_t>(scalar),0}; WORD index = 0xFFFF;
    require(GetGlyphIndicesW(c.dc,text,1,&index,GGI_MARK_NONEXISTING_GLYPHS) == 1 && index != 0xFFFF,
        "unsupported Unicode glyph");
    MAT2 matrix{}; matrix.eM11.value = 1; matrix.eM22.value = 1;
    GLYPHMETRICS metrics{};
    const UINT mode = GGO_GRAY8_BITMAP|GGO_GLYPH_INDEX;
    const DWORD bytes = GetGlyphOutlineW(c.dc,index,mode,&metrics,0,nullptr,&matrix);
    require(bytes != GDI_ERROR && bytes <= 512*512 && metrics.gmBlackBoxX <= 512 && metrics.gmBlackBoxY <= 512,
        "invalid grayscale glyph bounds");
    std::vector<uint8_t> gray(bytes);
    require(!bytes || GetGlyphOutlineW(c.dc,index,mode,&metrics,bytes,gray.data(),&matrix) == bytes,
        "grayscale glyph buffer changed");
    Glyph g; g.key = key(scalar,em); g.index = index; g.width = metrics.gmBlackBoxX;
    g.height = metrics.gmBlackBoxY; g.bearing_x = metrics.gmptGlyphOrigin.x;
    g.bearing_y = metrics.gmptGlyphOrigin.y; g.advance = metrics.gmCellIncX;
    const size_t stride = (g.width+3)&~size_t(3);
    require(gray.size() == stride*g.height, "grayscale stride mismatch");
    g.alpha.resize(size_t(g.width)*g.height);
    for (uint32_t y = 0; y < g.height; ++y) for (uint32_t x = 0; x < g.width; ++x) {
        const auto coverage = gray[size_t(y)*stride+x];
        require(coverage <= 64, "invalid gray8 coverage");
        g.alpha[size_t(y)*g.width+x] = static_cast<uint8_t>((coverage*255+32)/64);
    }
    require(g.advance == int(em), "non-integral P5 logical metric");
    entries_[size_++] = std::move(g);
}
bool GlyphCache::close() noexcept {
    bool removed = true;
    if (registered_) {
        removed = RemoveFontResourceExW(path_.c_str(),FR_PRIVATE,nullptr) != FALSE;
        if (removed) registered_ = false;
    }
    for (auto& g : entries_) { std::vector<uint8_t> empty; g.alpha.swap(empty); }
    size_ = 0;
    return removed;
}
}
