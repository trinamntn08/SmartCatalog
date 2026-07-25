# Naming and Encoding Audit

Phase 13 reviewed active workflow names, temporary compatibility helpers,
placeholder expressions, and Python source encoding.

## Workflow callback migration

| Canonical callback | Former callback removed after migration |
|---|---|
| `on_import_pdf_catalog()` | `on_choose_pdf_and_build_db()` |
| `on_import_excel_catalog()` | `on_build_excel_db()` |
| `on_export_catalog()` | `on_search_images_from_excel()` |

Toolbar bindings and characterization tests use the canonical names. A
post-refactor tracked-reference audit found no production callers for the
former names, so their temporary delegates were removed.

## Removed obsolete private wrappers

The private `main_window.py` wrappers around code/header normalization,
filename sanitization, workbook-image loading/anchors, and normalized-code
index construction had no production callers after Phases 5–10. Tests now
import the canonical utility modules directly, and the wrappers were removed.

The no-op ellipsis in the `MainWindow` class body was also removed.

The temporary private PDF image-helper re-exports in `pdf_loader.py` were
removed after tests migrated to the canonical `pdf_image_extractor.py`
functions.

## Encoding result

All active Python source decodes strictly as UTF-8. A scan for common UTF-8
decoded-as-Windows-1252 mojibake signatures found no matches. Therefore Phase
13 made no Vietnamese text changes and performed no encoding conversion.

The automated encoding test scans source bytes and common mojibake markers.
Interactive native-language UI review remains part of the manual checklist.
