#!/usr/bin/env python3
"""Measure a pinned original loader in a disposable checkout. No install, no package,
no binary output retained. Alternative pi32v2 toolchain, not the vendor compiler.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

PIN = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
TC_HASH = "cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990"


def run(*args, cwd=None):
    return subprocess.check_output([str(a) for a in args], cwd=cwd)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def layout(body):
    if type(body) is not int or body <= 0:
        raise ValueError("invalid body length")
    return {"body_bytes": body, "staged_bytes_including_header": body + 32,
            "first_stage_size_limit_met": body <= 19968,
            "record_sector_disjoint": body <= 16352,
            "record_sector_overlap_bytes": max(0, body - 16352),
            "installation_authorized": False}


def selftest():
    for n in range(1, 20481):
        v = layout(n)
        assert v["first_stage_size_limit_met"] == (n + 512 <= 20480)
        assert v["record_sector_disjoint"] == (n + 32 <= 16384)
        assert v["record_sector_overlap_bytes"] == max(0, n + 32 - 16384)
        assert not v["installation_authorized"]
    for n in (0, -1, True, "16352"):
        try:
            layout(n)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid length")
    print("81924 layout assertions PASS; synthetic only")


def measure(up, archive):
    up, archive = up.resolve(), archive.resolve()
    if run("git", "-C", up, "rev-parse", "HEAD").decode().strip() != PIN:
        raise ValueError("wrong upstream pin")
    if run("git", "-C", up, "status", "--porcelain"):
        raise ValueError("dirty upstream")
    if digest(archive.read_bytes()) != TC_HASH:
        raise ValueError("wrong compiler archive")
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        source, tc = root / "source", root / "tc"
        source.mkdir()
        tc.mkdir()
        tar = root / "source.tar"
        tar.write_bytes(run("git", "-C", up, "archive", PIN))
        run("tar", "-xf", tar, "-C", source)
        run("tar", "-xJf", archive, "-C", tc, "--strip-components=1")
        bin = tc / "bin"
        cc = bin / "clang"
        flags = ["-target", "pi32v2", "-mcpu=ac791n"]
        print(run(cc, "--version").decode().strip(), flush=True)
        def build(name):
            folder = root / name
            folder.mkdir()
            start, obj, elf, raw = [folder / x for x in ("start.o", "loader.o", "loader.elf", "loader.bin")]
            run(cc, *flags, "-c", "firmware/loader/crt0_ldr.S", "-o", start, cwd=source)
            run(cc, *flags, "-Os", "-ffunction-sections", "-fno-builtin",
                "-Wall", "-Wno-unused-function", "-Ifirmware/hal", "-Ifirmware/src",
                '-DLDR_NAME="DINGHY"', "-DLDR_COLOUR=0xb47fu", "-c",
                "firmware/loader/loader.c", "-o", obj, cwd=source)
            run(bin / "ld.lld", "--gc-sections", "-e", "_start", "-T",
                "firmware/loader/loader.ld", start, obj, "-o", elf, cwd=source)
            if run(bin / "llvm-nm", "-u", elf).strip():
                raise ValueError("unresolved loader symbols")
            print(run(bin / "llvm-size", "-A", elf).decode().strip(), flush=True)
            run(bin / "llvm-objcopy", "-O", "binary", "-j", ".text", elf, raw)
            return raw.read_bytes()
        a, b = build("first"), build("repeat")
        if not a or a != b or len(a) > 0x14000:
            raise ValueError("invalid or nonreproducible loader image")
        # Invoke original wrapping logic locally, in memory, with no package writer.
        sys.path.insert(0, str(source / "tools"))
        import build as upstream_build
        wrapped = upstream_build.ldr_wrap(a)
        body = int.from_bytes(wrapped[8:12], "little")
        if len(wrapped) != body + 32:
            raise ValueError("unexpected wrapper length")
        result = layout(body)
        result.update(raw_bytes=len(a), raw_sha256=digest(a),
                      wrapper_sha256=digest(wrapped), upstream=PIN,
                      compiler_archive_sha256=TC_HASH,
                      reproducible_raw=True, status="HOLD")
        print(json.dumps(result, sort_keys=True), flush=True)
        if not result["first_stage_size_limit_met"]:
            raise ValueError("first-stage limit exceeded")
    # No target binaries retained or uploaded, no device access.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", nargs="?", type=pathlib.Path)
    parser.add_argument("archive", nargs="?", type=pathlib.Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
    elif args.upstream and args.archive:
        measure(args.upstream, args.archive)
    else:
        parser.error("supply pinned checkout and toolchain archive, or --selftest")


if __name__ == "__main__":
    main()
