"""P5-only immutable Unicode identity, opaque slots and verified copy lifetimes."""

from dataclasses import dataclass
from fractions import Fraction
import hashlib


@dataclass(frozen=True)
class Run:
    route: str
    start: int
    end: int


@dataclass(frozen=True)
class Plan:
    text: str
    slots: bytes
    scalars: tuple
    runs: tuple
    utf16_sha256: str


def make_plan(text, supported):
    """One scalar per slot. Non-ASCII identity only lives in metadata, not a codec."""
    if not text or "\0" in text or "\x7f" in text:
        raise ValueError("empty/NUL/opaque-slot collision")
    raw = text.encode("utf-16-le", errors="strict")
    slots, scalars, runs = bytearray(), [], []
    for offset, char in enumerate(text):
        scalar = ord(char)
        if scalar < 128:
            route = "native";slots.append(scalar)
        elif scalar in supported:
            route = "unicode";slots.append(0x7F)
        else:
            raise ValueError(f"unsupported scalar U+{scalar:04X}; no silent native fallback")
        scalars.append(scalar)
        if runs and runs[-1].route == route:
            runs[-1] = Run(route, runs[-1].start, offset + 1)
        else:runs.append(Run(route, offset, offset + 1))
    return Plan(text, bytes(slots), tuple(scalars), tuple(runs), hashlib.sha256(raw).hexdigest())


def target_em(logical_em, output_width, output_height):
    if any(type(v) is not int or v <= 0 for v in (logical_em, output_width, output_height)):
        raise ValueError("positive integer em/output required")
    sx, sy = Fraction(output_width, 640), Fraction(output_height, 480)
    if sx != sy:
        raise ValueError("PoC requires the measured uniform 4:3 scale")
    em = logical_em * sy
    if em.denominator != 1 or not 1 <= em <= 256:
        raise ValueError("PoC em must map exactly to final pixels")
    return int(em), sx


def logical_advance(physical_advance, scale, native_spacing):
    value = Fraction(physical_advance, 1) / scale - native_spacing
    if value.denominator != 1 or not 0 < value <= 255:
        raise ValueError("advance cannot be represented exactly by native slot header")
    return int(value)


class CopyRegistry:
    """Only explicit full verified copies inherit identity. Address reuse revokes it."""

    def __init__(self, plan):
        self.plan = plan
        self.buffers = set()

    def add(self, address, observed):
        if not 0 < address < 0x100000000 or observed != self.plan.slots + b"\0":
            raise ValueError("Unicode cache provenance mismatch")
        self.buffers.add(address)

    def copy(self, source, destination, before, after):
        if source not in self.buffers:
            raise ValueError("unregistered Unicode copy source")
        self.verify(source, before)
        self.add(destination, after)

    def verify(self, address, observed):
        if address not in self.buffers or observed != self.plan.slots + b"\0":
            self.buffers.discard(address)
            raise ValueError("Unicode buffer lifetime/provenance invalidated")

    def locate(self, pointer):
        matches = [(base, pointer - base) for base in self.buffers
                   if base <= pointer < base + len(self.plan.slots)]
        if len(matches) > 1:
            raise ValueError("ambiguous overlapping Unicode buffers")
        return matches[0] if matches else None

    def invalidate(self, address):
        self.buffers.discard(address)
