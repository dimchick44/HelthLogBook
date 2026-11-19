$ErrorActionPreference = "Stop"

function Find-Python {
    if ($env:MEDARCHIVE_PY -and (Test-Path $env:MEDARCHIVE_PY)) { return $env:MEDARCHIVE_PY }
    $portable = Join-Path $env:LOCALAPPDATA "Temp\opencode\python312\python.exe"
    if (Test-Path $portable) { return $portable }
    foreach ($name in @("py", "python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "Python 3.12 not found. Set MEDARCHIVE_PY to python.exe"
}

$root = Split-Path -Parent $PSScriptRoot
$python = Find-Python
Push-Location (Join-Path $root "apps\api")
try {
    & $python -m pytest -q @args
} finally {
    Pop-Location
}
