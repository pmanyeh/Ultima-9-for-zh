"""Narrow, unpatched WOW64 diagnostic debugger for the private U9 copy.

Uses CPU debug registers only. There is no WriteProcessMemory, code injection,
software-breakpoint insertion or executable writer. OS loader debug exceptions
are continued normally. Original debug-register state is restored on detach.
"""

import ctypes as c
import hashlib
import os
from pathlib import Path

D = c.c_uint32
W = c.c_uint16
B = c.c_ubyte
P = c.c_void_p
DBG_CONTEXT = 0x10010
FULL_CONTEXT = 0x10017
CONTINUE = 0x10002
NOT_HANDLED = 0x80010001


class FloatSave(c.Structure):
    _fields_ = [(name, D) for name in ("ControlWord", "StatusWord", "TagWord", "ErrorOffset",
                                     "ErrorSelector", "DataOffset", "DataSelector")] + [
        ("RegisterArea", B * 80), ("Cr0NpxState", D)]


class Context32(c.Structure):
    _fields_ = [("ContextFlags", D)] + [(name, D) for name in
        ("Dr0", "Dr1", "Dr2", "Dr3", "Dr6", "Dr7")] + [("FloatSave", FloatSave)] + [
        (name, D) for name in ("SegGs", "SegFs", "SegEs", "SegDs", "Edi", "Esi", "Ebx",
                              "Edx", "Ecx", "Eax", "Ebp", "Eip", "SegCs", "EFlags", "Esp", "SegSs")
    ] + [("ExtendedRegisters", B * 512)]


class ExceptionRecord(c.Structure):
    _fields_ = [("code", D), ("flags", D), ("record", P), ("address", P),
                ("count", D), ("parameters", c.c_size_t * 15)]


class ExceptionInfo(c.Structure):
    _fields_ = [("record", ExceptionRecord), ("first_chance", D)]


class CreateInfo(c.Structure):
    _fields_ = [("file", P), ("process", P), ("thread", P), ("image_base", P),
                ("debug_offset", D), ("debug_size", D), ("tls", P), ("start", P),
                ("image_name", P), ("unicode", W)]


class ThreadInfo(c.Structure):
    _fields_ = [("thread", P), ("tls", P), ("start", P)]


class LoadInfo(c.Structure):
    _fields_ = [("file", P), ("base", P), ("debug_offset", D), ("debug_size", D),
                ("name", P), ("unicode", W)]


class EventUnion(c.Union):
    _fields_ = [("exception", ExceptionInfo), ("create", CreateInfo),
                ("thread", ThreadInfo), ("load", LoadInfo), ("exit_code", D)]


class DebugEvent(c.Structure):
    _fields_ = [("code", D), ("pid", D), ("tid", D), ("u", EventUnion)]


class StartupInfo(c.Structure):
    _fields_ = [("cb", D), ("reserved", P), ("desktop", P), ("title", P)] + [
        (name, D) for name in ("x", "y", "width", "height", "x_chars", "y_chars",
                              "fill", "flags")
    ] + [("show", W), ("reserved_size", W), ("reserved_data", P),
         ("stdin", P), ("stdout", P), ("stderr", P)]


class ProcessInfo(c.Structure):
    _fields_ = [("process", P), ("thread", P), ("pid", D), ("tid", D)]


def hardware_config(points):
    """Up to four (address, execute/readwrite, byte length) hardware points."""
    if len(points) > 4:
        raise ValueError("at most four hardware points")
    addresses = [0, 0, 0, 0]
    control = 0x400  # Architecturally reserved bit 10 is set.
    for index, (address, kind, size) in enumerate(points):
        if not 0 < address < 0x100000000:
            raise ValueError("hardware address outside WOW64 range")
        if kind == "execute":
            if size != 1:
                raise ValueError("execution points have no data width")
            rw, length = 0, 0
        elif kind == "readwrite" and size in (1, 2, 4) and address % size == 0:
            rw, length = 3, {1: 0, 2: 1, 4: 3}[size]
        else:
            raise ValueError("unsupported or unaligned hardware point")
        addresses[index] = address
        control |= 1 << (index * 2)
        control |= (rw | length << 2) << (16 + index * 4)
    return addresses, control


