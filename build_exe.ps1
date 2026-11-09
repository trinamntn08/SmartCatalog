[CmdletBinding()]
param(
    # Use a new, empty directory for isolated build/release verification.
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv-build\Scripts\python.exe"
$specPath = Join-Path $projectRoot "SmartCatalog.spec"
$outputBase = $projectRoot
if ($OutputRoot) {
    if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
        $OutputRoot = Join-Path $projectRoot $OutputRoot
    }
    $outputBase = [System.IO.Path]::GetFullPath($OutputRoot)
    if (Test-Path -LiteralPath $outputBase) {
        if (
            -not (Test-Path -LiteralPath $outputBase -PathType Container) -or
            (Get-Item -LiteralPath $outputBase).Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint) -or
            @(Get-ChildItem -LiteralPath $outputBase -Force).Count -gt 0
        ) {
            throw "-OutputRoot must be a new or empty directory: $outputBase"
        }
    }
}
$buildRoot = Join-Path $outputBase "build"
$distributionRoot = Join-Path $outputBase "dist"
$releaseRoot = Join-Path $distributionRoot "SmartCatalog"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Virtual-environment Python not found: $pythonExe"
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($outputBase)
$resolvedDistributionRoot = [System.IO.Path]::GetFullPath($distributionRoot)
if (
    $resolvedDistributionRoot -eq $resolvedOutputRoot -or
    -not $resolvedDistributionRoot.StartsWith(
        $resolvedOutputRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
) {
    throw "Refusing to clean distribution path outside the output root: $resolvedDistributionRoot"
}

# Complete preflight before removing an earlier release.
foreach ($required in @("run.py", "SmartCatalog.spec", "icons\icon.ico", "icons\bg.jpg", "docs\RELEASE_README.md", "tools\release.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $required) -PathType Leaf)) {
        throw "Required build input is missing: $required"
    }
}
$baseline = (Get-Content -LiteralPath (Join-Path $projectRoot ".python-version") -Raw).Trim()
$pythonLine = (($baseline -split '\.')[0..1] -join ".")
& $pythonExe -c "import sys; expected=tuple(map(int, '$pythonLine'.split('.'))); assert sys.version_info[:2] == expected, 'Unsupported build Python'; import PyInstaller, tkinter, pandas, openpyxl, PIL, pymupdf"
if ($LASTEXITCODE -ne 0) { throw "Build interpreter/dependency preflight failed. Run tools\setup.ps1 -Mode Build." }
& $pythonExe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Build dependency consistency check failed." }

foreach ($generatedRoot in @($buildRoot, $resolvedDistributionRoot)) {
    if (Test-Path -LiteralPath $generatedRoot) {
        if ((Get-Item -LiteralPath $generatedRoot).Attributes.HasFlag([System.IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing to build through a linked output directory: $generatedRoot"
        }
    }
}
if (Test-Path -LiteralPath $resolvedDistributionRoot) {
    # A prior smoke launch creates user data in the release folder. Do not
    # erase it during a later build, even though dist is normally disposable.
    if (Test-Path -LiteralPath (Join-Path $releaseRoot "config")) {
        throw "Release contains runtime data. Preserve it elsewhere or use a new -OutputRoot: $releaseRoot"
    }
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
New-Item -ItemType Directory -Force -Path $iconTarget | Out-Null

Copy-Item -LiteralPath (Join-Path $projectRoot "icons\icon.ico") -Destination $iconTarget -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "icons\bg.jpg") -Destination $iconTarget -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\RELEASE_README.md") -Destination (Join-Path $releaseRoot "README.md")

$archive = Join-Path $distributionRoot "SmartCatalog-Windows.zip"
& $pythonExe (Join-Path $projectRoot "tools\release.py") --release-dir $releaseRoot --archive $archive
if ($LASTEXITCODE -ne 0) { throw "Release validation or packaging failed." }

Write-Host ""
Write-Host "SmartCatalog build completed:"
Write-Host (Join-Path $releaseRoot "SmartCatalog.exe")
Write-Host "Release the complete folder:"
Write-Host $releaseRoot
Write-Host "Verified delivery archive:"
Write-Host $archive
Write-Host "$archive.sha256"
