# Build and release SmartCatalog for Windows

[Project overview](README.md) · [Developer guide](docs/DEVELOPMENT.md) ·
[Documentation index](docs/README.md)

## Prepare and build

Use PowerShell with Python 3.13.x. `.python-version` records the validated local
patch version; CI uses the 3.13 line. Runtime, Agent, and Build dependencies
have separate environments and complete pinned locks.

```powershell
.\tools\setup.ps1 -Mode Agent
.\tools\setup.ps1 -Mode Build
.\build_exe.ps1
```

Agent setup runs the canonical checks. Build setup installs
`requirements-build.txt` into `.venv-build`. For a clean build environment use
`-Mode Build -Clean`; this recreates that environment only. Offline setup is
described in [DEVELOPMENT.md](docs/DEVELOPMENT.md).

`build_exe.ps1` validates required inputs, Python, imports, and dependency
consistency before removing previous output. It builds the checked-in
`SmartCatalog.spec`, copies client instructions/branding, and runs
`tools/release.py`. It resolves relative paths from the script's repository,
even when called from another working directory.

Default outputs:

```text
build/                          PyInstaller work files
dist/
  SmartCatalog/
    SmartCatalog.exe
    _internal/                  Python, Tcl/Tk, MuPDF and other dependencies
    icons/icon.ico
    icons/bg.jpg
    README.md                   packaged client quick start
  SmartCatalog-Windows.zip      contains the entire SmartCatalog/ folder
  SmartCatalog-Windows.zip.sha256
```

The spec excludes MuPDF development headers. The build does not bundle the
development catalog, installation settings, dictionary, imported images/PDFs,
or agent scratch files. The verifier checks package layout, required runtime
components, executable header, empty/missing assets, linked content, and
accidental runtime/development files. The ZIP is checked for CRC errors and
has a separately written SHA-256 checksum. These checks complement a real EXE
smoke test; they cannot prove every interactive workflow works.

Use the build script rather than bare PyInstaller: the script supplies branding
beside the EXE, client instructions, verification, and delivery packaging.
Do not edit generated release contents to fix build problems.

## Protect previous output and data

The default build replaces the repository's `dist/` tree. Do not store user
files there. It refuses to clean `dist/SmartCatalog/config/`, which is created
by a smoke launch, and refuses linked output directories. Preserve that data
elsewhere or use an isolated output root; do not delete it just to pass a build.

For verification without touching existing `build/` or `dist/`:

```powershell
.\build_exe.ps1 -OutputRoot .cache\release-verification
```

That root must be new or empty. It receives its own `build/` and `dist/`
subdirectories. For another run, choose another fresh root or remove only
the verified disposable output from the earlier check.

To recheck a pristine runnable folder without rebuilding:

```powershell
.\.venv-build\Scripts\python.exe tools/release.py --release-dir dist\SmartCatalog
```

Do not launch the folder intended for delivery. First launch creates user data
and makes it unsuitable for a clean-install archive. Extract the checked ZIP
to a separate disposable directory for testing.

## Delivery checks

1. Confirm the source revision and worktree contents intended for release.
   Run `tools/check.ps1` and review the build/verifier result.
2. Check the archive digest, then extract the ZIP to a normal writable folder:

   ```powershell
   Get-FileHash .\dist\SmartCatalog-Windows.zip -Algorithm SHA256
   Get-Content .\dist\SmartCatalog-Windows.zip.sha256
   ```

3. Open the extracted `SmartCatalog/SmartCatalog.exe`. Confirm the empty
   first-launch catalog and default settings. Never test against the live
   client catalog.
4. On generated or backed-up disposable data, test PDF import, `.xlsx` import
   and export, image previews/editing/cropping, validation, and restart. Verify
   saved edits, image order, source PDF paths, branding, and print layout in
   desktop Excel. The backup button is currently hidden; check closed-app
   folder backup/reopen instead, or invoke the tested service separately.
5. For upgrades, reopen a disposable complete copy of a representative older
   data folder and verify paths, schema compatibility, and restart behavior.
6. Deliver the original checked ZIP and its checksum, not the smoke-tested
   folder. If distributing an extracted folder instead, include `_internal`,
   icons, instructions, and the EXE together.

The archive is not an installer and no code-signing step is configured. Do not
describe it as a signed installer or an automatically published release.

## Existing-client upgrade

1. Close SmartCatalog.
2. Copy the complete existing installation `config/database/` directory to a
   separate safe location. If installation settings select another database,
   also copy its complete active data root (database, `assets/`, and
   `catalog_pdfs/`) and preserve external absolute references separately.
3. Verify the backup, then replace application binaries, `_internal`, icons,
   and instructions while preserving those data/settings locations. Do not
   overlay an incomplete `_internal` folder from another release.
4. Start the new EXE and check catalog, images, PDF selection, and restart.
   Legacy settings without `database_path` adopt `sql/catalog.db`; an explicit
   configured relative or absolute database path remains authoritative.

The default portable unit is the entire `config/database/` folder, not SQLite
alone. When a selected database lives elsewhere, its active data root is the
database parent, or the parent of its `sql/` folder. Installation settings stay
beside the executable. A manual closed-app copy preserves settings; the internal
backup service itself copies the database/assets/PDFs without settings.

## CI artifacts and publication

`.github/workflows/check.yml` runs on pushes to `master`, pull requests targeting
`master`, and manual dispatch. It sets up/validates the Agent environment,
sets up the Build environment, builds/verifies/packages, then uploads
`SmartCatalog-Windows.zip` and its checksum as `SmartCatalog-Windows` with
30-day retention. Failed checks/builds do not produce a successful delivery.

Download the artifact from the successful run for the intended commit. GitHub's
browser download may wrap those two files in an artifact ZIP; extract that
wrapper first, then verify/extract the inner delivery ZIP. An artifact is a
time-limited CI build, not a GitHub Release. No tag-triggered publication,
release creation, or client upload is configured; publication is a separate
maintainer action after delivery checks.

Workflow behavior is described in the official [GitHub event documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Artifact download and retention behavior is described in the [GitHub artifact guide](https://docs.github.com/en/actions/tutorials/store-and-share-data).
PyInstaller output options are documented in its [usage guide](https://pyinstaller.org/en/stable/usage.html).
PyMuPDF's [license information](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
must be reviewed for the intended distribution; the build does not select or
grant a distribution license.
