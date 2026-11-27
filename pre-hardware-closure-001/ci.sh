#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
TMP="${RUNNER_TEMP:-/tmp/fm1-pre-hw}"
EVID="$TMP/pre-hardware-closure-evidence"
mkdir -p "$EVID"

PIN=92f17b28f2d05f2f78fd1b160b58475d518902c8
TC_SHA=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
TOOLCHAIN="$TMP/pi32v2.tar.xz"
DINGHY="$TMP/dinghy"
TC="$TMP/toolchain/bin"

python3 "$ROOT/pre-hardware-closure-001/table_aware_screen.py" --selftest | tee "$EVID/table-selftest.txt"

pwsh -NoLogo -NoProfile -Command '
  $tokens=$null; $errors=$null;
  [System.Management.Automation.Language.Parser]::ParseFile(
    "'"$ROOT"'/pre-hardware-closure-001/hardware-arrival/collect-arrival.ps1",
    [ref]$tokens,[ref]$errors) | Out-Null;
  if ($errors.Count) { $errors | Format-List | Out-String | Write-Error; exit 1 }
  "collect-arrival.ps1 syntax=PASS"
' | tee "$EVID/arrival-script-syntax.txt"

git init -q "$DINGHY"
git -C "$DINGHY" remote add origin https://github.com/zvenson/dinghy.git
git -C "$DINGHY" fetch --depth=1 origin "$PIN"
git -C "$DINGHY" checkout --detach FETCH_HEAD
test "$(git -C "$DINGHY" rev-parse HEAD)" = "$PIN"

curl -fL --retry 2 --max-time 120 -o "$TOOLCHAIN"   https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-linux-x64.tar.xz
echo "$TC_SHA  $TOOLCHAIN" | sha256sum -c -
mkdir "$TMP/toolchain"
tar -xJf "$TOOLCHAIN" -C "$TMP/toolchain" --strip-components=1

fetch_exact() {
  local name="$1" sha="$2"
  local repo="$TMP/repo-$name"
  git init -q "$repo"
  git -C "$repo" remote add origin https://github.com/techrote/FM-1-MHAC.git
  git -C "$repo" fetch --depth=1 origin "$sha"
  git -C "$repo" checkout --detach FETCH_HEAD
  test "$(git -C "$repo" rev-parse HEAD)" = "$sha"
}

build_pair() {
  local name="$1" sha="$2" exp="$3" expected_candidate="$4"
  local repo="$TMP/repo-$name"
  fetch_exact "$name" "$sha"
  for pass in first repeat; do
    local out="$TMP/$name-$pass"
    (cd "$repo/$exp" &&       sh qualify_target.sh "$DINGHY" "$TOOLCHAIN" "$out" &&       sh qualify_link.sh "$DINGHY" "$TOOLCHAIN" "$out")
  done
  local got
  got="$(sha256sum "$TMP/$name-first/candidate.elf" | cut -d' ' -f1)"
  test "$got" = "$expected_candidate"
  cmp "$TMP/$name-first/candidate.elf" "$TMP/$name-repeat/candidate.elf"
  cmp "$TMP/$name-first/baseline.elf" "$TMP/$name-repeat/baseline.elf"

  set +e
  (cd "$repo/$exp" && python3 audit_elf.py "$DINGHY" "$TC"       "$TMP/$name-first" "$TMP/$name-repeat")       >"$EVID/$name-legacy-audit.log" 2>&1
  local rc=$?
  set -e
  test "$rc" -ne 0
  grep -F 'pinned_mmio_baseline_candidate_negative_control=PASS' "$EVID/$name-legacy-audit.log"
  grep -F 'baseline_independent_ELF_rebuild=PASS' "$EVID/$name-legacy-audit.log"
  grep -F 'candidate_independent_ELF_rebuild=PASS' "$EVID/$name-legacy-audit.log"
  grep -F 'LLVM screen HOLD:' "$EVID/$name-legacy-audit.log"

  python3 "$ROOT/pre-hardware-closure-001/table_aware_screen.py" --toolchain "$TC"     "$TMP/$name-first/baseline.elf" "$TMP/$name-first/candidate.elf"     "$TMP/$name-repeat/baseline.elf" "$TMP/$name-repeat/candidate.elf"     | tee "$EVID/$name-table-aware.log"
}

