# SmartCatalog Architecture

[Documentation index](README.md) · [Developer guide](DEVELOPMENT.md)

This document describes the current runtime architecture.

## Runtime entry point

Normal startup follows:

```text
run.py
  -> smartcatalog.main.start_ui()
  -> AppState
  -> CatalogDB
  -> create_main_window()
```

`AppState` owns runtime paths and selection state. `CatalogDB` remains the
public persistence facade and opens a SQLite connection per operation, or uses
a caller-supplied connection. Commit behavior is method-specific; a supplied
connection alone does not establish an atomic workflow.

`start_ui()` displays a splash before importing `ui.main_window`, then performs
one catalog refresh before revealing the main window. `MainWindow.__init__`
does not queue a second initial refresh. `CatalogDB.list_items()` bulk-loads
linked images and caches repeated path resolutions for the duration of that
read. Search waits 180 ms after the latest key release and uses bounded text
and timestamp caches. See [PERFORMANCE_REVIEW.md](PERFORMANCE_REVIEW.md) for
measurements and remaining synchronous work.

## Active layers

- `domain/` contains the persisted and UI-facing `CatalogItem` model.
- `db/` contains schema compatibility, path mapping, and item/asset
  repositories behind `CatalogDB`.
- `loader/` contains layout-sensitive PDF and tolerant Excel parsing.
- `services/` contains UI-independent PDF import, Excel catalog import,
  backup, export preflight, workbook reading, and catalog export workflows.
- `ui/controllers/` contains item, form, image, candidate-image, and
  top-level workflow adapters.
- `ui/main_window.py` composes widgets and delegates business workflows.
- `utils/` contains shared normalization, hashing, filename, workbook-image,
  UI-dispatch, dictionary, and export-package policies.

## Dependency direction

```text
Tkinter views/controllers
          |
          v
       services
       /      \
      v        v
   loaders   CatalogDB facade
                |
                v
           repositories
```

Services do not depend on Tkinter. Controllers retain file dialogs, message
boxes, UI-thread dispatch, progress display, and refresh behavior.

The canonical top-level UI callbacks are `on_import_pdf_catalog()`,
`on_import_excel_catalog()`, `on_backup_data()`, and `on_export_catalog()`.
Former callback names and private PDF-helper re-exports were removed after all
tracked bindings and tests migrated to these canonical entry points.

The PDF, Excel, export, and backup workflows dispatch long work to worker
threads; UI decisions return through Tk callbacks/events. Image decoding and
crop-page rendering still include synchronous work. The backup and refresh
buttons are constructed but currently not packed into the toolbar, so the
backup callback is not an exposed user action.

## Persistence and paths

Runtime data lives beside the source project or frozen executable under
`config/database/`. At startup, `AppState` reads `settings.json` and resolves
its `database_path` relative to that directory (or accepts an absolute path)
before `CatalogDB` is created. The **Tải CSDL đã sao lưu...** toolbar button
persists the selected SQLite catalog for subsequent application launches.

Asset and PDF paths below the data directory are stored relatively and
resolved by `CatalogDB`; special tokens such as `excel:...` remain unchanged.
Product code is the stable unique business key.

The default portable catalog unit is the complete `config/database/` directory.
Installation `settings.json` remains there even after selecting an external
database. For that selected database, the active data root becomes the database
parent, or the parent of its `sql/` folder. `assets/` and `catalog_pdfs/` are
resolved below the active root. Preserve both locations if they differ, and
separately preserve any absolute references outside that root. Copying only
SQLite does not include its images or PDFs.

The backup service copies the configured database to `catalog.db` in its
destination, plus assets/PDF folders when present, and makes internal paths
portable in the backup copy. It does not copy installation settings.

SQLite page numbers are 1-based while PyMuPDF indexes are 0-based. Image order
is represented by `item_asset_links`, with the primary image first.

## Build

The supported Windows build is `build_exe.ps1` plus `SmartCatalog.spec`.
`tools/release.py` validates the runnable folder and produces a ZIP containing
the complete `SmartCatalog/` directory plus a separate SHA-256 checksum.
Development databases, imported PDFs, and product images are excluded. A
custom new/empty `-OutputRoot` isolates verification from existing outputs.
CI builds on master pushes, pull requests to master, and manual dispatch; it
uploads a checked ZIP/checksum artifact without publishing a GitHub Release.

See `AGENTS.md` for contributor constraints and `TESTING.md` for the current
validation policy and known behaviors.

## Related documents

- [User guide](USER_GUIDE.md)
- [Developer guide](DEVELOPMENT.md)
- [Windows build guide](../BUILD_EXE.md)
- [Contributor rules](../AGENTS.md)
