[CmdletBinding()]
param(
    [ValidateSet("Agent", "Runtime", "Build")]
    [string]$Mode = "Agent",

    [string]$PythonVersion = "",

    [switch]$Offline,

    [switch]$RefreshWheelhouse,

    [switch]$Clean,

    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$baselineFile = Join-Path $projectRoot ".python-version"
if (-not $PythonVersion) {
    $PythonVersion = (Get-Content -LiteralPath $baselineFile -Raw).Trim()
}
$pythonLine = (($PythonVersion -split '\.')[0..1] -join ".")
$environmentName = switch ($Mode) {
    "Runtime" { ".venv-runtime" }
    "Build" { ".venv-build" }
    default { ".venv-agent" }
}
$venvRoot = Join-Path $projectRoot $environmentName
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$pipCache = Join-Path $projectRoot ".cache\pip"
$wheelhouse = Join-Path $projectRoot ".cache\wheels"

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

if ($Offline -and $RefreshWheelhouse) {
    throw "-Offline and -RefreshWheelhouse cannot be used together."
}

if ($Clean -and (Test-Path -LiteralPath $venvRoot)) {
    $resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
    $resolvedVenvRoot = [System.IO.Path]::GetFullPath($venvRoot)
    $expectedVenvRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $projectRoot $environmentName)
    )
    if (
        $resolvedVenvRoot -ne $expectedVenvRoot -or
        -not $resolvedVenvRoot.StartsWith(
            $resolvedProjectRoot + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "Refusing to clean unexpected environment path: $resolvedVenvRoot"
    }
    Remove-Item -LiteralPath $resolvedVenvRoot -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    $matchingPython = $null
    if ($null -ne $pythonCommand) {
        & $pythonCommand.Source -c "import sys; expected=tuple(map(int, '$pythonLine'.split('.'))); raise SystemExit(0 if sys.version_info[:2] == expected else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $matchingPython = $pythonCommand.Source
        }
    }

    if ($null -ne $matchingPython) {
        Invoke-CheckedCommand "Create Python $pythonLine $Mode environment" {
            & $matchingPython -m venv $venvRoot
        }
    }
    elseif ($null -ne $pyLauncher) {
        Invoke-CheckedCommand "Create Python $pythonLine $Mode environment" {
            & $pyLauncher.Source "-$pythonLine" -m venv $venvRoot
        }
    }
    else {
        throw "SmartCatalog setup requires Python $pythonLine.x on PATH or through the Windows py launcher."
    }
}

Invoke-CheckedCommand "Verify virtual-environment Python" {
    & $venvPython -c "import sys; expected=tuple(map(int, '$pythonLine'.split('.'))); raise SystemExit(0 if sys.version_info[:2] == expected else f'SmartCatalog requires Python $pythonLine.x; found {sys.version.split()[0]}')"
}

$requirementsFile = switch ($Mode) {
    "Runtime" { "requirements.txt" }
    "Build" { "requirements-build.txt" }
    default { "requirements-dev.txt" }
}
$requirementsPath = Join-Path $projectRoot $requirementsFile

if ($RefreshWheelhouse) {
    New-Item -ItemType Directory -Path $wheelhouse -Force | Out-Null
    Invoke-CheckedCommand "Download $Mode dependency wheels" {
        & $venvPython -m pip download `
            --cache-dir $pipCache `
            --requirement $requirementsPath `
            --dest $wheelhouse
    }
}

$installArguments = @(
    "-m",
    "pip",
    "install",
    "--cache-dir",
    $pipCache,
    "--requirement",
    $requirementsPath
)
if ($Offline) {
    if (-not (Test-Path -LiteralPath $wheelhouse)) {
        throw "Offline wheelhouse not found: $wheelhouse. Run setup with -RefreshWheelhouse while online first."
    }
    $installArguments += @("--no-index", "--find-links", $wheelhouse)
}

Invoke-CheckedCommand "Install $Mode dependencies from $requirementsFile" {
    & $venvPython @installArguments
}

if ($Mode -eq "Agent" -and -not $SkipValidation) {
    Invoke-CheckedCommand "Validate the agent environment" {
        & (Join-Path $PSScriptRoot "check.ps1") `
            -PythonExe $venvPython `
            -ExpectedPythonLine $pythonLine
    }
}

Write-Host ""
Write-Host "$Mode environment is ready: $venvRoot"
