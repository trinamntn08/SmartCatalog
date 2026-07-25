# SmartCatalog Refactor Baseline

This document records the starting environment and manual verification process for the behavior-preserving refactor. Update results at each checkpoint; do not use it to redefine expected behavior.

## Baseline commit

- Contributor guide: `23a3121`
- Refactor plan: `6c7b912`
- Phase 0 checkpoint: `4926220`

## Reference environment

Captured from `venv\Scripts\python.exe` on 2026-07-25:

| Component | Version |
|---|---|
| Python | 3.10.5 |
| SQLite | 3.37.2 |
| Tk | 8.6 |
| PyMuPDF | 1.26.7 |
| pandas | 2.3.3 |
| Pillow | 12.1.0 |
| openpyxl | 3.1.5 |
| ReportLab | 4.4.9 |
| python-docx | 1.2.0 |
| rapidfuzz | 3.14.3 |
| python-Levenshtein | 0.27.3 |
| regex | 2026.1.15 |
| NumPy | 2.2.6 |

The checked-in `requirements.txt` is not fully pinned. These versions describe the current reference environment; they do not change the supported dependency policy.

## Automated Phase 0 commands

Run from the repository root:

```powershell
python -m compileall -q run.py src tests
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
git status --short
```

All tests must use `TemporaryProject` or an equivalent explicitly isolated directory. Tests must never construct `AppState()` with the repository root unless the operation is proven read-only.

## Manual source-startup smoke test

Use backed-up or disposable runtime data.

1. Record `git status --short`.
2. Activate the repository virtual environment.
3. Run `python run.py`.
4. Confirm the splash screen appears and closes.
5. Confirm the main window appears without an error dialog.
6. Confirm the item list finishes loading.
7. Select an item if disposable data is available; do not save changes.
8. Close the main window normally.
9. Confirm the process exits.
10. Run `git status --short` again and record any runtime file changes.

Do not run this check against unbacked live catalog data.

## Full manual regression checklist

Use this checklist in the later phases selected by `docs/REFACTOR_PLAN.md`.

### Startup and navigation

- [ ] Source startup and splash
- [ ] Main item list load
- [ ] Search/filter options
- [ ] Column sort
- [ ] Column movement
- [ ] Column visibility
- [ ] Normal shutdown
- [ ] Restart and persisted PDF selection

### Item editing

- [ ] Select an item
- [ ] Edit and save all supported fields
- [ ] Unsaved-change save choice
- [ ] Unsaved-change discard choice
- [ ] Unsaved-change cancel choice
- [ ] Add an item
- [ ] Delete a disposable item
- [ ] Validate and unvalidate an item
- [ ] Validation timestamp behavior

### PDF

- [ ] Select and copy a new catalog PDF
- [ ] Reuse the selected PDF
- [ ] Update an existing item
- [ ] Skip an existing item
- [ ] Apply update decision to all
- [ ] Validated-item protection
- [ ] Excel-image protection
- [ ] Candidate image extraction
- [ ] Candidate image assignment
- [ ] Manual PDF crop

### Excel database update

- [ ] Import descriptions from one sheet
- [ ] Import descriptions from multiple sheets
- [ ] Exact code matching
- [ ] Unique normalized code matching
- [ ] Missing/ambiguous code handling
- [ ] Embedded image extraction
- [ ] Duplicate image handling
- [ ] Update/skip/apply-to-all decisions

### Images

- [ ] Add image file
- [ ] Remove linked image
- [ ] Rotate left/right
- [ ] Drag reorder
- [ ] Primary image follows UI order
- [ ] Thumbnail and large preview rendering
- [ ] Provenance label

### Backup and export

- [ ] Backup database
- [ ] Backup assets, PDFs, and settings
- [ ] Read export codes and quantities
- [ ] VI-only descriptions
- [ ] EN-only descriptions
- [ ] Bilingual descriptions
- [ ] Missing-data preflight
- [ ] Save-and-next in preflight
- [ ] Cancel preflight
- [ ] Continue with incomplete data
- [ ] Product image order/rotation option
- [ ] Workbook opens in desktop Excel
- [ ] Branding and print settings

### Frozen application

- [ ] `build_exe.ps1` succeeds
- [ ] Complete distribution starts in a writable directory
- [ ] First-launch runtime directories are created
- [ ] PDF import
- [ ] Excel database update
- [ ] Image preview
- [ ] Export
- [ ] Restart

## Checkpoint history

| Phase | Commit | Automated result | Manual result | Notes |
|---|---|---|---|---|
| 0 | `4926220` | Passed: compile, imports, 7 tests, diff check | Not run: interactive GUI unavailable during automated checkpoint | Disposable fixture/snapshot harness and baseline documentation complete |
| 1 | `3326d1e` | Passed: compile, imports, 23 tests, diff check | Not required: characterization used fresh and upgraded disposable databases | Current schema, mapping, paths, ordering, and mixed transaction behavior locked down |
