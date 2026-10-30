"""Private-process scalable BMP glyph rasterizer; no game or window access."""

import ctypes as c
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path


@dataclass(frozen=True)
class Glyph:
    scalar: int
    index: int
    em_pixels: int
    width: int
    height: int
    bearing_x: int
    bearing_y: int
    advance: int
    alpha: bytes


def gray8_alpha(data, width, height):
    """Remove GGO_GRAY8 DWORD padding and expand its 0..64 coverage to 0..255."""
    if not 0 <= width <= 512 or not 0 <= height <= 512:
        raise ValueError("glyph bounds outside PoC limit")
    stride = (width + 3) & ~3
    if len(data) != stride * height:
        raise ValueError("incorrect grayscale raster size")
    pixels = bytes(data[y * stride + x] for y in range(height) for x in range(width))
    if any(v > 64 for v in pixels):
        raise ValueError("invalid GDI gray8 coverage")
    return bytes((v * 255 + 32) // 64 for v in pixels)


class GdiRasterizer:
    """Use an explicit, hash-verified face; release its registration on close."""

    def __init__(self, font_path, family, expected_sha256, em_pixels):
        if os.name != "nt":
            raise RuntimeError("Windows GDI is required")
        if not 1 <= em_pixels <= 256:
            raise ValueError("em size outside PoC limit")
        self.path = Path(font_path).resolve()
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("font file hash mismatch")
        self.g = c.WinDLL("gdi32", use_last_error=True)
        P, I, U = c.c_void_p, c.c_int32, c.c_uint32
        signatures = {
            "AddFontResourceExW": ([c.c_wchar_p, U, P], I),
            "RemoveFontResourceExW": ([c.c_wchar_p, U, P], I),
            "CreateCompatibleDC": ([P], P), "DeleteDC": ([P], I),
            "CreateFontW": ([I] * 5 + [U] * 8 + [c.c_wchar_p], P),
            "SelectObject": ([P, P], P), "DeleteObject": ([P], I),
            "GetTextFaceW": ([P, I, c.c_wchar_p], I),
            "GetFontData": ([P, U, U, P, U], U),
            "GetGlyphIndicesW": ([P, c.c_wchar_p, I, P, U], U),
            "GetGlyphOutlineW": ([P, U, U, P, U, P, P], U),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.g, name); fn.argtypes = args; fn.restype = result
        self.dc = self.font = self.previous = None
        self.registered = False
        self.em_pixels = em_pixels
        try:
            if not self.g.AddFontResourceExW(str(self.path), 0x10, None):
                raise OSError("private font registration failed")
            self.registered = True
            self.dc = self.g.CreateCompatibleDC(None)
            # MM_TEXT memory DC: negative height requests this many pixels per em.
            self.font = self.g.CreateFontW(-em_pixels, 0, 0, 0, 400, 0, 0, 0,
                                          1, 0, 0, 4, 0, family)
            if not self.dc or not self.font:
                raise OSError("font/DC creation failed")
            self.previous = self.g.SelectObject(self.dc, self.font)
            if not self.previous or self.previous == c.c_void_p(-1).value:
                raise OSError("font selection failed")
            face = c.create_unicode_buffer(128)
            if not self.g.GetTextFaceW(self.dc, len(face), face) or face.value != family:
                raise ValueError("font substitution detected")
            size = self.g.GetFontData(self.dc, 0, 0, None, 0)
            if size == 0xFFFFFFFF or not 0 < size <= 32 * 1024 * 1024:
                raise ValueError("selected font data unavailable")
            data = c.create_string_buffer(size)
            if self.g.GetFontData(self.dc, 0, 0, data, size) != size:
                raise ValueError("selected font data truncated")
            self.selected_sha256 = hashlib.sha256(data.raw).hexdigest()
            if self.selected_sha256 != expected_sha256:
                raise ValueError("selected face bytes differ from explicit font file")
        except Exception:
            self.close()
            raise

    def rasterize(self, scalar):
        if not 0 <= scalar <= 0xFFFF or 0xD800 <= scalar <= 0xDFFF:
            raise ValueError("bounded BMP rasterizer cannot handle this scalar")
        glyph_index = c.c_uint16()
        if self.g.GetGlyphIndicesW(self.dc, chr(scalar), 1, c.byref(glyph_index), 1) != 1:
            raise OSError("Unicode glyph mapping failed")
        if glyph_index.value == 0xFFFF:
            raise ValueError("unsupported Unicode glyph")

        class Metrics(c.Structure):
            _fields_ = [("width", c.c_uint32), ("height", c.c_uint32),
                        ("origin_x", c.c_int32), ("origin_y", c.c_int32),
                        ("advance_x", c.c_int16), ("advance_y", c.c_int16)]

        # MAT2's FIXED consists of a WORD fraction followed by a signed WORD value.
        matrix = (c.c_uint32 * 4)(0x10000, 0, 0, 0x10000)
        metrics = Metrics()
        size = self.g.GetGlyphOutlineW(self.dc, glyph_index.value, 6 | 0x80,
                                      c.byref(metrics), 0, None, matrix)
        if size == 0xFFFFFFFF or size > 512 * 512:
            raise OSError("grayscale glyph rasterization failed")
        data = c.create_string_buffer(size)
        if size and self.g.GetGlyphOutlineW(self.dc, glyph_index.value, 6 | 0x80,
                                           c.byref(metrics), size, data, matrix) != size:
            raise OSError("grayscale glyph buffer changed")
        return Glyph(scalar, glyph_index.value, self.em_pixels, metrics.width, metrics.height,
                     metrics.origin_x, metrics.origin_y, metrics.advance_x,
                     gray8_alpha(data.raw, metrics.width, metrics.height))

    def close(self):
        if self.dc and self.previous:
            self.g.SelectObject(self.dc, self.previous)
            self.previous = None
        if self.font:
            self.g.DeleteObject(self.font); self.font = None
        if self.dc:
            self.g.DeleteDC(self.dc); self.dc = None
        if self.registered:
            self.g.RemoveFontResourceExW(str(self.path), 0x10, None)
            self.registered = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
