#include "glyph_cache.h"
#include <algorithm>

namespace u9cht {
namespace {
GlyphKey key(const std::wstring& hash, uint32_t scalar, uint32_t em) {
    GlyphKey k; std::copy(hash.begin(),hash.end(),k.font.begin());
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
static uint32_t be16(std::span<const uint8_t> d, size_t at) { require(at+2 <= d.size(),"truncated font table"); return uint32_t(d[at])<<8|d[at+1]; }
static uint32_t be32(std::span<const uint8_t> d, size_t at) { return be16(d,at)<<16|be16(d,at+2); }
std::wstring font_family_from_sfnt(std::span<const uint8_t> d) {
    const auto version = be32(d,0);
    require(version != 0x74746366, "font collections (.ttc) are not supported; choose a single-face .ttf/.otf");
    require(version == 0x00010000 || version == 0x4F54544F || version == 0x74727565, "not an OpenType/TrueType font");
    const auto tables = be16(d,4);
    for (uint32_t t = 0; t < tables; ++t) {
        const size_t rec = 12+size_t(t)*16;
        if (be32(d,rec) != 0x6E616D65) continue; // 'name'
        const size_t base = be32(d,rec+8), length = be32(d,rec+12);
        require(base+length <= d.size() && length >= 6, "invalid name table");
        const auto count = be16(d,base+2); const size_t strings = base+be16(d,base+4);
        std::wstring fallback;
        for (uint32_t i = 0; i < count; ++i) {
            const size_t r = base+6+size_t(i)*12;
            // GDI matches CreateFont face names against Windows-platform family names (nameID 1).
            if (be16(d,r) != 3 || be16(d,r+6) != 1) continue;
            const auto encoding = be16(d,r+2), language = be16(d,r+4);
            if (encoding != 1 && encoding != 10) continue;
            const size_t len = be16(d,r+8), at = strings+be16(d,r+10);
            require(at+len <= base+length && len % 2 == 0 && len && len < 64*2, "invalid family name record");
            std::wstring name;
            for (size_t k = 0; k < len; k += 2) name += wchar_t(be16(d,at+k));
            if (language == 0x0409) return name;
            if (fallback.empty()) fallback = name;
        }
        require(!fallback.empty(), "font has no Windows family name");
        return fallback;
    }
    throw std::runtime_error("font has no name table");
}
void GlyphCache::open(const std::filesystem::path& font) {
    require(!registered_, "font already open");
    const auto bytes = std::filesystem::file_size(font);
    require(bytes > 12 && bytes <= 32*1024*1024, "font file size outside 12 B..32 MiB");
    std::vector<uint8_t> data(static_cast<size_t>(bytes));
    { Handle file(CreateFileW(font.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr));
      DWORD got = 0; require(file.get() != INVALID_HANDLE_VALUE && ReadFile(file.get(),data.data(),DWORD(bytes),&got,nullptr) &&
          got == bytes, "font file read failed"); }
    family_ = font_family_from_sfnt(data);
    hash_ = sha256_bytes(data.data(),data.size());
    path_ = font;
    require(AddFontResourceExW(path_.c_str(),FR_PRIVATE,nullptr) > 0, "private font registration failed");
    registered_ = true;
}
const Glyph* GlyphCache::get(uint32_t scalar, uint32_t em) noexcept {
    const int slot = index_.find(scalar,em,KeyView{entries_});
    if (slot >= 0) { ++hits; return &entries_[size_t(slot)]; }
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
        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,family_.c_str());
    require(c.dc && c.font, "GDI font/DC creation failed");
    c.previous = SelectObject(c.dc,c.font);
    require(c.previous && c.previous != HGDI_ERROR, "GDI font selection failed");
    // GDI may report a localized face name, so substitution is ruled out by the selected face's data hash below.
    if (!verified_em_[em]) {
    const auto font_size = GetFontData(c.dc,0,0,nullptr,0);
    require(font_size && font_size != GDI_ERROR && font_size <= 32*1024*1024, "selected font data unavailable");
    std::vector<uint8_t> selected(font_size);
    require(GetFontData(c.dc,0,0,selected.data(),font_size) == font_size &&
        sha256_bytes(selected.data(),selected.size()) == hash_, "font substitution detected: selected face differs from explicit font file");
    verified_em_[em] = true;
    }
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
    Glyph g; g.key = key(hash_,scalar,em); g.index = index; g.width = metrics.gmBlackBoxX;
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
    require(g.advance > 0 && g.advance*16%int(em) == 0 && g.advance*16/int(em) <= 255,
        "non-integral engine logical metric");
    alpha_bytes_ += g.alpha.size();
    index_.insert(scalar,em,size_);
    entries_[size_++] = std::move(g);
}
bool GlyphCache::close() noexcept {
    bool removed = true;
    if (registered_) {
        removed = RemoveFontResourceExW(path_.c_str(),FR_PRIVATE,nullptr) != FALSE;
        if (removed) registered_ = false;
    }
    for (auto& g : entries_) { std::vector<uint8_t> empty; g.alpha.swap(empty); }
    size_ = 0; alpha_bytes_ = 0; index_.clear(); verified_em_.fill(false); hash_.clear(); family_.clear();
    return removed;
}
}
