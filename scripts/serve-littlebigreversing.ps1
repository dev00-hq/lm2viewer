param(
    [string]$LittleBigReversingRoot,
    [string]$AssetRoot,
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8765,
    [switch]$KeepExisting,
    [switch]$OpenBrowser,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

if (-not $LittleBigReversingRoot) {
    $candidateRoot = Join-Path $RepoRoot "..\littlebigreversing"
    if (Test-Path $candidateRoot) {
        $LittleBigReversingRoot = (Resolve-Path $candidateRoot).Path
    }
}

if (-not $LittleBigReversingRoot -or -not (Test-Path $LittleBigReversingRoot)) {
    throw "LittleBigReversing root not found. Pass -LittleBigReversingRoot D:\path\to\littlebigreversing."
}

if (-not $AssetRoot) {
    $assetRootCandidates = @(
        "<extracted-assets>\Speedrun\Windows",
        "<asset-root>",
        "reference\lba2-classic\Common",
        "reference\lba2-classic\Speedrun\Windows"
    )

    foreach ($relativePath in $assetRootCandidates) {
        $candidate = Join-Path $LittleBigReversingRoot $relativePath
        if (-not (Test-Path $candidate)) {
            continue
        }
        $hqrCount = (Get-ChildItem -Path $candidate -Filter "*.HQR" -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
        if ($hqrCount -gt 0) {
            $AssetRoot = (Resolve-Path $candidate).Path
            break
        }
    }
}

if (-not $AssetRoot -or -not (Test-Path $AssetRoot)) {
    throw "HQR asset root not found. Pass -AssetRoot D:\path\containing\HQRs."
}

$AssetRoot = (Resolve-Path $AssetRoot).Path
$hqrFiles = @(Get-ChildItem -Path $AssetRoot -Filter "*.HQR" -File -Recurse -ErrorAction SilentlyContinue)
if ($hqrFiles.Count -eq 0) {
    throw "No HQR files found under asset root: $AssetRoot"
}

if (-not $KeepExisting -and -not $DryRun) {
    $existingViewers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like "*-m lba2_lm2_viewer.viewer*" }
    foreach ($process in $existingViewers) {
        Write-Host "Stopping existing viewer process $($process.ProcessId)"
        Stop-Process -Id $process.ProcessId -Force
    }
}

$SelectedPort = $Port
while ((Get-NetTCPConnection -LocalPort $SelectedPort -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {
    $SelectedPort += 1
}

$ips = @(
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.InterfaceAlias -notlike "vEthernet*"
        } |
        Sort-Object @{ Expression = { if ($_.InterfaceAlias -eq "Tailscale") { 0 } elseif ($_.InterfaceAlias -like "*Wi-Fi*") { 1 } else { 2 } } }, InterfaceAlias
)

Write-Host "Asset root: $AssetRoot"
Write-Host "HQR files: $($hqrFiles.Count)"
Write-Host "Binding: $HostAddress`:$SelectedPort"
if ($ips.Count -gt 0) {
    Write-Host "Phone URLs:"
    foreach ($ip in $ips) {
        Write-Host "  http://$($ip.IPAddress):$SelectedPort/"
    }
} else {
    Write-Host "Phone URL: no non-loopback IPv4 address found."
}

$arguments = @(
    "-m", "lba2_lm2_viewer.viewer",
    "--host", $HostAddress,
    "--port", "$SelectedPort",
    "--asset-root", $AssetRoot
)
if (-not $OpenBrowser) {
    $arguments += "--no-browser"
}

Write-Host "Command: python $($arguments -join ' ')"
if ($DryRun) {
    exit 0
}

Push-Location $RepoRoot
try {
    & python @arguments
} finally {
    Pop-Location
}
