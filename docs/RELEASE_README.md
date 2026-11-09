# SmartCatalog for Windows

Extract the complete archive to a writable folder, then open
`SmartCatalog.exe`. Keep `_internal`, `icons`, and the executable together.
Do not run the application from inside the ZIP or a read-only installation
folder. The splash appears while the application loads the catalog.

The package starts with an empty catalog. First launch creates
`config/database/settings.json`, `sql/catalog.db`, `assets/`, and
`catalog_pdfs/` under `config/database/` beside the executable.

To open an existing catalog, use **Tải CSDL đã sao lưu...** and select its
SQLite database. Keep that database with its associated `assets/` and
`catalog_pdfs/` folders. If the database is inside a folder named `sql`, those
folders belong beside `sql`; otherwise they belong beside the database file.
Your selection is saved in this installation's `config/database/settings.json`.

Before an upgrade, close SmartCatalog and back up the entire existing
`config/database/` directory. If you selected a catalog outside that directory,
back up its complete data folder as well. Replace application files while
preserving both locations. Never delete a catalog folder to reset the app.

Use `.xlsx` workbooks for import and export; convert older `.xls` files first.
Review extracted PDF fields and images before validating products, and open
exported workbooks in desktop Excel to check images and print layout.

The backup toolbar button is currently hidden. Back up manually with the app
closed by copying the complete active catalog data folder and the installation
settings to a separate safe location.

See the [online user guide](https://github.com/trinamntn08/SmartCatalog/blob/master/docs/USER_GUIDE.md)
for detailed workflows. Build and publication instructions are maintained in
the repository's `BUILD_EXE.md`; a CI artifact is a test build, not an automatic
GitHub Release publication.
