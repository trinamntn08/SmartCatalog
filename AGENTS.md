# SmartCatalog Contributor Guide

For general setup and navigation, start with `README.md` and
`docs/README.md`. This file contains mandatory rules for contributors and
automation.

## Scope and non-negotiable boundaries

SmartCatalog is a Windows-first Python/Tkinter desktop application for importing, reviewing, editing, and exporting a medical product catalog. Product data and images come mainly from layout-specific PDF catalogs and flexible Excel workbooks. The application persists its working catalog in SQLite and writes formatted Excel output.

- Work only in the tracked application, tests, build configuration, and
  documentation unless the user explicitly places another area in scope.
- `to_integrate/` is outside the application and outside review scope. Do not read it, edit it, import from it, copy code from it, or add fallbacks to it.
- Treat `config/`, `input/`, `output/`, `build/`, and `dist/` as local, generated, or user-data areas. Do not inspect or modify their contents unless the task specifically requires it and the data is safely backed up.
- Never delete, recreate, or casually rewrite the configured catalog database,
  imported PDFs, `settings.json`, branding, or asset directories. Runtime-data
  work requires explicit scope and a verified backup or disposable copy.
- The UI and catalog data are largely Vietnamese. Preserve Unicode exactly and save source and documentation as UTF-8. Some existing source strings/comments are visibly mojibake; do not perform speculative or mass encoding conversion.
- Preserve both source execution and frozen-executable behavior.

## Active architecture

Normal startup is:

`run.py` -> `smartcatalog.main.start_ui()` -> `AppState` -> `CatalogDB` -> `create_main_window()`

The active layer map is:

- `domain/`: persisted and UI-facing models.
- `db/`: schema, path mapping, repositories, and the `CatalogDB` facade.
- `loader/`: layout-sensitive PDF and tolerant Excel parsing.
- `services/`: UI-independent workflow orchestration and typed results.
- `ui/`: Tkinter composition, controllers, dialogs, and widgets.
- `utils/`: shared normalization, hashing, image, workbook, and package helpers.

Keep UI behavior in controllers, UI-independent workflows in services,
persistence behind `CatalogDB` and repositories, and parsing in loaders. See
`docs/ARCHITECTURE.md` for the current flow. More specific rules live in the
nearest scoped `AGENTS.md` under `db/`, `loader/`, `services/`, `ui/`, `utils/`,
and `tests/`.

## Removed legacy code

Phase 12 removed the previously unwired PDF database updater, alternate PDF
extractor/matcher/viewer, ReportLab PDF exporter, and experimental settings
module after verifying that no tracked caller remained. Their dispositions and
active replacements are recorded in `docs/LEGACY_MODULE_DISPOSITION.md`.

Do not recreate or revive those implementations merely because a similar
helper existed there. The active PDF import is `services/pdf_import.py` through
`ui/controllers/pdf_import_adapter.py`, the active crop UI is
`ui/pdf_crop_window.py`, and the
supported export is Excel post-processing through
`services/catalog_export.py`.

## Runtime data and persistence

`AppState.project_dir` is the repository root in source mode and the executable directory in frozen mode. Runtime data is created beside it:

```text
config/database/
├── sql/catalog.db
├── settings.json
├── catalog_pdfs/
└── assets/
    ├── excel_import/
    ├── pdf_import/
    └── manual_import/
```

The tree shows the first-launch default. The actual SQLite file is selected by
`database_path` in `settings.json` and may use another relative or absolute
location.

The live SQLite entities are:

- `items`: unique product `code`, descriptions, extracted fields, source PDF/page, and validation status/time.
- `assets`: stored image path, PDF/page provenance, optional PDF bounding box, source, hash, and creation time.
- `item_asset_links`: ordered item/image associations with match method, score, verified flag, and primary flag.

Persistence rules:

