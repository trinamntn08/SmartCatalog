# SmartCatalog Contributor Guide

## Scope and non-negotiable boundaries

SmartCatalog is a Windows-first Python/Tkinter desktop application for importing, reviewing, editing, and exporting a medical product catalog. Product data and images come mainly from layout-specific PDF catalogs and flexible Excel workbooks. The application persists its working catalog in SQLite and writes formatted Excel output.

- Work only in the tracked application, build, documentation, and explicitly requested migration-script areas.
- `to_integrate/` is outside the application and outside review scope. Do not read it, edit it, import from it, copy code from it, or add fallbacks to it.
- Treat `config/`, `input/`, `output/`, `build/`, and `dist/` as local, generated, or user-data areas. Do not inspect or modify their contents unless the task specifically requires it and the data is safely backed up.
- Never delete, recreate, or casually rewrite `config/database/sql/catalog.db`, imported PDFs, settings, dictionaries, branding, or asset directories.
- The UI and catalog data are largely Vietnamese. Preserve Unicode exactly and save source and documentation as UTF-8. Some existing source strings/comments are visibly mojibake; do not perform speculative or mass encoding conversion.
- Preserve both source execution and frozen-executable behavior.

## Active architecture

Normal startup is:

`run.py` -> `smartcatalog.main.start_ui()` -> `AppState` -> `CatalogDB` -> `create_main_window()`

The active modules are:

- `run.py`: resolves the source or frozen application root, adds the root and `src/` to `sys.path`, and starts the UI.
- `src/smartcatalog/main.py`: creates the Tk root, icon and splash screen, application state, database wrapper, and main window.
- `src/smartcatalog/domain/models.py`: defines the active persisted/UI `CatalogItem` model. `state.py` re-exports it for compatibility.
- `src/smartcatalog/state.py`: defines `AppState`, resolves runtime paths, creates data directories, and persists the selected catalog PDF.
- `src/smartcatalog/db/catalog_db.py`: compatibility facade for connection lifecycle, public persistence calls, and existing commit policy.
- `src/smartcatalog/db/schema.py` and `path_mapper.py`: live SQLite schema/compatibility upgrades and portable database-path policy.
- `src/smartcatalog/db/item_repository.py` and `asset_repository.py`: item mapping/CRUD and asset/link SQL, ordering, and mutation policy behind `CatalogDB`.
- `src/smartcatalog/loader/extract_item.py`: performs coordinate- and regex-sensitive extraction of item fields from PDF pages.
- `src/smartcatalog/loader/pdf_loader.py`: scans the selected PDF, upserts extracted items, finds the nearest image, stores it as an asset, and links it to the item.
- `src/smartcatalog/loader/excel_loader.py`: tolerantly detects header rows, code columns, and Vietnamese/English description columns across workbooks.
- `src/smartcatalog/ui/main_window.py`: composes the Tkinter UI and coordinates PDF import, Excel database updates, backup, and Excel export/post-processing.
- `src/smartcatalog/ui/controllers/items_controller.py`: item list filtering, sorting, selection, and search behavior.
- `src/smartcatalog/ui/controllers/item_form_controller.py`: dirty-state handling, item add/edit/delete/save, validation state, and synchronization of UI image order to asset links.
- `src/smartcatalog/ui/controllers/images_controller.py`: manual image add/remove/rotate, thumbnails, previews, drag reorder, and image provenance display.
- `src/smartcatalog/ui/controllers/candidates_controller.py`: asynchronously extracts candidate images from the current PDF page and allows manual assignment.
- `src/smartcatalog/ui/pdf_crop_window.py`: the currently wired manual PDF crop workflow.
- `src/smartcatalog/ui/export_review_dialog.py`: pre-export review and editing for missing VI/EN descriptions, images, and unmatched codes.
- `src/smartcatalog/utils/description_dictionary.py`: seeds only empty database description fields from `config/database/dictionary.csv`.
- `src/smartcatalog/utils/post_processing.py`: builds the formatted post-processing worksheet, inserts product images, then edits the XLSX ZIP/XML package to install the header image.
- `src/smartcatalog/utils/code_normalization.py`, `filename_utils.py`, `hashing.py`, `text_normalization.py`, `ui_dispatch.py`, and `workbook_images.py`: shared, side-effect-free policies extracted from active UI/loader code; compatibility wrappers remain at older entry points where needed.
- `src/smartcatalog/ui/widgets/scrollable_frame.py`: reusable Tkinter scrollable frame.

`MainWindow` currently mixes in `ItemsControllerMixin`, `CandidatesControllerMixin`, `ImagesControllerMixin`, and `ItemFormControllerMixin`. Keep reusable panel behavior in those controllers, persistence in `CatalogDB`, parsing in loaders, and leave `main_window.py` primarily for layout and workflow coordination.

## Removed legacy code

Phase 12 removed the previously unwired PDF database updater, alternate PDF
extractor/matcher/viewer, ReportLab PDF exporter, and experimental settings
module after verifying that no tracked caller remained. Their dispositions and
active replacements are recorded in `docs/LEGACY_MODULE_DISPOSITION.md`.