def forward_copy_destination(mnemonic, source_after, destination_after, watched, maximum, flags=0):
    """Recover a forward REP prefix destination, including grouped iterations.

    A hardware data trap may be delivered after several REP iterations. The
    advanced source/destination pointers, rather than an assumed single step,
    establish the copied prefix. Callers must still verify destination bytes.
    """
    unit = {"rep movsd": 4, "rep movsb": 1}.get(mnemonic)
    if unit is None or flags & 0x400:
        return None
    consumed = source_after - watched
    destination = destination_after - consumed
    if consumed <= 0 or consumed > maximum or consumed % unit or not 0 < destination < 0x100000000:
        return None
    return destination, unit, consumed


class PrivateDebugger:
    def __init__(self, expected_sha256):
        if os.name != "nt" or c.sizeof(P) != 8:
            raise RuntimeError("requires 64-bit Windows Python and a WOW64 target")
        self.expected_sha256 = expected_sha256
        self.k = c.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateProcessW": ([c.c_wchar_p, c.c_wchar_p, P, P, D, D, P, c.c_wchar_p,
                                c.POINTER(StartupInfo), c.POINTER(ProcessInfo)], D),
            "DebugSetProcessKillOnExit": ([D], D),
            "WaitForDebugEvent": ([c.POINTER(DebugEvent), D], D),
            "ContinueDebugEvent": ([D, D, D], D),
            "DebugActiveProcessStop": ([D], D),
            "Wow64GetThreadContext": ([P, c.POINTER(Context32)], D),
            "Wow64SetThreadContext": ([P, c.POINTER(Context32)], D),
            "ReadProcessMemory": ([P, P, P, c.c_size_t, c.POINTER(c.c_size_t)], D),
            "SuspendThread": ([P], D), "ResumeThread": ([P], D),
            "CloseHandle": ([P], D),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.k, name); fn.argtypes = args; fn.restype = result
        self.process = None
        self.pid = None
        self.threads = {}
        self.saved = {}
        self.pending = None
        self.exited = False
        self.handles = set()
        self.cleanup_errors = []

    def check(self, result, operation):
        if not result:
            raise OSError(c.get_last_error(), operation)
        return result

    def launch(self):
        root = Path(__file__).resolve().parents[1] / ".local/runtime-game"
        executable = (root / "u9.exe").resolve()
        if not executable.is_relative_to(root.resolve()):
            raise ValueError("target escaped private runtime directory")
        if hashlib.sha256(executable.read_bytes()).hexdigest() != self.expected_sha256:
            raise ValueError("STOP: executable baseline mismatch")
        startup, info = StartupInfo(), ProcessInfo()
        startup.cb = c.sizeof(startup)
        self.check(self.k.CreateProcessW(str(executable), None, None, None, 0, 2, None,
                                        str(root.resolve()), c.byref(startup), c.byref(info)),
                   "CreateProcessW(DEBUG_ONLY_THIS_PROCESS)")
        self.process, self.pid = info.process, info.pid
        self.threads[info.tid] = info.thread
        self.handles.update((info.process, info.thread))
        self.check(self.k.DebugSetProcessKillOnExit(0), "DebugSetProcessKillOnExit")
        return info.pid

    def wait(self, milliseconds=250):
        if self.pending is not None:
            raise RuntimeError("continue pending debug event first")
        event = DebugEvent()
        if not self.k.WaitForDebugEvent(c.byref(event), milliseconds):
            if c.get_last_error() == 121:
                return None
            raise OSError(c.get_last_error(), "WaitForDebugEvent")
        self.pending = event
        if event.code == 3:
            self.threads[event.tid] = event.u.create.thread
            self.handles.update((event.u.create.thread, event.u.create.process))
            if event.u.create.file:
                self.k.CloseHandle(event.u.create.file)
        elif event.code == 2:
            self.threads[event.tid] = event.u.thread.thread
            self.handles.add(event.u.thread.thread)
        elif event.code == 4:
            self.threads.pop(event.tid, None)
            self.saved.pop(event.tid, None)
        elif event.code == 5:
            self.exited = True
        elif event.code == 6 and event.u.load.file:
            self.k.CloseHandle(event.u.load.file)
        return event

    def continue_event(self, status=CONTINUE):
        if self.pending is not None:
            event = self.pending
            self.check(self.k.ContinueDebugEvent(event.pid, event.tid, status), "ContinueDebugEvent")
            self.pending = None

    def context(self, tid):
        ctx = Context32(); ctx.ContextFlags = FULL_CONTEXT
        self.check(self.k.Wow64GetThreadContext(self.threads[tid], c.byref(ctx)),
                   "Wow64GetThreadContext")
        return ctx

    def configure(self, tid, points, *, resume_execution=False):
        if self.pending is None:
            raise RuntimeError("hardware points may only be set while stopped in a debug event")
        ctx = self.context(tid)
        if tid not in self.saved:
            if ctx.Dr7 & 0xFF:
                raise RuntimeError("STOP: pre-existing debug points cannot be safely distinguished")
            self.saved[tid] = tuple(getattr(ctx, name) for name in ("Dr0", "Dr1", "Dr2", "Dr3", "Dr6", "Dr7"))
        addresses, control = hardware_config(points)
        for index, value in enumerate(addresses):
            setattr(ctx, "Dr" + str(index), value)
        ctx.Dr6, ctx.Dr7 = 0, control
        ctx.ContextFlags = DBG_CONTEXT
        if resume_execution:
            ctx.ContextFlags |= 1
            ctx.EFlags |= 0x10000  # Resume flag suppresses this execution-point retrigger.
        self.check(self.k.Wow64SetThreadContext(self.threads[tid], c.byref(ctx)),
                   "Wow64SetThreadContext(debug registers)")

    def read(self, address, size):
        if not 0 < address < 0x100000000 or not 0 <= size <= 0x100000:
            raise ValueError("invalid bounded WOW64 memory read")
        buffer = c.create_string_buffer(size)
        actual = c.c_size_t()
        self.check(self.k.ReadProcessMemory(self.process, address, buffer, size, c.byref(actual)),
                   "ReadProcessMemory")
        if actual.value != size:
            raise OSError("short process-memory read")
        return buffer.raw

    def close(self):
        if self.process and not self.exited:
            for tid, values in list(self.saved.items()):
                handle = self.threads.get(tid)
                if not handle:
                    continue
                suspended = False
                try:
                    if self.pending is None:
                        if self.k.SuspendThread(handle) == 0xFFFFFFFF:
                            continue
                        suspended = True
                    ctx = Context32(); ctx.ContextFlags = DBG_CONTEXT
                    for name, value in zip(("Dr0", "Dr1", "Dr2", "Dr3", "Dr6", "Dr7"), values):
                        setattr(ctx, name, value)
                    self.check(self.k.Wow64SetThreadContext(handle, c.byref(ctx)), "restore debug registers")
                except OSError as error:
                    self.cleanup_errors.append(str(error))
                finally:
                    if suspended:
                        self.k.ResumeThread(handle)
            self.continue_event()
            if not self.k.DebugActiveProcessStop(self.pid):
                self.cleanup_errors.append("DebugActiveProcessStop failed")
        elif self.pending is not None:
            self.continue_event()
        for handle in self.handles:
            if handle:
                self.k.CloseHandle(handle)
        self.process = None
