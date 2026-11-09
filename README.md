# SmartCatalog

SmartCatalog is a Windows desktop application for building and maintaining a
medical product catalog. It imports product data and images from PDF catalogs
and Excel workbooks, supports manual review and image editing, stores the
working catalog in SQLite, and exports formatted Excel workbooks.

## Main capabilities

- Import or update products from a catalog PDF.
- Merge Vietnamese and English descriptions from Excel.
- Import embedded Excel images and manage product images manually.
- Search, sort, edit, validate, and review catalog items.
- Reopen backed-up catalogs with their associated assets and PDFs.
- Export formatted Excel catalogs with images, branding, and print settings.

## Run from source

From PowerShell in the repository root:

```powershell
.\tools\setup.ps1 -Mode Runtime
.\.venv-runtime\Scripts\python.exe run.py
```

If PowerShell blocks activation, change policy only for the current process:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

## Build the Windows release

```powershell
.\tools\setup.ps1 -Mode Build
.\build_exe.ps1
```

The script preflights the build environment, uses `build\` for intermediate
files, replaces clean `dist\` output, and validates the complete release in
`dist\SmartCatalog\`. Deliver `dist\SmartCatalog-Windows.zip` and its `.sha256`
file. The ZIP includes the entire application folder, `_internal`, branding,
and client instructions. It refuses a prior release containing runtime data.

## Important data safety

SmartCatalog stores its working data under `config\database\` beside the source
project or frozen executable by default. An externally selected catalog keeps
its data beside that database. Close the app and copy the complete active data
folder plus this installation's settings before upgrades or manual file
operations. The backup toolbar action is currently hidden. Never delete the
data directory to reset the application.

## Documentation

- [Documentation index](docs/README.md)
- [User guide](docs/USER_GUIDE.md)
- [Developer guide](docs/DEVELOPMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Windows release build](BUILD_EXE.md)
- [Contributor rules](AGENTS.md)
