param([switch]$Dev)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        $version = $null
        foreach ($candidate in @('3.13', '3.12', '3.11')) {
            try {
                & py "-$candidate" -c 'import sys; assert sys.maxsize > 2**32' 2>$null
                if ($LASTEXITCODE -eq 0) { $version = $candidate; break }
            } catch {
                continue
            }
        }
        if (-not $version) { throw 'Install Python 3.11–3.13 x64 with the Windows Python launcher.' }
        & py "-$version" -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & '.venv\Scripts\python.exe' -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14) and sys.maxsize > 2**32'
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv must use Python 3.11–3.13 x64.' }
    $package = if ($Dev) { '.[dev]' } else { '.' }
    & '.venv\Scripts\python.exe' -m pip install -e $package
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access and Python compatibility.' }
} finally {
    Pop-Location
}
