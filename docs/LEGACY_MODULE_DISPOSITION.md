# Legacy Module and Dependency Disposition

[Documentation index](README.md)

This is the active reference for components that must remain removed unless a
separately scoped change deliberately replaces the supported architecture.
The current module map is documented in `ARCHITECTURE.md` and `AGENTS.md`.

The removal audit covered tracked application code, tests, build configuration,
and documentation. Runtime/generated/user-data directories and
`to_integrate/` were excluded.

## Removed modules

| Removed path | Evidence and active replacement |
|---|---|
| `src/smartcatalog/db/update_db_from_pdf.py` | No tracked caller. It used an incompatible image-BLOB/schema workflow. Active PDF import is `services/pdf_import.py` through `ui/controllers/pdf_import_adapter.py` and the current `CatalogDB` asset/link schema. |
| `src/smartcatalog/loader/pdf_loader.py` | Its remaining responsibility was a Tk status/preview adapter and introduced a reverse loader-to-service dependency. The adapter moved to `ui/controllers/pdf_import_adapter.py`; parsing remains in loaders and orchestration remains in `services/pdf_import.py`. |
| `src/smartcatalog/extracter/extract_key_info_from_pdf.py` | No tracked caller. Active field extraction is `loader/extract_item.py`; PDF orchestration is `services/pdf_import.py`. The now-empty `extracter` package marker was also removed. |
| `src/smartcatalog/matcher/pdf_matcher.py` | No tracked caller. Active matching policies live in the Excel services and PDF import pipeline. The now-empty `matcher` package marker was also removed. |
| `src/smartcatalog/ui/controllers/pdf_viewer_controller.py` | No tracked caller and not mixed into `MainWindow`. Active manual PDF cropping is `ui/pdf_crop_window.py`; candidate assignment is `ui/controllers/candidates_controller.py`. |
| `src/smartcatalog/utils/pdf_exporter.py` | No tracked caller. Supported export is Excel post-processing through `services/catalog_export.py` and `utils/post_processing.py`. |
| `src/smartcatalog/config/settings.py` | No tracked caller. Runtime path/settings behavior is owned by `state.py`; its two experimental constants had no consumer. |

No capability from these modules was migrated or revived because the
supported workflows already have active replacements.

## Removed requirements

| Requirement | Evidence |
|---|---|
| `reportlab` | Imported only by the removed, unwired PDF exporter. |
| `python-docx` | No import in tracked source, tests, build scripts, or supported documentation commands. |
| `rapidfuzz` | No import in tracked source, tests, build scripts, or supported documentation commands. |
| `python-Levenshtein` | No import in tracked source, tests, build scripts, or supported documentation commands. |
| `regex` | No import in tracked source, tests, build scripts, or supported documentation commands; active code uses the standard-library `re` module. |
| `numpy` | No import in tracked source, tests, build scripts, or supported documentation commands. |

Retained runtime requirements are `pandas`, `PyMuPDF`, `Pillow`, and
`openpyxl`. PyInstaller remains a build-environment requirement documented in
`BUILD_EXE.md`, not an application runtime requirement.

## Maintenance rules

- Do not restore a removed implementation solely for compatibility with an
  untracked or unsupported caller.
- Update this file when a deliberate change removes another module or changes
  one of the listed active replacements.
- Keep the architecture-boundary and legacy-disposition tests aligned with the
  supported module map.
