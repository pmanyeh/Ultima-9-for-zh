"""Explicit P5-only native surface call support; engine code is never patched.

Unlike the read-only wintrace module, this module writes its own allocation and
changes EIP temporarily. Lock/Unlock run on the stopped game's own render thread.
Its self-unwinding stub is safe to resume after debugger detachment. No thread is
created and no DLL is injected. Pixel writing is deliberately absent here.
"""

import ctypes as c

from .p5_surface import lock_stub
from .wintrace import PrivateDebugger


class SurfaceDebugger(PrivateDebugger):
    def __init__(self, expected_sha256):
        super().__init__(expected_sha256)
        P, U, S = c.c_void_p, c.c_uint32, c.c_size_t
        for name, (args, result) in {
            "VirtualAllocEx": ([P, P, S, U, U], P),
            "VirtualProtectEx": ([P, P, S, U, c.POINTER(U)], U),
            "VirtualFreeEx": ([P, P, S, U], U),
            "WriteProcessMemory": ([P, P, P, S, c.POINTER(S)], U),
            "FlushInstructionCache": ([P, P, S], U),
        }.items():
            fn = getattr(self.k, name); fn.argtypes = args; fn.restype = result
        self.allocation = None
        self.in_flight = False

    def write_owned(self, address, data):
        if self.allocation is None or not self.allocation <= address <= address + len(data) <= self.allocation + 8192:
            raise ValueError("write escaped own allocation")
        self._write(address, data)

    def _write(self, address, data):
        buffer = c.create_string_buffer(data)
        actual = c.c_size_t()
        self.check(self.k.WriteProcessMemory(self.process, address, buffer, len(data), c.byref(actual)),
                   "P5 WriteProcessMemory")
        if actual.value != len(data):
            raise OSError("short P5 memory write")

    def prepare_lock(self, surface, rect, return_va):
        if self.allocation is not None:
            raise RuntimeError("one surface call at a time")
        base = self.check(self.k.VirtualAllocEx(self.process, None, 8192, 0x3000, 4),
                          "P5 VirtualAllocEx")
        self.allocation = base
        data, code, first, second = lock_stub(base, surface, rect, return_va)
        self.write_owned(base, data)
        self.write_owned(base + 4096, code)
        old = c.c_uint32()
        self.check(self.k.VirtualProtectEx(self.process, base + 4096, 4096, 0x20, c.byref(old)),
                   "P5 VirtualProtectEx(code RX)")
        self.check(self.k.FlushInstructionCache(self.process, base + 4096, len(code)),
                   "P5 FlushInstructionCache")
        return {"allocation": base, "entry": base + 4096,
                "locked_marker": base + 4096 + first,
                "unlocked_marker": base + 4096 + second,
                "return_va": return_va, "code_hex": code.hex(" ")}

    def enter_call(self, tid, entry):
        if self.allocation is None or entry != self.allocation + 4096 or self.in_flight:
            raise RuntimeError("invalid call entry")
        ctx = self.context(tid)
        ctx.ContextFlags = 0x10001  # CONTROL only; retain installed debug points.
        ctx.Eip = entry
        ctx.EFlags |= 0x10000
        self.check(self.k.Wow64SetThreadContext(self.threads[tid], c.byref(ctx)),
                   "P5 temporary EIP redirect")
        self.in_flight = True

    def release_completed_call(self):
        if self.in_flight:
            raise RuntimeError("cannot free executing call stub")
        if self.allocation is not None:
            self.check(self.k.VirtualFreeEx(self.process, self.allocation, 0, 0x8000),
                       "P5 VirtualFreeEx")
            self.allocation = None

    def close(self):
        # An executing stub must remain allocated: removing hardware points and
        # continuing lets it unlock, restore FP/SSE/registers and return itself.
        if not self.in_flight and self.process and not self.exited:
            try:
                self.release_completed_call()
            except OSError as error:
                self.cleanup_errors.append(str(error))
        super().close()
