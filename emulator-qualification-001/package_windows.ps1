$ErrorActionPreference = "Stop"
$pin = "736aded65c8e2e9d652cf595fca248734483a877"
$dinghyPin = "92f17b28f2d05f2f78fd1b160b58475d518902c8"
$phaseSha = "ff0e6aff91da9af49bbfe45b2af08401b89fafa0"
$receiptSha = "7359337559af4d673038320a0b1eff666c74ef2f"
$root = $env:GITHUB_WORKSPACE
$emu = Join-Path $env:RUNNER_TEMP "fm1-emu-pin"
$d = Join-Path $env:RUNNER_TEMP "dinghy-source"
$legacy = Join-Path $env:RUNNER_TEMP "fm1-mhac-legacy-source"
$results = Join-Path $root "win-results"

git init -q $d
git -C $d remote add origin https://github.com/zvenson/dinghy.git
git -C $d fetch --depth=1 origin $dinghyPin
git -C $d checkout --detach FETCH_HEAD
if ((git -C $d rev-parse HEAD).Trim() -ne $dinghyPin) { throw "wrong Dinghy source pin" }

$imageFile = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "scope-weave.xip.bin" | Select-Object -First 1
$phaseImage = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "phase-debt.xip.bin" | Select-Object -First 1
$receiptImage = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "receipt-loom.xip.bin" | Select-Object -First 1
if (-not $imageFile -or -not $phaseImage -or -not $receiptImage) { throw "one or more XIP handoffs missing" }
$out = Join-Path $root "FM1-MHAC-emulator-evaluator-windows-x64"
$source = Join-Path $out "source"
$demos = Join-Path $out "demos"
New-Item -ItemType Directory -Force $out,$source,$demos | Out-Null
Copy-Item (Join-Path $emu "target\release\fm1-live.exe") $out
Copy-Item (Join-Path $emu "target\release\fm1-emu.exe") $out
Copy-Item $imageFile.FullName (Join-Path $out "scope-weave.xip.bin")
Copy-Item $phaseImage.FullName (Join-Path $out "phase-debt.xip.bin")
Copy-Item $receiptImage.FullName (Join-Path $out "receipt-loom.xip.bin")
foreach ($demo in @("p3.wav","p9.wav","phase-debt.wav","receipt-loom.wav")) {
  $demoPath = Join-Path $results $demo
  if (-not (Test-Path $demoPath)) { throw "missing demo WAV $demo" }
  Copy-Item $demoPath $demos
}
Copy-Item (Join-Path $root "emulator-qualification-001\README.md") (Join-Path $out "README.md")
Copy-Item (Join-Path $emu "LICENSE") (Join-Path $out "LICENSE-fm1-emu-MIT.txt")
Copy-Item (Join-Path $d "LICENSE") (Join-Path $out "LICENSE-dinghy-GPL-3.0.txt")
foreach ($f in @("app.c","scope_weave.h","qualify_target.sh","qualify_link.sh")) {
  Copy-Item (Join-Path $root ("experiments\scope-weave-005\" + $f)) $source
}
Copy-Item (Join-Path $root "emulator-qualification-001\elf_to_xip.py") $source
Copy-Item (Join-Path $root "emulator-qualification-001\analyze_wav.py") $source
$dinghyArchive = Join-Path $source ("dinghy-" + $dinghyPin + ".zip")
$emuArchive = Join-Path $source ("fm1-emu-" + $pin + ".zip")
git -C $d archive --format=zip -o $dinghyArchive $dinghyPin
if ($LASTEXITCODE -ne 0) { throw "Dinghy source archive failed" }
git -C $emu archive --format=zip -o $emuArchive $pin
if ($LASTEXITCODE -ne 0) { throw "emulator source archive failed" }
git init -q $legacy
git -C $legacy remote add origin https://github.com/techrote/FM-1-MHAC.git
git -C $legacy fetch --depth=1 origin $phaseSha
git -C $legacy fetch --depth=1 origin $receiptSha
$phaseArchive = Join-Path $source ("FM1-MHAC-phase-debt-" + $phaseSha + ".zip")
$receiptArchive = Join-Path $source ("FM1-MHAC-receipt-loom-" + $receiptSha + ".zip")
git -C $legacy archive --format=zip -o $phaseArchive $phaseSha experiments/phase-debt-001
if ($LASTEXITCODE -ne 0) { throw "Phase Debt source archive failed" }
git -C $legacy archive --format=zip -o $receiptArchive $receiptSha experiments/receipt-loom-003
if ($LASTEXITCODE -ne 0) { throw "Receipt Loom source archive failed" }

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
$phaseRun = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "fm1-live.exe --bin phase-debt.xip.bin --entry 0x02000120 --midi all --flash-chip p25q80"
)
$phaseRun | Set-Content -Encoding ascii (Join-Path $out "run-phase-debt.cmd")
$receiptRun = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "fm1-live.exe --bin receipt-loom.xip.bin --entry 0x02000120 --midi all --flash-chip p25q80"
)
$receiptRun | Set-Content -Encoding ascii (Join-Path $out "run-receipt-loom.cmd")
$bench = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  "set FM1_BENCH_KEYS=600:N3,700:N3^,900:PLAY,1000:PLAY^,3600:HOME,3700:HOME^",
  "set FM1_LCD_TIMED=1",
  "fm1-live.exe --bin scope-weave.xip.bin --entry 0x02000120 --bench 4500 --midi none --flash-chip p25q80",
  "pause"
)
$bench | Set-Content -Encoding ascii (Join-Path $out "benchmark-scope-weave.cmd")
$chooser = @(
  "@echo off",
  "cd /d `"%~dp0`"",
  ":menu",
  "cls",
  "echo FM1-MHAC virtual instruments",
  "echo   1. Phase Debt",
  "echo   2. Receipt Loom",
  "echo   3. Scope Weave",
  "echo   4. Scope Weave (UC25HQ80 flash model)",
  "echo   Q. Quit",
  "choice /c 1234Q /n /m `"Select: `"" ,
  "if errorlevel 5 exit /b 0",
  "if errorlevel 4 call run-scope-weave-uc25hq80.cmd & goto menu",
  "if errorlevel 3 call run-scope-weave.cmd & goto menu",
  "if errorlevel 2 call run-receipt-loom.cmd & goto menu",
  "if errorlevel 1 call run-phase-debt.cmd & goto menu"
)
$chooser | Set-Content -Encoding ascii (Join-Path $out "choose-instrument.cmd")

