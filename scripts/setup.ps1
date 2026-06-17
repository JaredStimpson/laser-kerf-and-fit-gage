[CmdletBinding()]
param(
    [string]$Python,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $RepoRoot "requirements.txt"

function Resolve-Python3 {
    if ($Python) {
        return (Resolve-Path -LiteralPath $Python).Path
    }

    if ($env:PYTHON_EXE) {
        return (Resolve-Path -LiteralPath $env:PYTHON_EXE).Path
    }

    $candidates = @(
        @("py", "-3"),
        @("python"),
        @("python3")
    )

    foreach ($candidate in $candidates) {
        $commandName = $candidate[0]
        $command = Get-Command $commandName -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) {
            continue
        }

        $candidateArgs = @()
        if ($candidate.Count -gt 1) {
            $candidateArgs = $candidate[1..($candidate.Count - 1)]
        }

        try {
            $pythonPath = & $command.Source @candidateArgs -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $pythonPath) {
                return $pythonPath.Trim()
            }
        }
        catch {
            continue
        }
    }

    throw "Could not find Python 3. Install Python 3.10+ from python.org, then run setup again."
}

if ($Force -and (Test-Path $VenvDir)) {
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    $PythonPath = Resolve-Python3
    & $PythonPath -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10+ is required."
    }

    Write-Host "Creating virtual environment with $PythonPath"
    & $PythonPath -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment."
    }
}

$hasRequirements = $false
if (Test-Path $Requirements) {
    $activeRequirements = Get-Content $Requirements | Where-Object {
        $line = $_.Trim()
        $line.Length -gt 0 -and -not $line.StartsWith("#")
    }
    $hasRequirements = $activeRequirements.Count -gt 0
}

if ($hasRequirements) {
    & $VenvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install requirements."
    }
}

& $VenvPython -c "import tkinter; print('Tkinter OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Tkinter is not available in this Python install. Install a Python build that includes Tcl/Tk."
}

Write-Host "Setup complete."
Write-Host "Run the app with: .\run.bat"
Write-Host "Run tests with: .\test.bat"
