# Loader scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `src/smartcatalog/loader/`.

- Keep loaders focused on tolerant input parsing and layout-sensitive
  extraction. Workflow orchestration belongs in services and Tk adaptation
  belongs in UI controllers.
- Do not import `smartcatalog.services`, `smartcatalog.ui`, or persistence
  modules from loaders.
- Preserve explicit conversion between 1-based catalog page numbers and
  0-based PyMuPDF indexes.
- Treat coordinate, clustering, regular-expression, header-detection, and
  nearest-image changes as high-impact compatibility changes.
- Exercise changes with generated single- and multi-column PDFs, unusual page
  dimensions, variable Excel headers, Unicode text, and resource-closure tests.
