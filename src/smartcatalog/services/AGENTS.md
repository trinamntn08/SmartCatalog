# Service scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `src/smartcatalog/services/`.

- Services must remain importable and callable without Tkinter.
- Accept paths, state, database facades, decisions, and progress callbacks as
  explicit inputs; return typed result objects for top-level workflows.
- Do not show dialogs or access widgets. Controllers own UI-thread dispatch and
  translate user decisions into callbacks.
- Use `CatalogDB` or repository operations for persistence. Do not introduce
  new raw SQL in services; preserve explicit caller-owned transactions where
  existing workflows require atomic groups.
- Close documents, workbooks, images, connections, and temporary resources
  deterministically, including failure paths.
- Exercise workflow changes with generated fixtures and disposable directories.
