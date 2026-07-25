# SmartCatalog Architecture

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
public persistence facade and opens a SQLite connection per operation or
caller-owned transaction.

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

## Persistence and paths

Runtime data lives beside the source project or frozen executable under
`config/database/`. Database file paths below that directory are stored
relatively and resolved by `CatalogDB`; special tokens such as `excel:...`
remain unchanged. Product code is the stable unique business key.

SQLite page numbers are 1-based while PyMuPDF indexes are 0-based. Image order
is represented by `item_asset_links`, with the primary image first.

## Build

The supported Windows build is `build_exe.ps1` plus `SmartCatalog.spec`.
Deliver the complete `dist/SmartCatalog/` directory. Development databases,
imported PDFs, and product images are intentionally excluded.

See `AGENTS.md` for contributor constraints and
`docs/REFACTOR_BASELINE.md` for characterization and validation evidence.
