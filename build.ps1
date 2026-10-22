$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot\setup.ps1" -Dev
    & '.venv\Scripts\python.exe' build_portable.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows portable packaging failed.' }
    Write-Host 'Extract dist\TalkNJ-windows-x64.zip and launch TalkNJ\TalkNJ.exe.'
} finally {
    Pop-Location
}
