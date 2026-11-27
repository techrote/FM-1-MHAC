$ErrorActionPreference = "Stop"
$pin = "736aded65c8e2e9d652cf595fca248734483a877"
$dinghyPin = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
$root = $env:GITHUB_WORKSPACE
$emu = Join-Path $env:RUNNER_TEMP "fm1-emu-pin"
$d = Join-Path $env:RUNNER_TEMP "dinghy-source"
$results = Join-Path $root "win-results"

git init -q $d
git -C $d remote add origin https://github.com/zvenson/dinghy.git
git -C $d fetch --depth=1 origin $dinghyPin
git -C $d checkout --detach FETCH_HEAD
if ((git -C $d rev-parse HEAD).Trim() -ne $dinghyPin) { throw "wrong Dinghy source pin" }

$imageFile = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "scope-weave.xip.bin" | Select-Object -First 1
if (-not $imageFile) { throw "scope-weave.xip.bin handoff missing" }
$out = Join-Path $root "FM1-MHAC-emulator-evaluator-windows-x64"
$source = Join-Path $out "source"
New-Item -ItemType Directory -Force $out,$source | Out-Null
Copy-Item (Join-Path $emu "target\release\fm1-live.exe") $out
Copy-Item (Join-Path $emu "target\release\fm1-emu.exe") $out
Copy-Item $imageFile.FullName (Join-Path $out "scope-weave.xip.bin")
Copy-Item (Join-Path $root "emulator-qualification-001\README.md") (Join-Path $out "README.md")
Copy-Item (Join-Path $emu "LICENSE") (Join-Path $out "LICENSE-fm1-emu-MIT.txt")
Copy-Item (Join-Path $d "LICENSE") (Join-Path $out "LICENSE-dinghy-GPL-3.0.txt")
foreach ($f in @("app.c","scope_weave.h","qualify_target.sh","qualify_link.sh")) {
  Copy-Item (Join-Path $root ("experiments\scope-weave-005\" + $f)) $source
}
Copy-Item (Join-Path $root "emulator-qualification-001\elf_to_xip.py") $source
Copy-Item (Join-Path $root "emulator-qualification-001\analyze_wav.py") $source
git -C $d archive --format=zip --output=(Join-Path $source ("dinghy-" + $dinghyPin + ".zip")) $dinghyPin
git -C $emu archive --format=zip --output=(Join-Path $source ("fm1-emu-" + $pin + ".zip")) $pin

$run = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "fm1-live.exe --bin scope-weave.xip.bin --entry 0x02000120 --midi all --flash-chip p25q80"
)
$run | Set-Content -Encoding ascii (Join-Path $out "run-scope-weave.cmd")
$runUc = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "fm1-live.exe --bin scope-weave.xip.bin --entry 0x02000120 --midi all --flash-chip uc25hq80"
)
$runUc | Set-Content -Encoding ascii (Join-Path $out "run-scope-weave-uc25hq80.cmd")
$bench = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "set FM1_BENCH_KEYS=600:N3,700:N3^,900:PLAY,1000:PLAY^,3600:HOME,3700:HOME^",
  "set FM1_LCD_TIMED=1",
  "fm1-live.exe --bin scope-weave.xip.bin --entry 0x02000120 --bench 4500 --midi none --flash-chip p25q80",
  "pause"
)
$bench | Set-Content -Encoding ascii (Join-Path $out "benchmark-scope-weave.cmd")

$prov = @(
  "EMULATOR-QUALIFICATION-001",
  "fm1-emu pin: $pin",
  "Dinghy source pin: $dinghyPin",
  "FM-1-MHAC branch checkout: $env:GITHUB_SHA",
  "",
  "scope-weave.xip.bin is a bare XIP image for virtual execution only.",
  "No .fwsc, updater, flash writer, recovery image, or physical-install tool is included.",
  "The separate physical-install HOLD is therefore unchanged.",
  "",
  "Corresponding source for the GPL-derived target image is bundled under source\.",
  "The exact emulator source archive and MIT license are bundled as well."
)
$prov | Set-Content -Encoding utf8 (Join-Path $out "PROVENANCE.txt")

$zip = Join-Path $root "FM1-MHAC-emulator-evaluator-windows-x64.zip"
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"evaluator_zip_sha256=$hash" | Tee-Object -FilePath (Join-Path $results "evaluator-sha256.txt")
"evaluator_zip_bytes=$((Get-Item $zip).Length)" | Tee-Object -Append -FilePath (Join-Path $results "evaluator-sha256.txt")
