"""Read-only PE32 metadata inspection; no executable rewriting or extraction."""

import hashlib
import struct


class PEError(ValueError):
    pass


class PEImage:
    def __init__(self, data):
        self.data = bytes(data)
        if self.read(0, 2) != b"MZ":
            raise PEError("missing DOS signature")
        pe = self.u32(0x3C)
        if self.read(pe, 4) != b"PE\0\0":
            raise PEError("missing PE signature")
        self.machine, section_count = self.unpack("<HH", pe + 4)
        optional_size = self.u16(pe + 20)
        self.characteristics = self.u16(pe + 22)
        optional = pe + 24
        self.read(optional, optional_size)
        if optional_size < 96 or self.u16(optional) != 0x10B:
            raise PEError("only PE32 images supported")
        self.entry_rva = self.u32(optional + 16)
        self.image_base = self.u32(optional + 28)
        self.image_size = self.u32(optional + 56)
        self.headers_size = self.u32(optional + 60)
        self.dll_characteristics = self.u16(optional + 70)
        directory_count = self.u32(optional + 92)
        if directory_count > 16 or 96 + directory_count * 8 > optional_size:
            raise PEError("invalid PE directory count")
        self.directories = [self.unpack("<II", optional + 96 + index * 8)
                            for index in range(directory_count)]
        if section_count > 96:
            raise PEError("implausible PE section count")
        self.sections = []
        for index in range(section_count):
            offset = optional + optional_size + index * 40
            raw = self.read(offset, 40)
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", raw, 8)
            self.read(raw_offset, raw_size)
            self.sections.append({
                "name": raw[:8].split(b"\0", 1)[0].decode("ascii", errors="replace"),
                "rva": rva, "virtual_size": virtual_size, "raw_offset": raw_offset,
                "raw_size": raw_size, "characteristics": struct.unpack_from("<I", raw, 36)[0],
            })

    def read(self, offset, length):
        if offset < 0 or length < 0 or offset + length > len(self.data):
            raise PEError("PE file read out of bounds")
        return self.data[offset:offset + length]

    def unpack(self, fmt, offset):
        return struct.unpack(fmt, self.read(offset, struct.calcsize(fmt)))

    def u16(self, offset):
        return self.unpack("<H", offset)[0]

    def u32(self, offset):
        return self.unpack("<I", offset)[0]

    def rva_offset(self, rva, length=1):
        if rva < 0 or length < 0:
            raise PEError("invalid RVA")
        if rva < self.headers_size and rva + length <= self.headers_size:
            self.read(rva, length)
            return rva
        for section in self.sections:
            relative = rva - section["rva"]
            if 0 <= relative and relative + length <= section["raw_size"]:
                result = section["raw_offset"] + relative
                self.read(result, length)
                return result
        raise PEError("RVA has no file-backed section range")

    def offset_rva(self, offset):
        for section in self.sections:
            if section["raw_offset"] <= offset < section["raw_offset"] + section["raw_size"]:
                return section["rva"] + offset - section["raw_offset"]
        if 0 <= offset < self.headers_size:
            return offset
        raise PEError("file offset has no mapped RVA")

    def cstring(self, rva):
        output = bytearray()
        for index in range(4096):
            byte = self.read(self.rva_offset(rva + index), 1)
            if byte == b"\0":
                return output.decode("ascii", errors="strict")
            output += byte
        raise PEError("unterminated PE string")

    def directory(self, index):
        return self.directories[index] if index < len(self.directories) else (0, 0)

    def imports(self):
        rva, size = self.directory(1)
        if not rva or not size:
            return []
        result = []
        for index in range(min(size // 20, 4096)):
            descriptor = self.unpack("<IIIII", self.rva_offset(rva + index * 20, 20))
            if not any(descriptor):
                return result
            original_thunk, _, _, name_rva, first_thunk = descriptor
            library = self.cstring(name_rva)
            thunk = original_thunk or first_thunk
            for slot in range(65536):
                value = self.u32(self.rva_offset(thunk + slot * 4, 4))
                if value == 0:
                    break
                name = None if value & 0x80000000 else self.cstring(value + 2)
                result.append({"dll": library, "name": name,
                               "ordinal": value & 0xFFFF if name is None else None,
                               "iat_rva": first_thunk + slot * 4})
            else:
                raise PEError("unterminated import thunk")
        raise PEError("unterminated import descriptors")

    def resources(self):
        root, size = self.directory(2)
        if not root or not size:
            return []
        output = []
        visited = set()

        def read_relative(relative, length):
            if relative < 0 or relative + length > size:
                raise PEError("resource directory out of bounds")
            return self.read(self.rva_offset(root + relative, length), length)

        def walk(relative, path):
            if len(path) > 4 or relative in visited:
                raise PEError("recursive resource directory")
            visited.add(relative)
            header = read_relative(relative, 16)
            named, numbered = struct.unpack_from("<HH", header, 12)
            if named + numbered > 4096:
                raise PEError("implausible resource entry count")
            for index in range(named + numbered):
                name, target = struct.unpack("<II", read_relative(relative + 16 + index * 8, 8))
                if name & 0x80000000:
                    name_offset = name & 0x7FFFFFFF
                    length = struct.unpack("<H", read_relative(name_offset, 2))[0]
                    name = read_relative(name_offset + 2, length * 2).decode("utf-16-le")
                if target & 0x80000000:
                    walk(target & 0x7FFFFFFF, path + [name])
                else:
                    data_rva, length, codepage, _ = struct.unpack("<IIII", read_relative(target, 16))
                    self.rva_offset(data_rva, length)
                    output.append({"path": path + [name], "rva": data_rva,
                                   "size": length, "codepage": codepage})
            visited.remove(relative)

        walk(0, [])
        return output

    def metadata(self):
        return {"sha256": hashlib.sha256(self.data).hexdigest(), "size": len(self.data),
                "machine": self.machine, "image_base": self.image_base,
                "entry_rva": self.entry_rva, "image_size": self.image_size,
                "characteristics": self.characteristics,
                "dll_characteristics": self.dll_characteristics,
                "sections": self.sections, "imports": self.imports(), "resources": self.resources()}
