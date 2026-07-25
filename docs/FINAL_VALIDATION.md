# Phase 14 Final Validation

[Documentation index](README.md)

Historical final-validation record for the completed behavior-preserving
refactor. Current validation commands are in `DEVELOPMENT.md`.

Date: 2026-07-25

## Reproducible checks completed

- `python -m compileall -q run.py src tests`: passed.
- Focused imports of `smartcatalog` and `smartcatalog.main`: passed.
- `python -m unittest discover -s tests -v`: 88 tests passed.
- `git diff --check`: passed before Phase 14 edits.
- Generated PDF, Excel, image, SQLite, backup, and export fixtures exercised
  the supported headless workflow boundaries.
- `build_exe.ps1` completed from a disposable tracked-source export using
  PyInstaller 6.18.0.
- The disposable frozen application remained running through a five-second
  first-launch smoke and a five-second restart smoke.
- First launch created `config/database/sql`, all three asset-source
  directories and `catalog_pdfs` beside the executable.
- Disposable build and runtime data were removed after validation.

PyInstaller emitted the existing optional warning that hidden import
`jinja2` was not found.

## Build-script correction

Calling `build_exe.ps1` from outside its project directory previously allowed
PyInstaller's relative `build/` and `dist/` paths to resolve against the
caller's working directory. The script now temporarily changes to its own
project root and restores the caller's location afterward.

The initial validation attempt exposed this defect by rebuilding the
repository's already-untracked `build/` and `dist/` contents. Those generated
directories were not deleted or staged, but their prior contents cannot be
restored from Git. The corrected repeat build stayed entirely in the
disposable directory.

## Manual acceptance

The source application and frozen distribution were launched interactively.
On 2026-07-25, the user confirmed that everything was working correctly after
the requested source and frozen workflow validation. This completes the
Phase 14 manual acceptance gate.

The known characterized PDF asset-link transaction behavior remains deferred:
the PNG is written, while caller-owned asset/link rows are rolled back because
the link operation is not committed. It was not changed during this refactor.
