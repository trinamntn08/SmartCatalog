# Utility scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `src/smartcatalog/utils/`.

- Keep general utilities independent of DB, loader, service, and UI layers.
  The narrowly named `ui_dispatch.py` may adapt a supplied Tk-compatible root
  but must not own widgets or dialogs.
- Preserve established normalization, hashing, filename, and workbook-image
  contracts; product-code ambiguity must remain explicit.
- Treat `post_processing.py` changes as package-format changes. Verify ZIP/XML
  relationships, content types, VML, images, branding, and desktop Excel
  compatibility with disposable workbooks.
- Close images, workbooks, archives, and temporary resources deterministically.
- Do not turn convenience helpers into hidden filesystem or database state.