- Product code is the stable unique business key. Reuse the relevant existing normalization behavior and avoid silently merging ambiguous normalized codes.
- `settings.json` is the source of truth for the SQLite `database_path`.
  Relative values resolve from `config/database/`; the first-launch and legacy
  default is `sql/catalog.db`. `AppState.db_path`, never a separately
  hard-coded catalog path, must be passed to `CatalogDB` and backup workflows.
- The portable user-data unit is the complete `config/database/` directory,
  including settings, the configured database, assets, and catalog PDFs.
  Moving only the SQLite file does not move its external images or PDFs.
- Paths under `config/database/` are deliberately stored relative to the data directory through `CatalogDB.to_db_path()` and resolved through `from_db_path()`. Preserve special non-file tokens such as `excel:...`.
- `CatalogDB` does not retain a shared connection. Open one connection per operation/thread. If a connection is passed into DB helpers, the caller owns grouped commits and closing it.
- Schema additions belong in `SCHEMA_SQL`; compatibility for existing databases belongs in `_ensure_columns()` or a deliberate, tested migration.
- Keep foreign keys enabled and keep `assets` and `item_asset_links` synchronized with item image changes.
- Image order is represented by link order, with `is_primary` sorted first. Reordering currently rebuilds links while retaining metadata. The first UI image is made primary when the form is saved.
- Keep active provenance strings compatible with existing behavior: `excel`, `extract`, `page_extract`, `manual_crop`, and `add`. Coordinate any rename across loaders, DB code, controllers, and existing data.
- Database PDF page values are 1-based. PyMuPDF document indexes are 0-based. Convert explicitly at every boundary.
- Validated items and items with Excel-sourced images receive special skip behavior during PDF re-import; preserve that protection unless the task explicitly changes it.
- SQLite descriptions are the source of truth. Dictionary import may fill empty VI/EN fields but must never overwrite non-empty user edits automatically.

For persistence work, use a temporary project directory or copies of representative databases. Test both a fresh schema and an older schema upgraded in place. Never use the live catalog as test data.

## Main user workflows

The supported PDF import, Excel update/export, manual image, and backup flows
are summarized in `docs/ARCHITECTURE.md` and described for users in
`docs/USER_GUIDE.md`. Preserve their established matching, overwrite, image,
and portability behavior unless a task explicitly changes it.

Long PDF, Excel, image, and backup work runs off the UI thread. Tkinter widgets and variables must be accessed only on the UI thread through `root.after(...)`, `_safe_ui`, `_ui_call`, or the established equivalent. A worker may wait for a UI-thread decision only through the existing event/dialog pattern; do not call dialogs directly from a worker.

## Development setup

Use PowerShell from the repository root:

```powershell
.\tools\setup.ps1
.\.venv-agent\Scripts\python.exe run.py
```

Python 3.13 is the currently supported and locally validated interpreter line;
`.python-version` records the exact local baseline. CI exercises Python 3.13.
The setup command creates or reuses a separate
`.venv-agent`, `.venv-runtime`, or `.venv-build` environment for the selected
mode, installs its lock, and runs validation in Agent mode.
Dependency intent lives in `requirements*.in`; generated `requirements*.txt`
files lock complete Runtime, Agent, and Build environments. Regenerate all
locks through `.\tools\lock.ps1` after deliberate input changes.

If script execution is blocked, change policy only for the current process:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

The repository has a `unittest` regression suite and conservative Ruff
correctness checks. Formatting and static type checking are not enforced.
Minimum non-GUI validation is available through one canonical command:

```powershell
.\tools\check.ps1
```

The script prefers the repository `venv`, then `.venv`, and otherwise uses
`python` from `PATH`. It verifies Python and imports, runs high-signal Ruff
checks and the complete discovered test suite, compiles the source, checks
patch whitespace, and reports worktree status. The discovered test output is
authoritative; do not duplicate an exact test count in current documentation.
Run focused disposable-data checks for changed parsing, persistence, backup,
or export code. UI changes also require a manual smoke test when feasible;
report any test that was not performed. Follow `docs/TESTING.md` for regression,
characterization, and known-behavior policy.

