# Post-refactor Cleanup Audit

Date: 2026-07-25

This audit reviewed tracked application code and documentation after the
Phase 14 checkpoint. Runtime data, generated output, and `to_integrate/` were
excluded.

## Removed

- Two unreferenced private PDF functions that implemented an obsolete
  page-wide image extraction/linking approach.
- Four private PDF image-helper aliases used only by migration-era tests.
  Tests now import the canonical helpers from `pdf_image_extractor.py`.
- The migration-era Excel-loader normalization re-export; callers use
  `utils/code_normalization.py` directly.
- Three temporary workflow callback delegates after toolbar bindings and all
  tracked callers migrated to the canonical callback names.
- Unused `AppState` fields for old parser caches, busy/error state, and an
  uncalled cache-clear method.
- Stale migration comments and controller contract references.

## Deliberately retained

- `CatalogDB` as the public persistence facade.
- Live schema compatibility upgrades for existing SQLite databases.
- `CatalogItem` availability through `state.py`, which is still used there for
  active state annotations and remains a low-cost compatibility import.
- `build_or_update_db_from_pdf()` as the active UI-to-service adapter.
- XLSX `legacyDrawingHF` XML, which is an Excel header-image mechanism rather
  than obsolete application code.
- Empty `__init__.py` files that define importable source and test packages.

Historical refactor-plan and baseline statements remain as a record of what
was true at each checkpoint. Current architecture guidance is maintained in
`AGENTS.md` and `docs/ARCHITECTURE.md`.
