# SmartCatalog Contributor Guide

## Project summary

SmartCatalog is a Windows-oriented Python desktop application for building and reviewing a product catalog. It imports product data and images from PDF and Excel files, stores normalized records in SQLite, lets users edit and validate records in a Tkinter UI, and exports post-processed Excel/PDF output.

The UI text and business data are largely Vietnamese. Preserve Unicode source text and save Python and documentation files as UTF-8.

`to_integrate/` is not part of the running application. Do not read from it, import from it, edit it, or add runtime fallbacks to it. Runtime resources must live under `config/database/` or the appropriate application package directory.

## Repository map

- `run.py`: source and frozen-executable entry point; adds the project/source roots to `sys.path`.
- `src/smartcatalog/main.py`: creates the Tk root, splash screen, application state, database, and main window.
- `src/smartcatalog/state.py`: `AppState`, `CatalogItem`, application paths, directory creation, and persisted PDF selection.
- `src/smartcatalog/db/catalog_db.py`: SQLite schema, compatibility migrations, path normalization, item CRUD, assets, and item/asset links.
- `src/smartcatalog/loader/`: PDF and Excel ingestion.
  - `extract_item.py`: layout-specific extraction of product fields from PDF pages.
  - `pdf_loader.py`: page scan, item upsert, nearest-image extraction, and asset linking.
  - `excel_loader.py`: flexible header/code detection and Excel description loading.
- `src/smartcatalog/ui/main_window.py`: main Tkinter composition and high-level import, backup, and export workflows.
- `src/smartcatalog/ui/controllers/`: mixins for the item list, form, images, PDF preview, and candidate images.
- `src/smartcatalog/ui/pdf_crop_window.py`: manual PDF image cropping.
- `src/smartcatalog/utils/post_processing.py`: formatted Excel output and low-level XLSX/XML header-image injection.
- `src/smartcatalog/utils/description_dictionary.py`: imports bilingual descriptions from `config/database/dictionary.csv` into empty database fields without overwriting user edits.
- `src/smartcatalog/utils/pdf_exporter.py`: ReportLab PDF exports.
- `src/smartcatalog/ui/export_review_dialog.py`: pre-export review of missing VI/EN descriptions, images, and unknown product codes.
- `scripts/`: one-off database/asset path migration utilities; review carefully before running.
- `input/`: sample/manual input files.
- `output/`: generated exports.
- `config/database/`: runtime data, including SQLite, settings, selected PDFs, and imported/cropped images.
- `docs/` and `icons/`: user documentation and application artwork.

There is currently no automated test suite or packaging metadata beyond `requirements.txt`.

## Runtime and data model

The normal startup flow is:

`run.py` -> `smartcatalog.main.start_ui()` -> `AppState` -> `CatalogDB` -> `create_main_window()`.

Runtime data lives beneath `<project_dir>/config/database/`:

- `sql/catalog.db`
- `settings.json`
- `catalog_pdfs/`
- `assets/excel_import/`
- `assets/pdf_import/`
- `assets/manual_import/`

The primary SQLite entities are:

- `items`: unique product `code`, extracted PDF fields, Excel descriptions, source PDF/page, and validation state.
- `assets`: image path, PDF/page origin, optional bounding box, source, and hash.
- `item_asset_links`: ordered/primary item-image associations plus match method, score, and verification state.

Database paths beneath the data directory are intentionally stored as relative paths through `CatalogDB.to_db_path()` and resolved with `from_db_path()`. Keep this behavior so databases remain portable when the project or packaged application is moved.

## Setup and common commands

Use PowerShell from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

If PowerShell blocks activation, use a process-scoped policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

Quick non-GUI validation:

```powershell
python -m compileall -q run.py src
python -c "import sys; sys.path.insert(0, 'src'); import smartcatalog"
```

The application must also be smoke-tested manually for UI or workflow changes. Use disposable/sample input and a backed-up runtime database. Relevant checks usually include startup, item selection/edit/save, PDF or Excel import, image add/remove/reorder, validation state, and export.

