#!/bin/sh
# Original host-only qualification. Never runs upstream target packaging/flashing.
# Usage: sh qualify_host.sh /path/to/dinghy-clone /new/output/directory
set -eu
[ "$#" -eq 2 ] || { echo 'usage: qualify_host.sh DINGHY_CHECKOUT NEW_OUTPUT_DIR' >&2; exit 2; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PIN=92f17b28f2d05f2f78fd1b160b58475d518902c8
UP=$(CDPATH= cd -- "$1" && pwd)
[ "$(git -C "$UP" rev-parse HEAD)" = "$PIN" ] || { echo 'HOLD: wrong Dinghy revision' >&2; exit 3; }
[ -z "$(git -C "$UP" status --porcelain)" ] || { echo 'HOLD: upstream checkout dirty' >&2; exit 3; }
mkdir -- "$2"
OUT=$(CDPATH= cd -- "$2" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT HUP INT TERM
# Work only in temporary extracted source; never edit supplied checkout.
git -C "$UP" archive --format=tar "$PIN" > "$TMP/source.tar"
mkdir "$TMP/source"
tar -xf "$TMP/source.tar" -C "$TMP/source"
cd "$TMP/source"
cc --version | head -1
printf 'dinghy_pin=%s\n' "$PIN"
# Match tests/run_host.sh host compiler contract; no target compiler or packager.
compile() {
    cc -O2 -Wall -Wno-unused-function -DDINGHY_HOST -DAPP_VER='"dev"' \
        -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -o "$TMP/host" firmware/src/dinghy.c
}
compile
"$TMP/host" "$TMP/baseline"
# Baseline original upstream host output is not published; check it exists.
[ -s "$TMP/baseline.wav" ]
cp "$HERE/app.c" firmware/src/dinghy.c
cp "$HERE/phase_debt.h" firmware/src/phase_debt.h
compile
"$TMP/host" "$OUT/panel" "$HERE/panel.script"
"$TMP/host" "$TMP/repeat" "$HERE/panel.script"
cmp "$OUT/panel.wav" "$TMP/repeat.wav"
python3 - "$OUT/panel.wav" <<'PY'
import array, hashlib, pathlib, sys, wave
p = pathlib.Path(sys.argv[1])
with wave.open(str(p), 'rb') as w:
    assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100)
    assert 4.98 < w.getnframes() / 44100 <= 5.0
    raw = w.readframes(w.getnframes())
a = array.array('h', raw)
if sys.byteorder != 'little': a.byteswap()
assert max(map(abs, a)) <= 6400
# Guard margins account for 256-frame scheduling and 800-frame decay.
for lo, hi, active in [(0,450,False),(550,950,True),(1050,1450,True),
                       (1550,1950,True),(2050,2450,True),(2550,2950,True),
                       (3050,3550,False),(3650,4050,True),(4150,4650,False),
                       (4750,4900,False)]:
    v = a[2*(44100*lo//1000):2*(44100*hi//1000)]
    assert bool(any(v)) == active, (lo, hi, active)
print('upstream_host_baseline=PASS candidate=PASS deterministic=PASS windows=10 peak=%d sha256=%s' %
      (max(map(abs, a)), hashlib.sha256(p.read_bytes()).hexdigest()))
PY
for t in 100 800 3100 4600; do
    test -s "$OUT/panel-$t.ppm"
    cmp "$OUT/panel-$t.ppm" "$TMP/repeat-$t.ppm"
done
printf 'screens=4 deterministic=PASS (not hardware)\n'
