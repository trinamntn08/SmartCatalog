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
- Back up the database and associated files.
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

The script uses `build\` for intermediate files, cleans `dist\`, and creates
the complete release in `dist\SmartCatalog\`. Distribute that entire folder,
including `_internal`; do not distribute `SmartCatalog.exe` by itself.

## Important data safety

SmartCatalog stores its working data under `config\database\` beside the source
project or frozen executable. Do not delete that directory to reset the
application. Use the built-in backup workflow before migrations, upgrades, or
manual file operations.

## Documentation

- [Documentation index](docs/README.md)
- [User guide](docs/USER_GUIDE.md)
- [Developer guide](docs/DEVELOPMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Windows release build](BUILD_EXE.md)
- [Contributor rules](AGENTS.md)