$prov = @(
  "EMULATOR-QUALIFICATION-001",
  "fm1-emu pin: $pin",
  "Dinghy source pin: $dinghyPin",
  "Phase Debt source head: $phaseSha",
  "Receipt Loom source head: $receiptSha",
  "FM-1-MHAC branch checkout: $env:GITHUB_SHA",
  "",
  "scope-weave.xip.bin, phase-debt.xip.bin and receipt-loom.xip.bin are bare XIP images for virtual execution only.",
  "No .fwsc, updater, flash writer, recovery image, or physical-install tool is included.",
  "The separate physical-install HOLD is therefore unchanged.",
  "This is an owner-directed evaluator artifact, not a public firmware release.",
  "Confirm the original FM1-MHAC code licensing/redistribution decision before broader redistribution.",
  "",
  "Corresponding source for all GPL-derived target images is bundled under source\.",
  "The exact emulator source archive and MIT license are bundled as well."
)
$prov | Set-Content -Encoding utf8 (Join-Path $out "PROVENANCE.txt")

$zip = Join-Path $root "FM1-MHAC-emulator-evaluator-windows-x64.zip"
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"evaluator_zip_sha256=$hash" | Tee-Object -FilePath (Join-Path $results "evaluator-sha256.txt")
"evaluator_zip_bytes=$((Get-Item $zip).Length)" | Tee-Object -Append -FilePath (Join-Path $results "evaluator-sha256.txt")
