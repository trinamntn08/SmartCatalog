# Active Error and Resource Handling Audit

This audit records the Phase 11 review of active startup and workflow modules.
Legacy/unwired modules listed in `AGENTS.md` were not changed.

## Changed in Phase 11

| Area | Classification | Action and coverage |
|---|---|---|
| Backup database/directory/copies | User-recoverable error | `BackupError` now identifies the failed source and destination operation. Missing-database and successful-copy tests use disposable paths. |
| Delayed backup error dialog | User-recoverable error | The scheduled callback retains the exception value after the `except` block. A delayed-root test executes the callback after stack unwinding. |
| PDF image conversion and saving | Resource lifecycle | Source and derived Pillow images are closed deterministically. Existing conversion, PNG-output, hash, and import tests cover equivalent output. |
| Legacy-compatible page image extraction helper | Resource lifecycle | Pillow images are closed deterministically while the helper's paths and PNG output remain unchanged. |

## Reviewed and intentionally retained

| Area | Classification | Reason retained |
|---|---|---|
| Optional startup icon, splash, and window decoration | Intentional best effort | Failure must not prevent application startup. |
| Widget cleanup, geometry, clipboard, and delayed UI updates | Intentional best effort | Widgets may already be destroyed during normal shutdown or popup dismissal. |
| Workbook embedded-image probing | Intentional best effort | Unsupported or unreadable individual images are skipped by the established tolerant import policy; warnings are returned where supported. |
| PDF nearest-image probing | Intentional best effort | Malformed/unsupported individual PDF images currently produce no candidate rather than aborting the catalog import. |
| Post-processing individual product images | Intentional best effort | Missing or unreadable product images are characterized as skipped while the workbook continues. |
| Item/image controller preview rendering | User-recoverable UI path | Existing handlers already report or safely omit preview failures; changing messages requires dedicated interactive fixtures. |

## Deferred

- The legacy/unwired modules covered by the Phase 12 disposition were removed.
- Interactive failure dialogs, destroyed-widget races, locked Excel files, and
  desktop Excel validation remain manual checks.
- The characterized PDF asset-link transaction bug is intentionally unchanged.