Do not recreate or revive those implementations merely because a similar
helper existed there. The active PDF import is `services/pdf_import.py` through
`loader/pdf_loader.py`, the active crop UI is `ui/pdf_crop_window.py`, and the
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

The live SQLite entities are:

- `items`: unique product `code`, descriptions, extracted fields, source PDF/page, and validation status/time.
- `assets`: stored image path, PDF/page provenance, optional PDF bounding box, source, hash, and creation time.
- `item_asset_links`: ordered item/image associations with match method, score, verified flag, and primary flag.

Persistence rules:

- Product code is the stable unique business key. Reuse the relevant existing normalization behavior and avoid silently merging ambiguous normalized codes.
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

- PDF import copies the chosen PDF into `catalog_pdfs/`, persists the relative selection, scans pages in a background thread, prompts before updating existing unvalidated records, and assigns nearest extracted images only when an item has no images.
- Excel database update tolerantly detects codes/descriptions on all sheets, updates matching descriptions, extracts embedded images by their nearest code row, deduplicates image content, and stores Excel images under `assets/excel_import/`.
- Manual image workflows can add files, assign PDF-page candidates, crop a PDF region, rotate images, remove links, and reorder linked images.
- Backup uses SQLite's backup API and copies assets, catalog PDFs, and settings to a timestamped user-selected directory.
- Excel export reads product codes/quantities from a selected workbook, performs exact then unique normalized matching, optionally runs the preflight dialog, replaces the output worksheet with the formatted post-processing sheet, embeds images, and injects branding into the XLSX package.

Long PDF, Excel, image, and backup work runs off the UI thread. Tkinter widgets and variables must be accessed only on the UI thread through `root.after(...)`, `_safe_ui`, `_ui_call`, or the established equivalent. A worker may wait for a UI-thread decision only through the existing event/dialog pattern; do not call dialogs directly from a worker.

## Development setup

Use PowerShell from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

If script execution is blocked, change policy only for the current process:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

There is no automated test suite, test configuration, formatter, linter, or type-checker configuration in the repository. Minimum non-GUI validation is:

```powershell
python -m compileall -q run.py src
python -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
```

Run focused read-only or temporary-directory checks for changed parsing/DB/export code. UI and workflow changes also require a manual smoke test when feasible; report any test that was not performed.

## Windows executable build

The supported build is the checked-in PyInstaller configuration:

```powershell
.\build_exe.ps1
```

- The script expects `venv\Scripts\python.exe` and PyInstaller installed in that environment; PyInstaller is not listed in `requirements.txt`.
- `SmartCatalog.spec` adds `src/`, collects `pymupdf`/`fitz`, includes the icon and branding image, and produces `dist/SmartCatalog/SmartCatalog.exe`.
- Deliver the complete `dist/SmartCatalog/` folder, including `_internal`, not the executable alone.
- The build intentionally excludes the development database and imported user content. First launch creates writable runtime directories beside the executable.
- Follow `BUILD_EXE.md` for delivery checks and licensing notes. The short `README.md` contains older `auto-py-to-exe` instructions and should not override the checked-in spec/build script.

Do not edit generated `build/` or `dist/` contents. Change the spec or build script and rebuild instead.

## Engineering guidance

- Prefer `pathlib.Path` and derive paths from `AppState.project_dir`, `data_dir`, or `assets_dir`; never hard-code a developer-machine path.
- Do not add dependencies without updating `requirements.txt` and verifying the frozen build.
- Keep strong references to every displayed `ImageTk.PhotoImage`; otherwise Tkinter may render blank images.
- Close PyMuPDF documents, PIL image contexts, workbooks where supported, and SQLite connections deterministically.
- Avoid broad exception swallowing in new code. Existing best-effort icon/UI paths contain it, but new failures should produce actionable status or dialog messages.
- PDF extraction is catalog-layout-specific. Small coordinate, clustering, regex, or nearest-image changes can alter many products; test representative single- and multi-column pages and unusual dimensions.
- Excel input intentionally accepts variable header rows and column names. Preserve tolerant detection unless a task explicitly narrows the accepted format.
- `post_processing.py` performs low-level ZIP, XML relationship, VML, and content-type edits after openpyxl. Verify the result opens in desktop Excel and retains images, branding, print settings, sheet relationships, and workbook integrity.
- Avoid opportunistic cleanup across the large `main_window.py` or mojibake-looking text. Make small, separable refactors with behavior-preserving checkpoints.

## Change workflow

For the behavior-preserving cleanup program, read `docs/REFACTOR_STATE.md` first to find the authoritative resume point, then follow `docs/REFACTOR_PLAN.md`. Its phases, validation gates, state updates, and checkpoint commits are mandatory; do not skip ahead or combine phases.

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

The files in `scripts/` are one-off data migrations, not normal startup code. Read the entire script, back up the database and assets, prefer a documented dry run when available, and verify its import/path assumptions before execution.
