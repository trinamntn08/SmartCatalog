[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [string]$ExpectedPythonLine = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$agentVenvPython = Join-Path $projectRoot ".venv-agent\Scripts\python.exe"
$legacyVenvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
$dotVenvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not $ExpectedPythonLine) {
    $baseline = (Get-Content -LiteralPath (Join-Path $projectRoot ".python-version") -Raw).Trim()
    $ExpectedPythonLine = (($baseline -split '\.')[0..1] -join ".")
}

if ($PythonExe) {
    $pythonExe = $PythonExe
}
elseif (Test-Path -LiteralPath $agentVenvPython) {
    $pythonExe = $agentVenvPython
}
elseif (Test-Path -LiteralPath $legacyVenvPython) {
    $pythonExe = $legacyVenvPython
}
elseif (Test-Path -LiteralPath $dotVenvPython) {
    $pythonExe = $dotVenvPython
}
else {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $pythonExe = $pythonCommand.Source
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Description,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Using Python: $pythonExe"

Push-Location $projectRoot
try {
    Invoke-CheckedCommand "Verify supported Python version" {
        & $pythonExe -c "import sys; expected=tuple(map(int, '$ExpectedPythonLine'.split('.'))); actual=sys.version_info[:2]; raise SystemExit(0 if actual == expected else f'SmartCatalog requires Python {expected[0]}.{expected[1]}.x; found {sys.version.split()[0]}')"
    }
    Invoke-CheckedCommand "Verify installed dependency consistency" {
        & $pythonExe -m pip check
    }
    Invoke-CheckedCommand "Compile Python sources" {
        & $pythonExe -m compileall -q run.py src tests
    }
    Invoke-CheckedCommand "Import application modules" {
        & $pythonExe -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
    }
    Invoke-CheckedCommand "Run conservative Ruff checks" {
        & $pythonExe -m ruff check run.py src tests tools
    }
    Invoke-CheckedCommand "Run unit tests" {
        & $pythonExe -m unittest discover -s tests -v
    }
    Invoke-CheckedCommand "Check patch whitespace" {
        & git diff --check HEAD
    }
    Invoke-CheckedCommand "Check repository text and documentation" {
        & $pythonExe tools/repository_checks.py
    }
    Invoke-CheckedCommand "Show worktree status" {
        & git status --short
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "All validation checks passed."
