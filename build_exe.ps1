$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"
$specPath = Join-Path $projectRoot "SmartCatalog.spec"
$distRoot = Join-Path $projectRoot "dist\SmartCatalog"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Virtual-environment Python not found: $pythonExe"
}

Push-Location $projectRoot
try {
    & $pythonExe -m PyInstaller --clean --noconfirm $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$iconTarget = Join-Path $distRoot "icons"
$brandingTarget = Join-Path $distRoot "config\database\assets"
New-Item -ItemType Directory -Force -Path $iconTarget | Out-Null
New-Item -ItemType Directory -Force -Path $brandingTarget | Out-Null

Copy-Item -LiteralPath (Join-Path $projectRoot "icons\icon.ico") -Destination $iconTarget -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "config\database\assets\bg.jpg") -Destination $brandingTarget -Force

Write-Host ""
Write-Host "SmartCatalog build completed:"
Write-Host (Join-Path $distRoot "SmartCatalog.exe")
