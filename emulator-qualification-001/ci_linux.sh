#!/usr/bin/env bash
set -euo pipefail

PIN=736aded65c8e2e9d652cf595fca248734483a877
CURRENT=69cb1ef46d86a2776112cc9279773ded3ffa293b
DINGHY=92f17b28f2d05f2f78fd1b160b58475d518902c8
TC_SHA=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
ROOT="$GITHUB_WORKSPACE"
RES="$RUNNER_TEMP/results"
mkdir -p "$RES"

git init -q "$RUNNER_TEMP/dinghy"
git -C "$RUNNER_TEMP/dinghy" remote add origin https://github.com/zvenson/dinghy.git
git -C "$RUNNER_TEMP/dinghy" fetch --depth=1 origin "$DINGHY"
git -C "$RUNNER_TEMP/dinghy" checkout --detach FETCH_HEAD
curl -fL --retry 2 --max-time 120 -o "$RUNNER_TEMP/pi32v2.tar.xz" \
  https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-linux-x64.tar.xz
printf '%s  %s\n' "$TC_SHA" "$RUNNER_TEMP/pi32v2.tar.xz" | sha256sum -c -

cd "$ROOT/experiments/scope-weave-005"
sh qualify_target.sh "$RUNNER_TEMP/dinghy" "$RUNNER_TEMP/pi32v2.tar.xz" "$RUNNER_TEMP/scope-objects"
sh qualify_link.sh "$RUNNER_TEMP/dinghy" "$RUNNER_TEMP/pi32v2.tar.xz" "$RUNNER_TEMP/scope-objects"
python3 "$ROOT/emulator-qualification-001/elf_to_xip.py" \
  "$RUNNER_TEMP/scope-objects/candidate.elf" "$RUNNER_TEMP/scope-weave.xip.bin" \
  | tee "$RUNNER_TEMP/xip-receipt.json"
sha256sum "$RUNNER_TEMP/scope-objects/candidate.elf" "$RUNNER_TEMP/scope-weave.xip.bin"

mkdir "$RUNNER_TEMP/audit-toolchain"
tar -xJf "$RUNNER_TEMP/pi32v2.tar.xz" -C "$RUNNER_TEMP/audit-toolchain" --strip-components=1
set +e
python3 audit_elf.py "$RUNNER_TEMP/dinghy" "$RUNNER_TEMP/audit-toolchain/bin" \
  "$RUNNER_TEMP/scope-objects" "$RUNNER_TEMP/scope-objects" > "$RUNNER_TEMP/inherited-audit.log" 2>&1
AUDIT_RC=$?
set -e
echo "inherited_audit_exit=$AUDIT_RC" >> "$RUNNER_TEMP/inherited-audit.log"
cat "$RUNNER_TEMP/inherited-audit.log"

rustup toolchain install 1.95.0 --profile minimal
build_emu() {
  ref="$1"; dir="$2"
  git init -q "$dir"
  git -C "$dir" remote add origin https://github.com/joakimeriksson/fm1-emu.git
  git -C "$dir" fetch --depth=1 origin "$ref"
  git -C "$dir" checkout --detach FETCH_HEAD
  test "$(git -C "$dir" rev-parse HEAD)" = "$ref"
  rustup run 1.95.0 cargo build --release -p fm1-emu --manifest-path "$dir/Cargo.toml"
}
build_emu "$PIN" "$RUNNER_TEMP/fm1-emu-pin"
build_emu "$CURRENT" "$RUNNER_TEMP/fm1-emu-current"

run_case() {
  exe="$1"; preset="$2"; part="$3"; out="$4"; run_dir="$5"
  mkdir -p "$run_dir/work"
  keys="600-700:N$preset,900-1000:PLAY,3600-3700:HOME"
  name="$RES/$out"
  (
    cd "$run_dir"
    FM1_LCD_TIMED=1 /usr/bin/time -v -o "$name.time.txt" \
      "$exe" --bin "$RUNNER_TEMP/scope-weave.xip.bin" --entry 0x02000120 --ms 4500 \
      --keys "$keys" --flash-chip "$part" --wav "$name.wav" --quiet
  )
  python3 "$ROOT/emulator-qualification-001/analyze_wav.py" "$name.wav" \
    --require-audio --silent-tail-ms 500 | tee "$name.json"
}

PIN_EXE="$RUNNER_TEMP/fm1-emu-pin/target/release/fm1-emu"
CUR_EXE="$RUNNER_TEMP/fm1-emu-current/target/release/fm1-emu"
run_case "$PIN_EXE" 3 p25q80 pin-p3-puya "$RUNNER_TEMP/run-pin-p3"
run_case "$PIN_EXE" 9 p25q80 pin-p9-puya "$RUNNER_TEMP/run-pin-p9"
run_case "$PIN_EXE" 3 uc25hq80 pin-p3-uc25 "$RUNNER_TEMP/run-pin-uc"
cmp "$RES/pin-p3-puya.wav" "$RES/pin-p3-uc25.wav"
if cmp -s "$RES/pin-p3-puya.wav" "$RES/pin-p9-puya.wav"; then
  echo "HOLD: ordered presets 3 and 9 unexpectedly alias" >&2
  exit 1
fi

run_case "$CUR_EXE" 3 p25q80 current-p3-puya "$RUNNER_TEMP/run-current"
cmp "$RES/pin-p3-puya.wav" "$RES/current-p3-puya.wav"
echo "pin_vs_current_source_pcm=byte-identical" | tee "$RES/source-ab.txt"

mkdir "$RUNNER_TEMP/release"
curl -fL --retry 2 --max-time 120 -o "$RUNNER_TEMP/release.tar.gz" \
  https://github.com/joakimeriksson/fm1-emu/releases/download/v0.5.1/fm1-emu-0.5.1-linux-x86_64.tar.gz
printf '%s  %s\n' 2b4b5cc89bc42edc91dc64830b912633bde35b5fb8a66c173341ed9a851917b7 "$RUNNER_TEMP/release.tar.gz" | sha256sum -c -
tar -xzf "$RUNNER_TEMP/release.tar.gz" -C "$RUNNER_TEMP/release"
REL_EXE="$(find "$RUNNER_TEMP/release" -type f -name fm1-emu -perm -111 | head -1)"
test -x "$REL_EXE"
"$REL_EXE" --version | tee "$RES/release-version.txt"
run_case "$REL_EXE" 3 p25q80 release-p3-puya "$RUNNER_TEMP/run-release"
if cmp -s "$RES/pin-p3-puya.wav" "$RES/release-p3-puya.wav"; then
  echo "release_vs_pin_pcm=byte-identical" | tee "$RES/release-ab.txt"
else
  echo "release_vs_pin_pcm=differs (release predates qualification pin)" | tee "$RES/release-ab.txt"
fi
