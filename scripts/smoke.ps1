$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$portable = Join-Path $env:LOCALAPPDATA "Temp\opencode\python312\python.exe"
$python = if ($env:MEDARCHIVE_PY) { $env:MEDARCHIVE_PY } elseif (Test-Path $portable) { $portable } else { "python" }
$apiDir = Join-Path $root "apps\api"

$api = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $apiDir -PassThru -WindowStyle Hidden
$smtp = $null

try {
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "API did not become ready" }

    $smtp = Start-Process -FilePath $python `
        -ArgumentList "-m", "app.smtp_server" `
        -WorkingDirectory $apiDir -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 1

    & $python (Join-Path $root "scripts\smoke_mail.py")
    if ($LASTEXITCODE -ne 0) { throw "smoke failed: $LASTEXITCODE" }
} finally {
    if ($smtp) { Stop-Process -Id $smtp.Id -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}
