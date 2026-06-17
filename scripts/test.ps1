[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $setupArgs = @()
    if ($env:PYTHON_EXE) {
        $setupArgs += @("-Python", $env:PYTHON_EXE)
    }
    & (Join-Path $PSScriptRoot "setup.ps1") @setupArgs
}

$env:PYTHONPATH = $RepoRoot
Push-Location $RepoRoot
try {
    & $VenvPython -m unittest discover -s tests -p "test_*.py"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
