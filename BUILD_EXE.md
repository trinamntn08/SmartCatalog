# Build the SmartCatalog Windows application

Build from PowerShell at the repository root:

```powershell
.\build_exe.ps1
```

The script resolves paths from its own location, so invoking it by absolute
path from another working directory produces `build/` and `dist/` beside the
script rather than in the caller's directory.

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
- `config/database/assets/bg.jpg`
- the complete `pymupdf` and compatibility `fitz` packages

`build_exe.ps1` also copies the icon and branding image beside the executable
in the layout expected by frozen-mode runtime paths. Use the script rather
than invoking PyInstaller directly.

Do not place files that must be preserved in `dist\`; it is replaced on every
release build.

It intentionally does not include the development database, imported PDFs, or
product images. On first launch, SmartCatalog creates its writable
`config/database` structure beside the executable.

Before delivery:

1. Extract/copy the distribution to a normal writable client folder.
2. Start `SmartCatalog.exe`.
3. Test PDF import, Excel import/export, image previews, and application restart.
4. Zip the entire `dist\SmartCatalog` folder for delivery.

PyMuPDF is dual-licensed under AGPL and a commercial Artifex license. Confirm
that the intended client distribution complies with the applicable license.
