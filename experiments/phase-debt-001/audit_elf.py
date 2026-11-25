#!/usr/bin/env python3
"""ELF-only audit for FM1-001. No packaging, flash image or device access."""
import hashlib
import importlib.util
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

PIN = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
BASE = 0x02000120
LIMIT = BASE + 0x8DFBC
REGIONS = {".text": (BASE, LIMIT), ".ram_text": (0x01C00000, 0x01C06000),
           ".data": (0x01C08000, 0x01C20000), ".bss": (0x01C08000, 0x01C20000),
           ".pool": (0x01C20000, 0x01C74000), ".noinit": (0x01C7C000, 0x01C7FD50)}


def require(ok, detail):
    if not ok:
        raise ValueError(detail)


def cmd(*args):
    return subprocess.check_output([str(a) for a in args], text=True)


def audit(path, tc):
    blob = path.read_bytes()
    require(blob[:7] == b"\x7fELF\x01\x01\x01", "not little-endian ELF32")
    h = struct.unpack_from("<16sHHIIIIIHHHHHH", blob)
    require(h[1] == 2 and h[4] == BASE, "unexpected type or entry")
    phoff, shoff, phentsize, phnum, shentsize, shnum, shstr = (
        h[5], h[6], h[9], h[10], h[11], h[12], h[13])
    require(phentsize == 32 and shentsize == 40 and 0 < shstr < shnum,
            "unexpected ELF table format")
    sections = [struct.unpack_from("<10I", blob, shoff + i * shentsize)
                for i in range(shnum)]
    strings = sections[shstr]
    names = blob[strings[4]:strings[4]+strings[5]]
    mapped = {}
    for s in sections:
        name = names[s[0]:].split(b"\0", 1)[0].decode("ascii")
        if not s[2] & 2 or not s[5]:
            continue
        require(name in REGIONS and name not in mapped, f"unexpected alloc section {name}")
        lo, hi = REGIONS[name]
        require(lo <= s[3] and s[3] + s[5] <= hi, f"{name} outside region")
        require(s[1] == 8 or s[4] + s[5] <= len(blob), "section beyond file")
        mapped[name] = s
    require(set(mapped) == set(REGIONS), "missing allocated section")
    require(mapped[".data"][3]+mapped[".data"][5] <= mapped[".bss"][3],
            "data/bss overlap")
    require(all(mapped[n][1] == 8 for n in (".bss", ".pool", ".noinit")),
            "unexpected initialization of NOLOAD region")
    syms = {}
    for ln in cmd(tc/"llvm-nm", "--defined-only", path).splitlines():
        fields = ln.split()
        if len(fields) == 3:
            syms[fields[2]] = int(fields[0], 16)
    require(syms["_start"] == BASE, "incorrect start symbol")
    require(not cmd(tc/"llvm-nm", "-u", path).strip(), "undefined symbols")
    text = mapped[".text"]
    require(blob[text[4]:text[4]+4] == bytes.fromhex("04818000"),
            "upstream entry stub mismatch")
    loads = []
    for i in range(phnum):
        typ, off, va, pa, fs, ms, flags, align = struct.unpack_from(
            "<8I", blob, phoff+i*phentsize)
        if typ == 1 and fs:
            require(off+fs <= len(blob) and fs <= ms, "bad load extent")
            require(BASE <= pa and pa+fs <= LIMIT, "load outside candidate XIP slot")
            loads.append((pa, pa+fs))
    loads.sort()
    require(loads and loads[0][0] == BASE and
            all(a[1] <= b[0] for a,b in zip(loads, loads[1:])), "overlapping load extents")
    # Confirm each initialized section is covered at its linker-declared load address.
    for name, sym in ((".text", "_start"), (".ram_text", "_rt_load"),
                      (".data", "_data_load")):
        start = syms[sym]
        require(start % 4 == 0 and any(a <= start and start+mapped[name][5] <= b
                                        for a,b in loads), f"{name} load not covered")
    # This is an LLVM-specific screen, NOT a proof of ROM avoidance or equivalent
    # to Dinghy's proprietary objdump parser. Retain actual mnemonic samples.
    dis = cmd(tc/"llvm-objdump", "-d", path)
    rt = cmd(tc/"llvm-objdump", "-d", "-j", ".ram_text", path)
    def instructions(s):
        return [ln for ln in s.splitlines() if re.match(r"^\s*[0-9a-fA-F]+:", ln)]
    il, rl = instructions(dis), instructions(rt)
    require(il and rl, "disassembler returned no instruction lines")
    unknown = [ln for ln in il if re.search(r"<unknown>|\bunknown\b", ln, re.I)]
    calls = [ln for ln in rl if re.search(r"\bcall\w*\b", ln, re.I)]
    rom = [ln for ln in il if re.search(r"\b(?:0x)?ffc[0-9a-f]{5}\b", ln, re.I)]
    print(json.dumps({"elf":path.name, "sha256":hashlib.sha256(blob).hexdigest(),
          "machine":h[2], "entry":hex(h[4]), "load_extent":loads[-1][1]-BASE,
          "section_sizes":{n:s[5] for n,s in mapped.items()},
          "instruction_lines":len(il), "ram_instruction_lines":len(rl),
          "unknown_lines":len(unknown), "ram_call_screen":calls[:8],
          "rom_hex_screen":rom[:8], "instruction_sample":il[:4]}, sort_keys=True), flush=True)
    require(not unknown and not calls and not rom, "LLVM screen flagged instructions; inspect")
    return hashlib.sha256(blob).hexdigest()


def main():
    up, tc, first, second = map(lambda p: Path(p).resolve(), sys.argv[1:])
    require(cmd("git", "-C", up, "rev-parse", "HEAD").strip() == PIN, "wrong upstream")
    require(not cmd("git", "-C", up, "status", "--porcelain").strip(), "dirty upstream")
    # Use the exact upstream MMIO source checker in a temporary copy. Do not
    # invoke its package builder, or copy its code into this repository.
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)/"dinghy"
        shutil.copytree(up, tree, ignore=shutil.ignore_patterns(".git"))
        spec = importlib.util.spec_from_file_location("dinghy_build", tree/"tools/build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        require(not module.mmio_check(), "upstream baseline MMIO checker failed")
        here = Path(__file__).resolve().parent
        shutil.copyfile(here/"app.c", tree/"firmware/src/dinghy.c")
        shutil.copyfile(here/"phase_debt.h", tree/"firmware/src/phase_debt.h")
        errors = module.mmio_check()
        require(not errors, f"candidate MMIO checker failed: {errors}")
        # Negative control: deliberately bad source, disposable copy only.
        with (tree/"firmware/src/phase_debt.h").open("a") as f:
            f.write("\n/* negative control */\n#define BAD_ADDR 0x10000\n")
        require(module.mmio_check(), "MMIO checker failed to detect planted violation")
        print("pinned_mmio_baseline_candidate_negative_control=PASS", flush=True)
    for name in ("baseline", "candidate"):
        a = audit(first/(name+".elf"), tc)
        b = audit(second/(name+".elf"), tc)
        require(a == b, f"{name} ELF differs between independent build directories")
        print(f"{name}_independent_ELF_rebuild=PASS {a}", flush=True)
    print("ELF static audit PASS; ROM screen is limited, no runtime or installability claim")


if __name__ == "__main__":
    main()
