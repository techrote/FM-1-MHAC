#!/bin/sh
# Experimental ELF-only link after qualify_target.sh; never creates a flash image.
# Usage: sh qualify_link.sh PINNED_DINGHY_CHECKOUT TOOLCHAIN_ARCHIVE OBJECT_DIRECTORY
set -eu
[ "$#" -eq 3 ] || { echo 'usage: qualify_link.sh DINGHY_CHECKOUT TOOLCHAIN_ARCHIVE OBJECT_DIRECTORY' >&2; exit 2; }
PIN=92f17b28f2d05f2f78fd1b160b58475d518902c8
HASH=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
UP=$(CDPATH= cd -- "$1" && pwd)
[ "$(git -C "$UP" rev-parse HEAD)" = "$PIN" ] || { echo 'HOLD: wrong Dinghy revision' >&2; exit 3; }
[ -z "$(git -C "$UP" status --porcelain)" ] || { echo 'HOLD: upstream checkout dirty' >&2; exit 3; }
[ "$(sha256sum "$2" | cut -d ' ' -f 1)" = "$HASH" ] || { echo 'HOLD: wrong toolchain archive hash' >&2; exit 4; }
ARCHIVE=$(realpath "$2")
OUT=$(CDPATH= cd -- "$3" && pwd)
# Require the prior gate's objects, and never overwrite linked evidence.
for n in baseline candidate; do
    test -f "$OUT/$n.o"
    test ! -e "$OUT/$n.elf"
done
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT HUP INT TERM
mkdir "$TMP/toolchain" "$TMP/source"
tar -xJf "$ARCHIVE" -C "$TMP/toolchain" --strip-components=1
TC=$TMP/toolchain/bin
git -C "$UP" archive --format=tar "$PIN" > "$TMP/source.tar"
tar -xf "$TMP/source.tar" -C "$TMP/source"
cd "$TMP/source"
# Exact original startup and ISR assembly, no modifications to HAL or memory map.
for src in firmware/crt0.S firmware/hal/fm1_vec.S firmware/hal/fm1_isr.S; do
    name=$(basename "$src" .S)
    "$TC/clang" -target pi32v2 -mcpu=ac791n -c "$src" -o "$TMP/$name.o"
done
for n in baseline candidate; do
    "$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld \
        "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$OUT/$n.o" -o "$OUT/$n.elf"
    "$TC/llvm-readelf" -h "$OUT/$n.elf"
    "$TC/llvm-size" -A "$OUT/$n.elf"
    undefined=$("$TC/llvm-nm" -u "$OUT/$n.elf")
    [ -z "$undefined" ] || { printf '%s\n' "$undefined" >&2; exit 5; }
    printf 'pi32v2_%s_elf=PASS (linked, no undefined symbols; not packaged)\n' "$n"
done
# No objcopy, no packager, no flashable .fwsc, no publication or hardware I/O.
