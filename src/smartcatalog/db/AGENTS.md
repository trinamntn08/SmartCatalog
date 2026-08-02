# Persistence scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `src/smartcatalog/db/`.

- Keep `CatalogDB` as the public persistence facade. Put reusable SQL and row
  mapping in repositories rather than adding SQL to UI controllers.
- Open one SQLite connection per operation or thread. A caller that supplies a
  connection owns grouped commits and closing it; preserve each public method's
  established commit contract.
- Keep foreign keys enabled and preserve item, asset, and link synchronization.
- Add fresh-schema changes to `SCHEMA_SQL` and existing-database compatibility
  to the explicit compatibility path. Never use a live catalog for migration
  tests.
- Preserve portable path mapping and non-file tokens such as `excel:...`.
- Test fresh databases and in-place upgrades using disposable directories.
