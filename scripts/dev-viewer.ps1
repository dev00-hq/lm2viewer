$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendRoot = Join-Path $repoRoot "frontend"
$backendPort = 8765

function Test-PortListening {
    param([int] $Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

$startedBackend = $null
if (Test-PortListening -Port $backendPort) {
    Write-Host "Backend already listening on http://127.0.0.1:$backendPort"
} else {
    Write-Host "Starting backend on http://127.0.0.1:$backendPort"
    $startedBackend = Start-Process `
        -FilePath "py" `
        -ArgumentList @("-3", "-m", "lba2_lm2_viewer", "--host", "127.0.0.1", "--port", "$backendPort", "--no-browser") `
        -WorkingDirectory $repoRoot `
        -PassThru `
        -WindowStyle Hidden

    for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
        if (Test-PortListening -Port $backendPort) {
            break
        }
        Start-Sleep -Milliseconds 250
    }

    if (-not (Test-PortListening -Port $backendPort)) {
        throw "Backend did not start on port $backendPort."
    }
}

try {
    Write-Host "Starting Vite watcher on http://127.0.0.1:5173"
    Push-Location $frontendRoot
    try {
        & npm.cmd run dev -- --host 127.0.0.1
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }
} finally {
    if ($null -ne $startedBackend -and -not $startedBackend.HasExited) {
        Write-Host "Stopping backend started by this watcher."
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($startedBackend.Id)" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $startedBackend.Id -Force -ErrorAction SilentlyContinue
    }
}