The README documents the current `auto-py-to-exe` build setup. A frozen build must include `src` on the search path and collect PyMuPDF (`fitz`/`pymupdf`).

## Engineering rules

- Target the Python version used by the checked-in `venv`/deployment environment; do not add dependencies without updating `requirements.txt`.
- Use `pathlib.Path` for filesystem work and derive runtime paths from `AppState.project_dir`, `data_dir`, or `assets_dir`. Do not hard-code developer-machine paths.
- Preserve both source execution and frozen executable behavior (`sys.frozen` and `sys.executable`).
- Never commit or casually rewrite runtime data in `config/`, `data/`, `input/`, or `output/`. These may contain large, local, or user-generated files even when ignored by Git.
- Do not delete or rebuild `catalog.db`, asset directories, settings, or imported PDFs as a side effect of a code change.
- Preserve backward compatibility for existing databases. Schema additions belong in `SCHEMA_SQL` and, where needed, `_ensure_columns()` or an explicit migration.
- Product codes are the stable unique key. Reuse the existing normalization helpers when matching codes from spreadsheets or PDFs.
- PDF page numbers stored in the database are 1-based; PyMuPDF page indexes are 0-based. Convert explicitly at boundaries.
- Image ordering matters: the first linked image may be marked primary. Keep asset records and `item_asset_links` synchronized when adding, deleting, or reordering images.
- Keep image provenance values compatible with current UI behavior (`excel`, `extract`, `page_extract`, `manual_crop`, and `add`) unless performing a coordinated migration.
- Treat SQLite description fields as the source of truth. `config/database/dictionary.csv` may seed empty VI/EN fields, but must never overwrite non-empty user data automatically.
- `CatalogDB` deliberately does not retain a shared SQLite connection. Open a connection per operation/thread, pass it into grouped DB methods, commit intentionally, and close it in `finally`.
- Long PDF/Excel/image operations run in background threads. Tkinter widgets and variables must only be touched on the UI thread; marshal updates with `root.after(...)` or the existing safe UI helpers.
- Keep strong references to `ImageTk.PhotoImage` objects or Tkinter will display blank images.
- Close PyMuPDF documents and PIL image contexts deterministically.
- Avoid broad exception swallowing in new logic. Existing best-effort UI/icon code uses it in places, but new failures should provide actionable status or dialog messages.
- Keep `main_window.py` focused on layout and workflow coordination where practical; put reusable panel behavior in the existing controller mixins and data operations in loaders/DB utilities.

## Change workflow

Before editing:

1. Check `git status --short`; the worktree may contain user changes.
2. Search application code under `src/`; exclude `to_integrate/`.
3. Trace the complete flow across UI, state, DB, and filesystem before changing persisted behavior.

After editing:

1. Review the diff and ensure unrelated/local runtime files are untouched.
2. Run `python -m compileall -q run.py src`.
3. Run focused imports or small read-only checks for the changed module.
4. Manually smoke-test GUI/data workflows when feasible and report anything not tested.

For changes involving persistence, test against a copy of the database or a temporary project directory. Validate both a newly created schema and an older schema upgraded in place.

## Current caveats

- PDF extraction is catalog-layout-specific; small coordinate, clustering, or regex changes can affect many products. Test representative pages, including pages with multiple product columns and unusual dimensions.
- Excel ingestion accepts variable header rows and column names. Preserve that tolerant detection unless the task explicitly narrows the accepted format.
- Some modules contain legacy or mojibake-looking comments/messages. Do not perform unrelated mass encoding rewrites; edit only verified strings and keep files UTF-8.
- `post_processing.py` edits the XLSX ZIP/XML package after using openpyxl. Changes there should verify that the workbook opens in Excel and retains images, relationships, print settings, and branding.
- No automated regression coverage exists yet. Prefer small, separable changes and document manual verification.
