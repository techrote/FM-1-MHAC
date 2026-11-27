#!/usr/bin/env bash
set -euo pipefail

PIN=736aded65c8e2e9d652cf595fca248734483a877
DINGHY=92f17b28f2d05f2f78fd1b160b58475d518902c8
TC_SHA=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
PHASE_SHA=ff0e6aff91da9af49bbfe45b2af08401b89fafa0
RECEIPT_SHA=7359337559af4d673038320a0b1eff666c74ef2f
ROOT="$GITHUB_WORKSPACE"
RES="$RUNNER_TEMP/legacy-results"
mkdir -p "$RES"

git init -q "$RUNNER_TEMP/dinghy"
git -C "$RUNNER_TEMP/dinghy" remote add origin https://github.com/zvenson/dinghy.git
git -C "$RUNNER_TEMP/dinghy" fetch --depth=1 origin "$DINGHY"
git -C "$RUNNER_TEMP/dinghy" checkout --detach FETCH_HEAD
curl -fL --retry 2 --max-time 120 -o "$RUNNER_TEMP/pi32v2.tar.xz" https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-linux-x64.tar.xz
printf "%s  %s\n" "$TC_SHA" "$RUNNER_TEMP/pi32v2.tar.xz" | sha256sum -c -

rustup toolchain install 1.95.0 --profile minimal
EMU="$RUNNER_TEMP/fm1-emu-pin"
git init -q "$EMU"
git -C "$EMU" remote add origin https://github.com/joakimeriksson/fm1-emu.git
git -C "$EMU" fetch --depth=1 origin "$PIN"
git -C "$EMU" checkout --detach FETCH_HEAD
test "$(git -C "$EMU" rev-parse HEAD)" = "$PIN"
rustup run 1.95.0 cargo build --release -p fm1-emu --manifest-path "$EMU/Cargo.toml"
E="$EMU/target/release/fm1-emu"

build_image() {
  name="$1"; sha="$2"; exp="$3"
  checkout="$RUNNER_TEMP/repo-$name"
  objects="$RUNNER_TEMP/$name-objects"
  image="$RUNNER_TEMP/$name.xip.bin"
  git init -q "$checkout"
  git -C "$checkout" remote add origin https://github.com/techrote/FM-1-MHAC.git
  git -C "$checkout" fetch --depth=1 origin "$sha"
  git -C "$checkout" checkout --detach FETCH_HEAD
  test "$(git -C "$checkout" rev-parse HEAD)" = "$sha"
  cd "$checkout/$exp"
  sh qualify_target.sh "$RUNNER_TEMP/dinghy" "$RUNNER_TEMP/pi32v2.tar.xz" "$objects"
  sh qualify_link.sh "$RUNNER_TEMP/dinghy" "$RUNNER_TEMP/pi32v2.tar.xz" "$objects"
  python3 "$ROOT/emulator-qualification-001/elf_to_xip.py" "$objects/candidate.elf" "$image" | tee "$RES/$name-xip.json"
  sha256sum "$objects/candidate.elf" "$image" | tee "$RES/$name-hashes.txt"
}

run_case() {
  name="$1"; image="$2"; keys="$3"; part="$4"; ms="$5"
  wav="$RES/$name.wav"
  FM1_LCD_TIMED=1 /usr/bin/time -v -o "$RES/$name.time.txt" "$E" --bin "$image" --entry 0x02000120 --ms "$ms" --keys "$keys" --flash-chip "$part" --wav "$wav" --quiet
  python3 "$ROOT/emulator-qualification-001/analyze_wav.py" "$wav" --require-audio --silent-tail-ms 500 | tee "$RES/$name.json"
}

build_image phase-debt "$PHASE_SHA" experiments/phase-debt-001
PHASE_IMG="$RUNNER_TEMP/phase-debt.xip.bin"
PHASE_BASE="300-400:N3,1200-1300:PLAY,3800-3900:HOME"
PHASE_MOVING="300-400:N3,500-560:SCL,650-710:SCL,1200-1300:PLAY,3800-3900:HOME"
run_case phase-stagger-puya "$PHASE_IMG" "$PHASE_BASE" p25q80 4700
run_case phase-stagger-uc25 "$PHASE_IMG" "$PHASE_BASE" uc25hq80 4700
run_case phase-moving-puya "$PHASE_IMG" "$PHASE_MOVING" p25q80 4700
cmp "$RES/phase-stagger-puya.wav" "$RES/phase-stagger-uc25.wav"
if cmp -s "$RES/phase-stagger-puya.wav" "$RES/phase-moving-puya.wav"; then echo "HOLD: Phase Debt mode change did not alter PCM" >&2; exit 1; fi

build_image receipt-loom "$RECEIPT_SHA" experiments/receipt-loom-003
RECEIPT_IMG="$RUNNER_TEMP/receipt-loom.xip.bin"
RECEIPT_CLEAN="300-400:N26,1600-1700:PLAY,3900-4000:HOME"
RECEIPT_TAGGED="300-400:N26,500-560:SCL,650-710:SCL,800-860:SCL,950-1010:SCL,1100-1160:SCL,1600-1700:PLAY,3900-4000:HOME"
run_case receipt-clean-puya "$RECEIPT_IMG" "$RECEIPT_CLEAN" p25q80 4800
run_case receipt-clean-uc25 "$RECEIPT_IMG" "$RECEIPT_CLEAN" uc25hq80 4800
run_case receipt-tagged-puya "$RECEIPT_IMG" "$RECEIPT_TAGGED" p25q80 4800
cmp "$RES/receipt-clean-puya.wav" "$RES/receipt-clean-uc25.wav"
if cmp -s "$RES/receipt-clean-puya.wav" "$RES/receipt-tagged-puya.wav"; then echo "HOLD: Receipt Loom tagged mode did not alter PCM" >&2; exit 1; fi

echo "legacy_matrix=PASS phase=$PHASE_SHA receipt=$RECEIPT_SHA emulator=$PIN" | tee "$RES/summary.txt"
