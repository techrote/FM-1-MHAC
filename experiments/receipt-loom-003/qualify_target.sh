#!/bin/sh
# Compile-only alternative toolchain experiment, no link/packaging/device I/O.
# Usage: sh qualify_target.sh PINNED_DINGHY_CHECKOUT PINNED_TOOLCHAIN_ARCHIVE NEW_OUTPUT_DIR
set -eu
[ "$#" -eq 3 ] || { echo 'usage: qualify_target.sh DINGHY_CHECKOUT TOOLCHAIN_ARCHIVE NEW_OUTPUT_DIR' >&2; exit 2; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PIN=92f17b28f2d05f2f78fd1b160b58475d518902c8
UP=$(CDPATH= cd -- "$1" && pwd)
[ "$(git -C "$UP" rev-parse HEAD)" = "$PIN" ] || { echo 'HOLD: wrong Dinghy revision' >&2; exit 3; }
[ -z "$(git -C "$UP" status --porcelain)" ] || { echo 'HOLD: upstream checkout dirty' >&2; exit 3; }
HASH=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
[ "$(sha256sum "$2" | cut -d ' ' -f 1)" = "$HASH" ] || { echo 'HOLD: wrong toolchain archive hash' >&2; exit 4; }
ARCHIVE=$(realpath "$2")
mkdir -- "$3"
OUT=$(CDPATH= cd -- "$3" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT HUP INT TERM
mkdir "$TMP/toolchain" "$TMP/source"
tar -xJf "$ARCHIVE" -C "$TMP/toolchain" --strip-components=1
TC=$TMP/toolchain/bin
"$TC/clang" --version
printf 'dinghy_pin=%s toolchain_archive_sha256=%s\n' "$PIN" "$HASH"
# Separate core compilation from the unmodified and candidate unity builds.
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin \
    -Wall -Wextra -Werror -c "$HERE/target_probe.c" -o "$OUT/core.o"
"$TC/llvm-readelf" -h "$OUT/core.o"
"$TC/llvm-size" "$OUT/core.o"
"$TC/llvm-nm" -u "$OUT/core.o"
printf 'pi32v2_core_object=PASS (not linked)\n'
git -C "$UP" archive --format=tar "$PIN" > "$TMP/source.tar"
tar -xf "$TMP/source.tar" -C "$TMP/source"
cd "$TMP/source"
compile() {
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin \
        -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen \
        -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' \
        -c firmware/src/dinghy.c -o "$1"
}
compile "$OUT/baseline.o"
"$TC/llvm-size" "$OUT/baseline.o"
printf 'pi32v2_baseline_object=PASS (not linked)\n'
cp "$HERE/app.c" firmware/src/dinghy.c
cp "$HERE/receipt_loom.h" firmware/src/receipt_loom.h
compile "$OUT/candidate.o"
"$TC/llvm-size" "$OUT/candidate.o"
printf 'pi32v2_candidate_object=PASS (not linked)\n'
# Objects stay local. No SDK files, link, .fwsc, release identity or flash access.
