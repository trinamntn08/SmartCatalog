[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv-agent\Scripts\python.exe"
$pipToolsCache = Join-Path $projectRoot ".cache\pip-tools"
$pipCache = Join-Path $projectRoot ".cache\pip"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Agent virtual-environment Python not found: $venvPython. Run .\tools\setup.ps1 first."
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

$previousCompileCommand = $env:CUSTOM_COMPILE_COMMAND
$previousPipCache = $env:PIP_CACHE_DIR
$env:CUSTOM_COMPILE_COMMAND = ".\tools\lock.ps1"
$env:PIP_CACHE_DIR = $pipCache
New-Item -ItemType Directory -Path $pipToolsCache -Force | Out-Null

Push-Location $projectRoot
try {
    foreach ($lock in @(
        @{ Input = "requirements.in"; Output = "requirements.txt" },
        @{ Input = "requirements-build.in"; Output = "requirements-build.txt" },
        @{ Input = "requirements-dev.in"; Output = "requirements-dev.txt" }
    )) {
        $inputPath = $lock.Input
        $outputPath = $lock.Output
        Invoke-CheckedCommand "Compile $outputPath" {
            & $venvPython -m piptools compile `
                --allow-unsafe `
                --cache-dir $pipToolsCache `
                --no-emit-index-url `
                --no-emit-trusted-host `
                --newline lf `
                --resolver backtracking `
                --strip-extras `
                --output-file $outputPath `
                $inputPath
        }
    }
}
finally {
    Pop-Location
    if ($null -eq $previousCompileCommand) {
        Remove-Item Env:CUSTOM_COMPILE_COMMAND -ErrorAction SilentlyContinue
    }
    else {
        $env:CUSTOM_COMPILE_COMMAND = $previousCompileCommand
    }
    if ($null -eq $previousPipCache) {
        Remove-Item Env:PIP_CACHE_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:PIP_CACHE_DIR = $previousPipCache
    }
}

Write-Host ""
Write-Host "Dependency lock files updated. Review them before committing."
