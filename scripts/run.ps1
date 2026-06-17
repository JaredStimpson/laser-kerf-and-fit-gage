[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$App = Join-Path $RepoRoot "laser_tester_generator.py"

if (-not (Test-Path $VenvPython)) {
    $setupArgs = @()
    if ($env:PYTHON_EXE) {
        $setupArgs += @("-Python", $env:PYTHON_EXE)
    }
    & (Join-Path $PSScriptRoot "setup.ps1") @setupArgs
}

& $VenvPython $App @AppArgs
exit $LASTEXITCODE
