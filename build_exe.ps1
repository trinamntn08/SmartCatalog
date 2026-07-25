$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"
$specPath = Join-Path $projectRoot "SmartCatalog.spec"
$buildRoot = Join-Path $projectRoot "build"
$distributionRoot = Join-Path $projectRoot "dist"
$releaseRoot = Join-Path $distributionRoot "SmartCatalog"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Virtual-environment Python not found: $pythonExe"
}

$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
$resolvedDistributionRoot = [System.IO.Path]::GetFullPath($distributionRoot)
if (
    $resolvedDistributionRoot -eq $resolvedProjectRoot -or
    -not $resolvedDistributionRoot.StartsWith(
        $resolvedProjectRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
) {
    throw "Refusing to clean distribution path outside the project: $resolvedDistributionRoot"
}

if (Test-Path -LiteralPath $resolvedDistributionRoot) {
    Remove-Item -LiteralPath $resolvedDistributionRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $resolvedDistributionRoot -Force | Out-Null

Push-Location $projectRoot
try {
    & $pythonExe -m PyInstaller `
        --clean `
        --noconfirm `
        --workpath $buildRoot `
        --distpath $distributionRoot `
        $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$iconTarget = Join-Path $releaseRoot "icons"
$brandingTarget = Join-Path $releaseRoot "config\database\assets"
New-Item -ItemType Directory -Force -Path $iconTarget | Out-Null
New-Item -ItemType Directory -Force -Path $brandingTarget | Out-Null

Copy-Item -LiteralPath (Join-Path $projectRoot "icons\icon.ico") -Destination $iconTarget -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "config\database\assets\bg.jpg") -Destination $brandingTarget -Force

Write-Host ""
Write-Host "SmartCatalog build completed:"
Write-Host (Join-Path $releaseRoot "SmartCatalog.exe")
Write-Host "Release the complete folder:"
Write-Host $releaseRoot
