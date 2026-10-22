param([switch]$Dev)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & py -3 -c 'import sys; assert (3,11) <= sys.version_info[:2] and sys.maxsize > 2**32' 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or newer x64 with the Windows Python launcher.' }
        & py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & '.venv\Scripts\python.exe' -c 'import sys; assert (3,11) <= sys.version_info[:2] and sys.maxsize > 2**32'
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv must use Python 3.11 or newer x64.' }
    $package = if ($Dev) { '.[dev]' } else { '.' }
    & '.venv\Scripts\python.exe' -m pip install -e $package
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access and Python compatibility.' }
} finally {
    Pop-Location
}
