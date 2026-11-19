param(
    [ValidateSet('web', 'android')]
    [string]$Target = 'web'
)

$ErrorActionPreference = 'Stop'

$sdk = 'C:\Users\Dimka\AppData\Local\Temp\opencode\flutter_sdk\flutter'
$git = 'C:\Users\Dimka\AppData\Local\Temp\opencode\portable_git2\bin'
$project = Join-Path $PSScriptRoot '..\apps\mobile'

$env:PATH = "$git;$sdk\bin;$env:PATH"
$env:FLUTTER_ROOT = $sdk
$env:FLUTTER_PREBUILT_ENGINE_VERSION = '371f77202a73e8dff57a8b3bff75bca55c090aee'

Push-Location $project
try {
    if ($Target -eq 'web') {
        & "$sdk\bin\flutter.bat" run -d chrome
    }
    else {
        & "$sdk\bin\flutter.bat" run -d android
    }
}
finally {
    Pop-Location
}
