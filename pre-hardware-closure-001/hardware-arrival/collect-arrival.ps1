param(
    [string]$OutDir = ".\fm1-arrival-evidence",
    [string[]]$ReferenceFile = @()
)
$ErrorActionPreference = "Stop"

# PRE-HARDWARE-CLOSURE-001: read-only arrival evidence.
# This script never opens a device handle, sends USB/MIDI data, invokes an updater, or writes firmware.

if (-not $IsWindows) { throw "This collector is Windows-only." }

New-Item -ItemType Directory -Force $OutDir | Out-Null
$root = (Resolve-Path $OutDir).Path
$stamp = (Get-Date).ToUniversalTime().ToString("o")

$os = Get-CimInstance Win32_OperatingSystem |
    Select-Object Caption, Version, BuildNumber, OSArchitecture
$os | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $root "windows.json")

$pnp = Get-PnpDevice -PresentOnly | ForEach-Object {
    [pscustomobject]@{
        Status       = $_.Status
        Class        = $_.Class
        FriendlyName = $_.FriendlyName
        InstanceId   = $_.InstanceId
        Manufacturer = $_.Manufacturer
    }
} | Where-Object {
    (($_.FriendlyName, $_.InstanceId, $_.Manufacturer) -join " ") -match "(?i)M-VAVE|FM-1|JieLi|Jieli|USB|MIDI|Audio"
}
$pnp | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $root "pnp-relevant.json")

Get-CimInstance Win32_SoundDevice |
    Select-Object Name, Manufacturer, Status, PNPDeviceID |
    ConvertTo-Json -Depth 4 |
    Set-Content -Encoding utf8 (Join-Path $root "sound-devices.json")

$refs = foreach ($f in $ReferenceFile) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "Reference file not found: $f" }
    $item = Get-Item -LiteralPath $f
    [pscustomobject]@{
        FileName = $item.Name
        Bytes = $item.Length
        SHA256 = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$refs | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $root "reference-files.json")

$manifest = [ordered]@{
    Mission = "FM1-MHAC PRE-HARDWARE-CLOSURE-001"
    CollectedUTC = $stamp
    ReadOnlyCollector = $true
    DeviceWritesAttempted = $false
    ReferenceFileCount = @($refs).Count
    PrivacyNotice = "PnP InstanceId fields can contain device serial identifiers. Review/redact before publishing."
    NextGate = "Do not install experimental firmware until exact unit identity, independent recovery/full-backup evidence and rollback plan are accepted."
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $root "MANIFEST.json")

Get-ChildItem $root -File | Sort-Object Name | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $_.Name
} | Set-Content -Encoding ascii (Join-Path $root "SHA256SUMS.txt")

Write-Host "Read-only FM-1 arrival evidence written to $root"
Write-Host "Review pnp-relevant.json for serial identifiers before sharing."
