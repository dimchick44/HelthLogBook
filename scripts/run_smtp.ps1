$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$portable = Join-Path $env:LOCALAPPDATA "Temp\opencode\python312\python.exe"
$python = if ($env:MEDARCHIVE_PY) { $env:MEDARCHIVE_PY } elseif (Test-Path $portable) { $portable } else { "python" }

Push-Location (Join-Path $root "apps\api")
try {
    & $python -m app.smtp_server
} finally {
    Pop-Location
}
