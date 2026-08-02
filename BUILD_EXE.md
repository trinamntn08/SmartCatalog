# Build the SmartCatalog Windows application

[Project overview](README.md) ·
[Developer guide](docs/DEVELOPMENT.md) ·
[Documentation index](docs/README.md)

This is the supported release process. The older `auto-py-to-exe` workflow is
not supported.

## Build

Install the separately pinned build dependencies, then build from PowerShell
at the repository root:

```powershell
.\tools\setup.ps1 -Mode Build
.\build_exe.ps1
```

Build dependencies are isolated in `.venv-build`. Use
`.\tools\setup.ps1 -Mode Build -Clean` for a clean release environment.

The script resolves paths from its own location, so invoking it by absolute
path from another working directory produces `build/` and `dist/` beside the
script rather than in the caller's directory.

## Release output

The client-ready folder is:

```text
dist\SmartCatalog\
```

Every build uses `build\` for PyInstaller work files, removes the previous
`dist\` tree, and creates a fresh `dist\SmartCatalog\` release folder.

Launch it with:

```text
dist\SmartCatalog\SmartCatalog.exe
```

Send the complete `SmartCatalog` folder to the client, not only the `.exe`.
The `_internal` directory contains Python and native dependencies, including
the MuPDF binaries required by `fitz`/PyMuPDF.

The build includes:

- `icons/icon.ico`
- `icons/bg.jpg`
- the complete `pymupdf` and compatibility `fitz` packages

`build_exe.ps1` also copies the icon and branding image beside the executable
in the layout expected by frozen-mode runtime paths. Use the script rather
than invoking PyInstaller directly.

Do not place files that must be preserved in `dist\`; it is replaced on every
release build.

It intentionally does not include the development database, imported PDFs, or
product images. On first launch, SmartCatalog creates its writable
`config/database` structure beside the executable, including a
`settings.json` file whose default database entry is:

```json
{
  "database_path": "sql\\catalog.db",
  "catalog_pdf_path": ""
}
```

Relative paths in `settings.json` are resolved from `config/database/`. The
portable user-data unit is the complete `config/database/` directory, not the
SQLite file alone; it also contains the referenced product images and catalog
PDFs.

## Existing-client upgrade

Never replace or delete an existing client's `config/database/` directory.
Before upgrading:

1. Close SmartCatalog.
2. Use the application's backup workflow, or copy the complete existing
   `config/database/` directory to a safe location.
3. Install the new release binaries while preserving the client's existing
   `config/database/` directory.
4. Start the new `SmartCatalog.exe`. Legacy `settings.json` files that do not
   yet contain `database_path` are upgraded automatically to
   `sql/catalog.db`.
5. Confirm that the existing catalog, product images, selected PDF, and
   restart behavior still work.

For a clean installation, distribute the generated folder unchanged. Do not
add the development `catalog.db`, `settings.json`, imported PDFs, or imported
product images to the release archive.

## Delivery checklist

Before delivery:

1. Extract/copy the distribution to a normal writable client folder.
2. Start `SmartCatalog.exe`.
3. Confirm `config\database\settings.json` contains the expected relative
   `database_path`.
4. Test PDF import, Excel import/export, image previews, backup, and
   application restart.
5. For an upgrade test, preserve and reopen a disposable copy of an existing
   complete `config/database/` directory.
6. Zip the entire clean `dist\SmartCatalog` folder for delivery.

PyMuPDF is dual-licensed under AGPL and a commercial Artifex license. Confirm
that the intended client distribution complies with the applicable license.
