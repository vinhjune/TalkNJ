$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot\setup.ps1" -Dev
    & '.venv\Scripts\python.exe' -m PyInstaller --noconfirm TalkNJ.spec
    if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed.' }
    Write-Host 'Launch dist\TalkNJ\TalkNJ.exe. Distribute the entire dist\TalkNJ folder.'
} finally {
    Pop-Location
}