build_pair phase ff0e6aff91da9af49bbfe45b2af08401b89fafa0   experiments/phase-debt-001   0055c9cf1e7cd1d2299963bfabca687bbe34b1bbd574eda9079a1f3b63abe9fe

build_pair receipt 7359337559af4d673038320a0b1eff666c74ef2f   experiments/receipt-loom-003   b5039aab60cf05cfad1424722d0ba60f94abcce8c645cea243a924d6cf291596

build_pair scope b8ce089a770945bd19d03204c536b85dbfced6af   experiments/scope-weave-005   4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac

SCOPE="$TMP/repo-scope/experiments/scope-weave-005"
node "$SCOPE/direct_object.mjs" --selftest | tee "$EVID/direct-object-selftest.txt"
DM="$TMP/direct-map"
mkdir "$DM"
cp "$TMP/scope-first/baseline.o" "$TMP/scope-first/candidate.o" "$DM/"
python3 - "$SCOPE/qualify_link.sh" "$DM/link.sh" <<'PY'
import sys
from pathlib import Path
src=Path(sys.argv[1]).read_text()
old='-o "$OUT/$n.elf"'
assert src.count(old)==1
Path(sys.argv[2]).write_text(src.replace(old,'-Map="$OUT/$n.map" '+old))
PY
(cd "$SCOPE" && sh "$DM/link.sh" "$DINGHY" "$TOOLCHAIN" "$DM")
node "$SCOPE/direct_object.mjs" baseline "$DM/baseline.o"   "$TMP/scope-first/baseline.elf" "$DM/baseline.elf" "$DM/baseline.map"   | tee "$EVID/direct-object-baseline.json"
node "$SCOPE/direct_object.mjs" scope "$DM/candidate.o"   "$TMP/scope-first/candidate.elf" "$DM/candidate.elf" "$DM/candidate.map"   | tee "$EVID/direct-object-scope.json"

python3 "$ROOT/pre-hardware-closure-001/provenance_probe.py"   "$DINGHY" "$TOOLCHAIN" "$SCOPE" | tee "$EVID/provenance-probe.log"
grep -F 'provenance_probe_complete=PASS' "$EVID/provenance-probe.log"

python3 - "$EVID" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
summary={"mission":"PRE-HARDWARE-CLOSURE-001","legacy_audit_expected_fail":{},"table_aware":{},"provenance":[]}
for name in ("phase","receipt","scope"):
    legacy=(p/f"{name}-legacy-audit.log").read_text()
    summary["legacy_audit_expected_fail"][name]="LLVM screen HOLD:" in legacy
    rows=[]
    for line in (p/f"{name}-table-aware.log").read_text().splitlines():
        if line.startswith("table_aware_screen "):
            rows.append(json.loads(line.split(" ",1)[1]))
    assert rows and all(r["status"]=="PASS" for r in rows)
    summary["table_aware"][name]=rows
for line in (p/"provenance-probe.log").read_text().splitlines():
    if line.startswith("provenance_probe "):
        summary["provenance"].append(json.loads(line.split(" ",1)[1]))
assert len(summary["provenance"])==2
assert all(x["direct_repeat_exact"] for x in summary["provenance"])
(p/"closure-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({
    "table_aware_pass": {k: len(v) for k,v in summary["table_aware"].items()},
    "provenance_status": {x["variant"]:x["status"] for x in summary["provenance"]},
},sort_keys=True))
PY

sha256sum "$ROOT/pre-hardware-closure-001/"*.py   "$ROOT/pre-hardware-closure-001/hardware-arrival/"*   "$ROOT/pre-hardware-closure-001/READINESS.md"   > "$EVID/closure-source-sha256.txt"

echo "PRE-HARDWARE-CLOSURE-001 CI PASS"