## Windows executable build

The supported build is the checked-in PyInstaller configuration:

```powershell
.\tools\setup.ps1 -Mode Build
.\build_exe.ps1
```

- The setup command installs the complete pinned build environment, including
  PyInstaller, into `.venv-build`.
- The script uses `build/` for PyInstaller intermediates and deliberately
  removes/recreates `dist/` as the release output on every build. Never keep
  user or irreplaceable files in `dist/`.
- `SmartCatalog.spec` adds `src/`, collects `pymupdf`/`fitz`, includes the icon and branding image, and produces `dist/SmartCatalog/SmartCatalog.exe`.
- Deliver the complete `dist/SmartCatalog/` folder, including `_internal`, not the executable alone.
- The build intentionally excludes the development database, `settings.json`,
  and imported user content. First launch creates the writable runtime layout
  and settings beside the executable. Existing-client upgrades must preserve
  the complete existing `config/database/` directory.
- Follow `BUILD_EXE.md` for the supported build, delivery checks, and licensing
  notes. `README.md` and `docs/README.md` provide the current documentation
  entry points.

Do not edit generated `build/` or `dist/` contents. Change the spec or build script and rebuild instead.

## Engineering guidance

- Prefer `pathlib.Path` and derive paths from `AppState.project_dir`, `data_dir`, or `assets_dir`; never hard-code a developer-machine path.
- Keep direct dependency intent in the matching `requirements*.in` file,
  regenerate every lock with `.\tools\lock.ps1`, update the relevant dependency
  contract test, and verify the frozen build after dependency changes.
- Keep strong references to every displayed `ImageTk.PhotoImage`; otherwise Tkinter may render blank images.
- Close PyMuPDF documents, PIL image contexts, workbooks where supported, and SQLite connections deterministically.
- Avoid broad exception swallowing in new code. Existing best-effort icon/UI paths contain it, but new failures should produce actionable status or dialog messages.
- PDF extraction is catalog-layout-specific. Small coordinate, clustering, regex, or nearest-image changes can alter many products; test representative single- and multi-column pages and unusual dimensions.
- Excel input intentionally accepts variable header rows and column names. Preserve tolerant detection unless a task explicitly narrows the accepted format.
- `post_processing.py` performs low-level ZIP, XML relationship, VML, and content-type edits after openpyxl. Verify the result opens in desktop Excel and retains images, branding, print settings, sheet relationships, and workbook integrity.
- Avoid opportunistic cleanup across the large `main_window.py` or mojibake-looking text. Make small, separable refactors with behavior-preserving checkpoints.

## Change workflow

The behavior-preserving refactor is complete. Git history is the authoritative
record of its phased checkpoints; there is no active phase queue. New features,
bug fixes, and release work must be separately scoped and must preserve the
architecture, data-safety rules, and regression baseline in this guide.

Before editing:

1. Run `git status --short` and preserve all unrelated tracked and untracked work.
2. Search tracked application code under `src/`, explicitly excluding `to_integrate/`, generated outputs, and runtime data.
3. Identify whether the target code is active or legacy.
4. Trace the complete UI -> state -> DB -> filesystem flow before changing persisted behavior.

After editing:

1. Review `git diff` and confirm runtime/generated/user files are untouched.
2. Run compile validation and focused imports.
3. Run focused checks against disposable data.
4. Manually smoke-test affected workflows when feasible: startup, select/edit/save, dirty-state prompts, PDF import, Excel import/export, image add/remove/rotate/reorder/crop, validation, backup, restart, and frozen execution as relevant.
5. Report exactly what was validated and what remains untested.

There is no active `scripts/` migration directory. If a future task requires a
one-off migration, keep it out of normal startup, provide a documented dry
run, operate on a backed-up or disposable database and assets, and test both
the intended old layout and the resulting current layout.
