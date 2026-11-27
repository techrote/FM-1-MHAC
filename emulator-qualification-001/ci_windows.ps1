$ErrorActionPreference = "Stop"
$pin = "736aded65c8e2e9d652cf595fca248734483a877"
$root = $env:GITHUB_WORKSPACE
$emu = Join-Path $env:RUNNER_TEMP "fm1-emu-pin"
$results = Join-Path $root "win-results"
New-Item -ItemType Directory -Force $results | Out-Null

rustup toolchain install 1.95.0 --profile minimal
git init -q $emu
git -C $emu remote add origin https://github.com/joakimeriksson/fm1-emu.git
git -C $emu fetch --depth=1 origin $pin
git -C $emu checkout --detach FETCH_HEAD
if ((git -C $emu rev-parse HEAD).Trim() -ne $pin) { throw "wrong emulator pin" }
rustup run 1.95.0 cargo build --release -p fm1-emu -p fm1-live --manifest-path (Join-Path $emu "Cargo.toml")
$emuExe = Join-Path $emu "target\release\fm1-emu.exe"
$liveExe = Join-Path $emu "target\release\fm1-live.exe"
& $emuExe --version | Tee-Object -FilePath (Join-Path $results "fm1-emu-version.txt")
if ($LASTEXITCODE -ne 0) { throw "fm1-emu --version failed" }

$imageFile = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "scope-weave.xip.bin" | Select-Object -First 1
if (-not $imageFile) { throw "scope-weave.xip.bin handoff missing" }
$image = $imageFile.FullName
$env:FM1_LCD_TIMED = "1"
foreach ($preset in 3,9) {
  $wav = Join-Path $results ("p{0}.wav" -f $preset)
  $json = Join-Path $results ("p{0}.json" -f $preset)
  $keys = "600-700:N$($preset),900-1000:PLAY,3600-3700:HOME"
  & $emuExe --bin $image --entry 0x02000120 --ms 4500 --keys $keys --flash-chip p25q80 --wav $wav --quiet
  if ($LASTEXITCODE -ne 0) { throw "fm1-emu preset $preset failed" }
  python (Join-Path $root "emulator-qualification-001\analyze_wav.py") $wav --require-audio --silent-tail-ms 500 | Tee-Object -FilePath $json
  if ($LASTEXITCODE -ne 0) { throw "WAV analysis preset $preset failed" }
}
$h3 = (Get-FileHash (Join-Path $results "p3.wav") -Algorithm SHA256).Hash
$h9 = (Get-FileHash (Join-Path $results "p9.wav") -Algorithm SHA256).Hash
if ($h3 -eq $h9) { throw "ordered preset 3 and preset 9 unexpectedly alias" }
"windows_ordered_pcm_distinct=PASS p3=$h3 p9=$h9" | Tee-Object -FilePath (Join-Path $results "ordered-distinction.txt")

$phaseFile = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "phase-debt.xip.bin" | Select-Object -First 1
$receiptFile = Get-ChildItem (Join-Path $root "handoff") -Recurse -Filter "receipt-loom.xip.bin" | Select-Object -First 1
if (-not $phaseFile -or -not $receiptFile) { throw "legacy XIP handoff missing" }
$legacyCases = @(
  @{ Name="phase-debt"; Image=$phaseFile.FullName; Ms="4700"; Keys="300-400:N3,1200-1300:PLAY,3800-3900:HOME" },
  @{ Name="receipt-loom"; Image=$receiptFile.FullName; Ms="4800"; Keys="300-400:N26,500-560:SCL,650-710:SCL,800-860:SCL,950-1010:SCL,1100-1160:SCL,1600-1700:PLAY,3900-4000:HOME" }
)
foreach ($case in $legacyCases) {
  $wav = Join-Path $results ($case.Name + ".wav")
  & $emuExe --bin $case.Image --entry 0x02000120 --ms $case.Ms --keys $case.Keys --flash-chip p25q80 --wav $wav --quiet
  if ($LASTEXITCODE -ne 0) { throw ("fm1-emu " + $case.Name + " failed") }
  python (Join-Path $root "emulator-qualification-001\analyze_wav.py") $wav --require-audio --silent-tail-ms 500 | Tee-Object -FilePath (Join-Path $results ($case.Name + ".json"))
  if ($LASTEXITCODE -ne 0) { throw ("WAV analysis " + $case.Name + " failed") }
}
$env:FM1_BENCH_KEYS = "600:N3,700:N3^,900:PLAY,1000:PLAY^,3600:HOME,3700:HOME^"
$stdout = Join-Path $results "fm1-live-bench.stdout.txt"
$stderr = Join-Path $results "fm1-live-bench.stderr.txt"
$benchArgs = @("--bin",$image,"--entry","0x02000120","--bench","4500","--midi","none","--flash-chip","p25q80")
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $liveExe -ArgumentList $benchArgs -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$peak = 0L
while (-not $p.HasExited) {
  Start-Sleep -Milliseconds 50
  try { $p.Refresh(); if ($p.PeakWorkingSet64 -gt $peak) { $peak = $p.PeakWorkingSet64 } } catch {}
}
$p.WaitForExit()
$sw.Stop()
$p.Refresh()
if ($p.ExitCode -ne 0) { Get-Content $stdout; Get-Content $stderr; throw "fm1-live benchmark failed with exit $($p.ExitCode)" }
$receipt = @(
  "wall_ms=$([math]::Round($sw.Elapsed.TotalMilliseconds,1))",
  "cpu_ms=$([math]::Round($p.TotalProcessorTime.TotalMilliseconds,1))",
  "peak_working_set_bytes=$peak",
  "exit_code=$($p.ExitCode)"
)
$receipt | Tee-Object -FilePath (Join-Path $results "fm1-live-process.txt")
Get-Content $stdout
Get-Content $stderr
