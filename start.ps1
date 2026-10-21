$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\talknj.exe')) {
        & "$PSScriptRoot\setup.ps1"
    }
    & '.venv\Scripts\python.exe' -m talknj
    if ($LASTEXITCODE -ne 0) { throw 'TalkNJ exited with an error.' }
} finally {
    Pop-Location
}
