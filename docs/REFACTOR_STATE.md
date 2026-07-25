# SmartCatalog Refactor Session State

This is the authoritative resume point for the behavior-preserving refactor. Read this file before starting work in every new session.

## Current state

```text
Program status: IN PROGRESS
Current branch: master
Last completed phase: Phase 2 — Characterize Excel and dictionary behavior
Last checkpoint commit: current HEAD (Checkpoint 2)
Next permitted phase: Phase 3 — Characterize PDF and image behavior
Production refactoring permitted: NO
Reason: Phases 3 and 4 characterization gates are not complete
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
| 2 | Current HEAD (Checkpoint 2) | Excel parsing, matching, embedded-image import, and dictionary fill-only behavior characterized |

Current automated baseline:

- 35 tests pass, including resource-warning enforcement.
- `python -m compileall -q run.py src tests` passes.
- Importing `smartcatalog` and `smartcatalog.main` with the repository virtual environment passes.
- `git diff --check` passes.
- No production application code has been changed by the refactor program.

Known validation limitation:

- The interactive GUI smoke test has not been run during the automated checkpoints. Use backed-up or disposable runtime data when it is performed.

## Next work: Phase 3 only

Follow the full Phase 3 definition in `docs/REFACTOR_PLAN.md`.

Phase 3 may add tests and generated or explicitly approved sanitized fixtures for:

- zero-based PyMuPDF to one-based database page conversion;
- item code, category, author, dimension, and description extraction;
- reproducible single- and multi-column PDF layouts;
- pages without products or usable images;
- nearest-image selection and image conversion/hashing;
- validated-item and Excel-image skip behavior;
- existing-item update/skip callbacks;
- repeated imports and document closure.

Phase 3 must not:

- tune extraction coordinates, clustering, geometry, or regexes;
- change production PDF import or database behavior;
- begin utility extraction or other structural refactoring;
- inspect unapproved live/runtime PDFs;
- proceed to Phase 4 before Phase 3 tests, validation, state update, and checkpoint commit are complete.

Suggested Phase 3 checkpoint commit:

```text
test: characterize PDF extraction and image linking
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

5. Confirm that the documented Checkpoint 2 commit or a later checkpoint is in the current branch history.
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
