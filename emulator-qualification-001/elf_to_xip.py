#!/usr/bin/env python3
"""Flatten an FM-1 pi32v2 ELF into the raw XIP image accepted by fm1-live/fm1-emu.

This deliberately creates only a bare emulator image. It does not create .fwsc,
loader records, flash headers, recovery metadata, or any installable package.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

XIP_BASE = 0x02000000
DEFAULT_ENTRY = 0x02000120
PT_LOAD = 1

def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]

def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]

def flatten(data: bytes, entry: int) -> tuple[bytes, list[dict[str, int]]]:
    if len(data) < 52 or data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("ELF32 little-endian image required")
    if u16(data, 16) != 2:
        raise ValueError("ET_EXEC required")
    if u16(data, 18) != 241:
        raise ValueError("pi32v2 ELF machine 241 required")
    if u32(data, 24) != entry:
        raise ValueError(f"ELF entry {u32(data,24):#010x} != requested {entry:#010x}")
    phoff, phentsize, phnum = u32(data, 28), u16(data, 42), u16(data, 44)
    if phentsize != 32 or not (1 <= phnum <= 64):
        raise ValueError("invalid ELF32 program-header table")
    if phoff + phentsize * phnum > len(data):
        raise ValueError("truncated program-header table")

    segs: list[tuple[int,int,int,int,int]] = []
    info: list[dict[str,int]] = []
    high = XIP_BASE
    for i in range(phnum):
        o = phoff + i * phentsize
        if u32(data, o) != PT_LOAD:
            continue
        file_off, paddr, filesz, memsz = u32(data,o+4), u32(data,o+12), u32(data,o+16), u32(data,o+20)
        if filesz == 0:
            continue
        if filesz > memsz or file_off + filesz > len(data):
            raise ValueError(f"invalid PT_LOAD {i}")
        end = paddr + filesz
        if paddr < XIP_BASE or end < paddr or end > XIP_BASE + 0x01000000:
            raise ValueError(f"PT_LOAD {i} outside bounded XIP window")
        for _, a, z, _, _ in segs:
            if not (end <= a or z <= paddr):
                raise ValueError(f"overlapping PT_LOAD {i}")
        segs.append((i,paddr,end,file_off,filesz))
        info.append({"index":i,"paddr":paddr,"filesz":filesz,"memsz":memsz})
        high=max(high,end)
    if not segs or not any(a <= entry < z for _,a,z,_,_ in segs):
        raise ValueError("entry is not covered by a PT_LOAD segment")

    out=bytearray(b"\xff" * (high-XIP_BASE))
    for _,a,z,off,n in segs:
        out[a-XIP_BASE:z-XIP_BASE]=data[off:off+n]
    return bytes(out), info

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("elf", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--entry", default=f"{DEFAULT_ENTRY:#x}")
    ns=ap.parse_args()
    entry=int(ns.entry,0)
    raw, segs=flatten(ns.elf.read_bytes(),entry)
    ns.out.write_bytes(raw)
    print(json.dumps({
        "elf":str(ns.elf),"out":str(ns.out),"entry":f"{entry:#010x}",
        "bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"segments":segs
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
