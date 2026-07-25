# SmartCatalog Refactor Session State

This is the authoritative resume point for the behavior-preserving refactor. Read this file before starting work in every new session.

## Current state

```text
Program status: IN PROGRESS
Current branch: refactor/behavior-preserving-cleanup
Last completed phase: Phase 8 — Extract Excel export service
Last checkpoint commit: this checkpoint commit (Checkpoint 8)
Next permitted phase: Phase 9 — Extract PDF import service
Production refactoring permitted: YES, within the next permitted phase only
Reason: Characterization gates 0–4 and refactor gates 5–8 are complete
Tracked worktree expected: clean
Last updated: 2026-07-25
```

Existing untracked local directories may include `build/`, `dist/`, `input/`, `output/`, `scripts/`, and `to_integrate/`. They are not part of the refactor checkpoints. Preserve them and do not stage, inspect, or modify them unless the user explicitly places them in scope. Never inspect `to_integrate/`.

## Completed checkpoints

| Phase | Commit | Result |
|---|---|---|
| Plan baseline | `6c7b912` | Refactor phases and mandatory gates established |
| 0 | `4926220` | Disposable test harness, generated fixtures, snapshots, environment baseline, and manual checklist |
| 1 | `3326d1e` | Database schema, migration, mapping, path, item, asset, ordering, and transaction behavior characterized |
| 2 | `5d6fa34` | Excel parsing, matching, embedded-image import, and dictionary fill-only behavior characterized |
| 3 | `fdadc52` | PDF field extraction, page numbering, image selection, import skip policy, repeat behavior, and resource closure characterized |
| 4 | `9488c47` | Export matching, preflight, descriptions, images, workbook structure, branding, and package relationships characterized |
| 5 | `c24589a` | Active domain model and proven normalization, filename, hashing, workbook-image, and Tk-dispatch policies extracted with compatibility entry points |
| 6 | `6858482` | Schema, path mapping, item mapping/CRUD, and asset/link operations separated behind the existing CatalogDB facade |
| 7 | `18869cf` | Excel parsing, embedded-image extraction, database updates, and typed import results extracted behind a thin Tk UI adapter |
| 8 | This checkpoint commit | Workbook reading, export preflight, matching, output generation, branding, and typed results extracted behind a thin Tk UI adapter |

Current automated baseline:

- 77 tests pass, including resource-warning enforcement, compatibility-wrapper equivalence, database module-boundary checks, Excel import service equivalence, and Tk-free export service coverage.
- `python -m compileall -q run.py src tests` passes.
- Importing `smartcatalog` and `smartcatalog.main` with the repository virtual environment passes.
- `git diff --check` passes.
- Active production behavior is now separated through the completed Phase 5–8 boundaries while compatibility entry points remain in place.

Known validation limitation:

- The interactive GUI smoke test has not been run during the automated checkpoints. Use backed-up or disposable runtime data when it is performed.
- Generated PDFs cover reproducible single- and two-column layouts, but representative real catalog layouts remain a manual-only validation risk.
- Current PDF import writes the extracted PNG file but rolls back the asset/link rows because the caller-owned SQLite connection is not committed after linking. Phase 3 characterizes this existing behavior; fix it only as a separate approved bug change.
- Phase 4 reopens generated workbooks with openpyxl and validates their XLSX/XML relationships, but desktop Excel visual inspection was not available in the automated checkpoint.

## Next work: Phase 9 only

Follow the full Phase 9 definition in `docs/REFACTOR_PLAN.md`.

Phase 9 may extract the PDF import workflow into:

- an explicit parsing, update-policy, persistence, and image-assignment pipeline;
- injected existing-item decisions and status callbacks;
- a compatibility wrapper retaining the current public loader entry point.

Phase 9 must not:

- tune extraction geometry, regexes, page conversion, matching, hashes, paths, provenance, ordering, or skip rules;
- fix the recorded PDF asset-link transaction bug;
- redesign transaction boundaries;
- begin backup or broader `MainWindow` reduction;
- proceed to Phase 10 before Phase 9 tests, validation, state update, and checkpoint commit are complete.

Suggested Phase 9 checkpoint commit:

```text
refactor: extract PDF import service
```

## New-session resume procedure

At the beginning of a new session:

1. Read `AGENTS.md`.
2. Read this entire file.
3. Read the current phase and mandatory gate sections in `docs/REFACTOR_PLAN.md`.
4. Run:

   ```powershell
   git status --short
   git log -5 --oneline --decorate
   ```

5. Confirm that the documented Checkpoint 8 commit or a later checkpoint is in the current branch history.
6. Preserve all unrelated tracked and untracked work.
7. Run the current automated baseline before editing:

   ```powershell
   python -m compileall -q run.py src tests
   .\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
   .\venv\Scripts\python.exe -m unittest discover -s tests -v
   git diff --check
   ```

8. Work only on the `Next permitted phase` recorded above.
9. Stop if repository state or test results conflict with this file; reconcile the discrepancy before editing.

## Mandatory state update at every checkpoint

Before committing a completed phase:

1. Update `docs/REFACTOR_PLAN.md` progress tracker.
2. Update `docs/REFACTOR_BASELINE.md` checkpoint history and validation results.
3. Update this file:
   - last completed phase;
   - checkpoint reference;
   - next permitted phase;
   - current automated baseline;
   - limitations and blockers;
   - production-refactoring permission.
4. Run the complete phase gate.
5. Commit code, tests, and all three tracking documents together.
6. After the commit, verify the actual commit hash with `git log -1 --oneline`.

Because a commit cannot contain its own final hash, the state file may say `this checkpoint commit` inside that commit. At the start of the next phase, replace it with the actual hash while updating the state. Git history remains the final authority.

## Stop conditions

Do not advance when:

- the current phase gate fails;
- required fixtures would use unbacked live data;
- a structural refactor would begin before Phase 4 is complete;
- observed behavior conflicts with an existing characterization test;
- an unrelated tracked change overlaps the phase;
- the next action would require reading `to_integrate/`;
- a discovered issue would mix a bug fix into a characterization/refactor checkpoint.

Record blockers here and leave `Next permitted phase` unchanged.
