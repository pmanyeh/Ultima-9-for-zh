"""Bounded P5 RGB surface validation and coverage blending (asset-free)."""

from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Surface:
    width: int
    height: int
    pitch: int
    pointer: int
    caps: int


def parse_surface(data):
    """Accept only the experimentally observed 32-bit WOW64 DDSURFACEDESC2."""
    if len(data) != 124:
        raise ValueError("DDSURFACEDESC2 must be 124 bytes")
    v = struct.unpack("<31I", data)
    # CAPS, HEIGHT, WIDTH, PITCH and PIXELFORMAT must all be present.
    if v[0] != 124 or v[1] & 0x100F != 0x100F:
        raise ValueError("surface descriptor missing required fields")
    if v[18:26] != (32, 0x40, 0, 32, 0xFF0000, 0xFF00, 0xFF, 0):
        raise ValueError("surface is not the observed XRGB8888 format")
    pitch = struct.unpack_from("<i", data, 16)[0]
    if not (0 < v[3] <= 4096 and 0 < v[2] <= 4096
            and v[3] * 4 <= pitch <= 0x10000 and pitch % 4 == 0):
        raise ValueError("unsupported surface bounds/pitch")
    return Surface(v[3], v[2], pitch, v[9], v[26])


def intersect_rect(a, b):
    """Half-open output-space clipping; empty intersections return None."""
    if len(a) != 4 or len(b) != 4 or any(type(n) is not int for n in (*a, *b)):
        raise ValueError("rectangles require four integers")
    if a[0] > a[2] or a[1] > a[3] or b[0] > b[2] or b[1] > b[3]:
        raise ValueError("inverted rectangle")
    r = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return r if r[0] < r[2] and r[1] < r[3] else None


def blend_row(original, coverage, color=(255, 255, 255)):
    """Blend grayscale coverage into BGRX, retaining every original X byte."""
    if len(original) != len(coverage) * 4 or len(color) != 3 or any(
            type(n) is not int or not 0 <= n <= 255 for n in color):
        raise ValueError("invalid blend row")
    out = bytearray(original)
    for x, a in enumerate(coverage):
        for channel, target in enumerate(reversed(color)):
            offset = x * 4 + channel
            out[offset] = (target * a + original[offset] * (255 - a) + 127) // 255
    return bytes(out)


def lock_stub(base, surface, rect, return_va=0x597B1A):
    """Own-allocation x86 stdcall Lock/Unlock stub; never overwrites engine code.

    Saves flags/registers/FP/SSE itself. Hardware execution markers (NOPs) are
    after Lock and conditional Unlock; no INT3 exists. Detaching at either marker
    lets the stub unlock/restore/return without a live host. In-flight allocation
    must never be freed. Offsets are returned for strict marker identity checks.
    """
    if not 0 < base <= 0xFFFFE000 or base % 4096 or not 0 < surface < 0x100000000:
        raise ValueError("invalid WOW64 allocation/surface")
    if intersect_rect(rect, rect) != tuple(rect):
        raise ValueError("empty lock rectangle")
    data = bytearray(4096)
    struct.pack_into("<4i", data, 4, *rect)
    struct.pack_into("<I", data, 20, 124)
    if not 0 < return_va < 0x100000000:
        raise ValueError("invalid return VA")
    code_va = base + 4096
    code = bytearray(b"\x9C\x60\x0F\xAE\x05" + struct.pack("<I", base + 512))
    def push(v):
        code.extend(b"\x68" + struct.pack("<I", v))
    push(0)                 # event
    push(0x801)             # DDLOCK_WAIT | DDLOCK_NOSYSLOCK
    push(base + 20)         # DDSURFACEDESC2
    push(base + 4)          # RECT
    push(surface)
    code.extend(b"\xB8" + struct.pack("<I", surface) + b"\x8B\x00\xFF\x50\x64")
    code.extend(b"\xA3" + struct.pack("<I", base + 144))
    first = len(code)
    code.extend(b"\x90\x85\xC0\x78\x00")  # marker; test eax,eax; js second marker
    branch = len(code) - 1
    push(base + 4)
    push(surface)
    code.extend(b"\xB8" + struct.pack("<I", surface) + b"\x8B\x00\xFF\x90\x80\x00\x00\x00")
    code.extend(b"\xA3" + struct.pack("<I", base + 148))
    second = len(code)
    code[branch] = second - (branch + 1)
    code.extend(b"\x90\x0F\xAE\x0D" + struct.pack("<I", base + 512) + b"\x61\x9D")
    code.extend(b"\xE9" + struct.pack("<i", return_va - (code_va + len(code) + 5)))
    return bytes(data), bytes(code), first, second
