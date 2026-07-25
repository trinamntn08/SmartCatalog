# SmartCatalog Behavior-Preserving Refactor Plan

## Objective

Refactor SmartCatalog into code that is easier to read, test, and maintain while preserving the application's current observable behavior.

This is an incremental plan, not a rewrite. Every phase must be implemented, tested, validated, reviewed, and committed as its own checkpoint before work begins on the next phase.

The authoritative cross-session resume point is `docs/REFACTOR_STATE.md`. Update it at every checkpoint together with this plan and `docs/REFACTOR_BASELINE.md`.

## Non-regression contract

Unless a separately approved change explicitly says otherwise, the refactor must preserve:

- Source-mode and frozen-executable startup.
- Existing runtime paths under `config/database/`.
- Compatibility with existing SQLite databases.
- Product-code matching and uniqueness rules.
- Exact database field meanings and defaults.
- Relative database path storage and `excel:...` tokens.
- PDF page-number conversion and extraction behavior.
- Validated-item and Excel-image protections during PDF import.
- Excel header and code-column tolerance.
- Description precedence and dictionary fill-only behavior.
- Image provenance, deduplication, link ordering, and primary-image behavior.
- UI-thread/background-thread boundaries.
- Existing dialogs, choices, workflows, and user-visible results.
- Excel output structure, images, branding, relationships, and print settings.

Structural cleanup and intentional behavior changes must never be mixed in one phase.

## Repository safety rules

- Never read from, edit, import from, or add fallbacks to `to_integrate/`.
- Never use the live `config/database/` contents as test data.
- Do not edit generated `build/`, `dist/`, `input/`, or `output/` contents.
- Use temporary project directories and generated or explicitly approved sanitized fixtures.
- Check `git status --short` before and after every phase.
- Preserve unrelated tracked and untracked user files.
- Do not begin a phase while the previous checkpoint is incomplete.

## Mandatory gate for every phase

A phase is complete only when all of the following are true:

1. The phase scope is fully implemented without unrelated cleanup.
2. New or changed behavior boundaries have automated coverage.
3. Existing automated tests pass.
4. Compilation and focused imports pass.
5. Required manual checks pass, or an explicit blocker is recorded.
6. `git diff` contains only intended files.
7. Runtime, generated, and user-data directories are untouched.
8. The phase report records commands, results, limitations, and remaining risks.
9. The phase is committed as an independent Git checkpoint.
10. `git status --short` is clean for tracked files after the commit.

Minimum commands:

```powershell
python -m compileall -q run.py src tests
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
git status --short
```

If a required check fails, stop the phase. Fix it within the same phase or revert the phase to its previous checkpoint. Do not continue on the promise of fixing it later.

## Checkpoint record

Complete this record for every phase in the phase's commit message, pull-request description, or project log:

```text
Phase:
Status: NOT STARTED | IN PROGRESS | BLOCKED | COMPLETE
Baseline commit:
Checkpoint commit:
Files changed:
Behavior intended to change: None
Automated tests added/updated:
Automated test result:
Manual validation performed:
Manual validation not performed:
Database fixtures used:
PDF/Excel fixtures used:
Frozen build checked:
Known limitations:
Rollback command/commit:
Approved to start next phase: YES | NO
```

## Progress tracker

| Phase | Scope | Status | Checkpoint |
|---|---|---|---|
| 0 | Baseline and test harness | Complete | Checkpoint 0 commit |
| 1 | Characterize database behavior | Complete | Checkpoint 1 commit |
| 2 | Characterize Excel and dictionary behavior | Complete | Checkpoint 2 commit |
| 3 | Characterize PDF and image behavior | Complete | Checkpoint 3 commit |
| 4 | Characterize export and UI workflows | Complete | Checkpoint 4 commit |
| 5 | Extract pure shared utilities | Complete | Checkpoint 5 commit |
| 6 | Split database internals behind `CatalogDB` | Complete | Checkpoint 6 commit |
| 7 | Extract Excel database-import service | Complete | Checkpoint 7 commit |
| 8 | Extract Excel export service | Complete | Checkpoint 8 commit |
| 9 | Extract PDF import service | Complete | Checkpoint 9 commit |
| 10 | Extract backup service and reduce `MainWindow` | Complete | Checkpoint 10 commit |
| 11 | Improve error and resource handling | Not started | — |
| 12 | Resolve legacy code and dependencies | Not started | — |
| 13 | Verified naming and encoding cleanup | Not started | — |
| 14 | Full regression and frozen release validation | Not started | — |

Update this table only after the corresponding checkpoint has been validated and committed.

---

## Phase 0 — Establish the baseline and test harness

### Purpose

Create a repeatable safety net without moving or changing application logic.

### Implementation

- Add a `tests/` package using standard-library `unittest`.
- Add helpers that create disposable project directories.
- Add fixture builders for SQLite, XLSX, images, and small generated PDFs.
- Add helpers to compare:
  - SQLite table schemas and normalized row contents.
  - Asset files and content hashes.
  - Workbook sheet names, cells, merges, dimensions, images, and relationships.
- Document the manual smoke-test procedure.
- Record the current Python and major dependency versions from the repository virtual environment.
- Do not add production dependencies.

### Automated validation

- Confirm test discovery works with an empty smoke test.
- Confirm temporary fixtures are created outside live runtime data.
- Confirm test teardown removes only its own temporary directory.
- Run compilation and import checks.

### Manual validation

- Launch the application from source without changing data.
- Confirm the main window opens and the item list loads.
- Close the application normally.

### Checkpoint 0

Required evidence:

- Test harness passes.
- No production application files changed unless required solely for testability and explicitly reviewed.
- Manual smoke-test document exists.
- Commit suggestion: `test: establish refactor safety harness`

Do not begin Phase 1 until Checkpoint 0 is committed.

---

## Phase 1 — Characterize database behavior

### Purpose

Lock down existing persistence behavior before splitting `catalog_db.py`.

### Implementation and tests

Add tests for:

- Fresh creation of `items`, `assets`, and `item_asset_links`.
- Upgrade of a representative older `items` schema.
- Unique product-code enforcement.
- All item defaults and row-to-`CatalogItem` mapping.
- `to_db_path()` and `from_db_path()` for:
  - paths inside the data directory;
  - paths outside the data directory;
  - relative paths;
  - empty values;
  - `excel:...` tokens.
- `upsert_by_code()` field-preservation and overwrite behavior.
- Validation flags and timestamp preservation/reset behavior.
- English and Vietnamese description update rules.
- Asset insertion/deduplication.
- Item/asset link idempotency.
- Link removal and cascading item deletion.
- Primary-image ordering.
- Reorder behavior and preservation of match metadata.
- Current transaction behavior for owned and caller-supplied connections.

### Validation

- Run every test against a fresh temporary database.
- Run migration tests against an older temporary schema.
- Compare schemas and data before/after reopen.
- Confirm no connection remains locked after each test.

### Checkpoint 1

Required evidence:

- Database characterization suite passes repeatedly.
- Current transaction inconsistencies are documented as existing behavior, not silently corrected.
- Commit suggestion: `test: characterize catalog persistence`

Do not begin Phase 2 until Checkpoint 1 is committed.

---

## Phase 2 — Characterize Excel and dictionary behavior

### Purpose

Protect tolerant workbook parsing and description rules before extracting services.

### Implementation and tests

Generate workbook fixtures covering:

- Headers on different rows.
- Alternate recognized code and description header names.
- Multiple sheets.
- Empty sheets and sheets without a usable code column.
- Codes containing whitespace and Unicode dash variants.
- Exact matches, unique normalized matches, and ambiguous normalized matches.
- English-only, Vietnamese-only, and bilingual descriptions.
- Duplicate codes across sheets.
- Embedded images anchored on, above, and below code rows.
- Repeated image content.
- Missing or unreadable embedded images where reproducible.

Add dictionary tests covering:

- UTF-8 CSV parsing.
- Missing dictionary file.
- Empty descriptions receiving values.
- Existing non-empty descriptions never being overwritten.

### Validation

- Assert exact mappings, selected header rows, selected code columns, and skipped rows.
- Assert image hashes, generated filenames, provenance, and link order where the active workflow applies them.
- Reopen generated workbooks with openpyxl.

### Checkpoint 2

Required evidence:

- Excel and dictionary characterization tests pass.
- Fixture assumptions and expected mappings are documented.
- Commit suggestion: `test: characterize Excel catalog workflows`

Do not begin Phase 3 until Checkpoint 2 is committed.

---

## Phase 3 — Characterize PDF and image behavior

### Purpose

Protect layout-sensitive extraction, page conversion, and image assignment.

### Implementation and tests

Add generated PDF tests for:

- Zero-based PyMuPDF index to one-based database page conversion.
- Item code, category, author, dimension, and description extraction.
- Single- and multi-column layouts that can be represented reliably.
- Pages with no products.
- Pages with codes but no usable images.
- Nearest-image selection.
- JPEG/PNG conversion and image hashing.
- Validated-item skip behavior.
- Excel-image skip behavior.
- Existing-item update and skip callbacks.
- No-image replacement when an item already has linked images.
- PDF document closure after success and failure.

Where generated PDFs cannot represent real catalog layouts, add only explicitly approved sanitized representative fixtures.

### Validation

- Compare extracted objects field by field.
- Compare resulting database rows, asset hashes, source values, match methods, and link order.
- Run repeated imports and assert idempotent behavior where currently expected.

### Checkpoint 3

Required evidence:

- PDF characterization suite passes.
- Any catalog layouts not represented by fixtures are listed as manual-only risks.
- Commit suggestion: `test: characterize PDF extraction and image linking`

Do not begin Phase 4 until Checkpoint 3 is committed.

---

## Phase 4 — Characterize export and UI workflows

### Purpose

Lock down workbook post-processing and the highest-risk user workflows.

### Implementation and tests

Add export tests for:

- Product-code and quantity input.
- Exact and normalized DB matching.
- Missing-code reporting.
- VI/EN description selection and fallback.
- Missing-description highlighting.
- Missing-image reporting.
- Image order and optional rotation behavior.
- Output sheet replacement and naming.
- Cell values, merges, row heights, column widths, and images.
- Branding image injection.
- XLSX content types, relationships, VML, and header/footer XML.
- Reopening the final workbook with openpyxl.

Create a manual UI checklist covering:

- Startup and restart.
- List filtering, sorting, column movement, and visibility.
- Item selection and unsaved-change prompts.
- Add, edit, save, validate, and delete.
- Manual image add/remove/rotate/reorder.
- PDF candidate assignment and cropping.
- PDF import decisions.
- Excel database update decisions.
- Export preflight editing and cancellation.
- Backup.

### Validation

- Compare workbook semantics rather than raw ZIP byte order or timestamps.
- Open at least one representative exported workbook in desktop Excel.
- Record screenshots or a signed checklist for manual validation.

### Checkpoint 4

Required evidence:

- Export characterization tests pass.
- Manual baseline checklist is completed or limitations are recorded.
- Commit suggestion: `test: characterize export and UI behavior`

Do not begin production refactoring until Checkpoint 4 is committed.

---

## Phase 5 — Extract pure shared utilities

### Purpose

Remove safe duplication without moving stateful workflows.

### Implementation

Introduce focused modules for tested pure behavior, such as:

```text
src/smartcatalog/
├── domain/models.py
└── utils/
    ├── code_normalization.py
    ├── filename_utils.py
    ├── image_utils.py
    └── ui_dispatch.py
```

Extract only utilities whose equivalence is proven:

- Code and header normalization.
- Unique normalized-code index building.
- Filename sanitization.
- Image-anchor lookup and content hashing.
- UI-thread dispatch.

Keep compatibility imports or wrappers at old locations. If similar helpers differ, preserve separate named policies instead of forcing them together.

Do not consolidate active code with legacy modules in this phase.

### Validation

- Run the full suite.
- Add direct tests for every extracted helper.
- Compare old-wrapper and new-function results over representative and edge-case inputs.
- Run the complete Phase 4 UI checklist sections affected by imports or callbacks.

### Checkpoint 5

Required evidence:

- No observable behavior change.
- Old imports still work.
- Duplicate code is removed only where equivalence is proven.
- Commit suggestion: `refactor: extract shared pure utilities`

Do not begin Phase 6 until Checkpoint 5 is committed.

---

## Phase 6 — Split database internals behind `CatalogDB`

### Purpose

Make persistence maintainable without changing its public interface.

### Implementation

Split internal responsibilities:

```text
src/smartcatalog/db/
├── catalog_db.py
├── schema.py
├── path_mapper.py
├── item_repository.py
└── asset_repository.py
```

- Keep `CatalogDB` as the compatibility facade used by all current callers.
- Move schema and compatibility migration definitions.
- Move path conversion policy.
- Move item row mapping and item operations.
- Move asset and link operations.
- Preserve SQL, ordering, commit behavior, exceptions, defaults, and returned types.
- Do not redesign transactions in this phase.

### Validation

- Run all database characterization tests against baseline and refactored commits.
- Compare fresh and upgraded schemas.
- Compare normalized DB dumps after identical operation sequences.
- Verify asset/link IDs and ordering.
- Run affected item/image manual checks.

### Checkpoint 6

Required evidence:

- `CatalogDB` public calls remain compatible.
- Database outputs match the baseline.
- No migration is triggered beyond existing behavior.
- Commit suggestion: `refactor: separate catalog persistence internals`

Do not begin Phase 7 until Checkpoint 6 is committed.

---

## Phase 7 — Extract the Excel database-import service

### Purpose

Remove Excel import, embedded-image extraction, and DB-update logic from `MainWindow`.

### Implementation

Create focused services, for example:

```text
src/smartcatalog/services/
├── excel_catalog_import.py
└── workbook_images.py
```

- Accept explicit paths, DB/state dependencies, progress callback, and overwrite-decision callback.
- Return a typed result object containing counts, updated codes, missing codes, and warnings.
- Keep file dialogs, Tk variables, message boxes, and item refresh in the UI.
- Preserve multi-sheet order, first-occurrence rules, image hashes, filenames, provenance, and overwrite decisions.
- Retain `MainWindow.on_build_excel_db()` as a thin UI adapter.

### Validation

- Run all Excel, DB, asset, and threading tests.
- Compare baseline and refactored DB dumps and asset hashes from identical fixtures.
- Manually test cancel, update one, skip one, apply-to-all, and import completion.

### Checkpoint 7

Required evidence:

- `MainWindow` no longer contains workbook parsing or DB import mechanics.
- Results match baseline fixtures.
- UI decisions execute on the Tk thread.
- Commit suggestion: `refactor: extract Excel catalog import service`

Do not begin Phase 8 until Checkpoint 7 is committed.

---

## Phase 8 — Extract the Excel export service

### Purpose

Separate product matching, preflight preparation, and workbook generation from the UI.

### Implementation

Create:

```text
src/smartcatalog/services/
├── catalog_export.py
├── export_preflight.py
└── workbook_product_reader.py
```

- Separate reading, matching, issue collection, row preparation, workbook writing, branding, and result reporting.
- Keep the interactive review dialog in the UI layer.
- Pass edited descriptions back to the service through explicit data objects.
- Return a typed export result.
- Keep `on_search_images_from_excel()` as a compatibility adapter initially; rename it only in Phase 13.
- Preserve the current selected-workbook mutation behavior unless a separately approved behavior change alters it.

### Validation

- Run all export and workbook-package tests.
- Compare semantic workbook snapshots against the baseline.
- Reopen output with openpyxl.
- Open a representative output in desktop Excel and verify images, branding, relationships, print settings, and layout.
- Manually test review cancellation and incomplete export confirmation.

### Checkpoint 8

Required evidence:

- Export orchestration is independent of Tkinter.
- Workbook semantics match the baseline.
- Desktop Excel validation passes.
- Commit suggestion: `refactor: extract catalog export service`

Do not begin Phase 9 until Checkpoint 8 is committed.

---

## Phase 9 — Extract the PDF import service

### Purpose

Separate parsing, update policy, persistence, and UI reporting.

### Implementation

Create a clear pipeline:

```text
PDF page
-> extracted item candidates
-> existing-item policy
-> item persistence
-> nearest-image extraction
-> asset persistence and linking
```

Suggested modules:

```text
src/smartcatalog/services/pdf_import.py
src/smartcatalog/loader/pdf_item_extractor.py
src/smartcatalog/loader/pdf_image_extractor.py
```

- Keep UI prompts behind an injected callback.
- Keep status reporting behind a callback/data event.
- Preserve page numbering, skip rules, hashes, paths, provenance, match methods, ordering, and commit boundaries.
- Keep the current public loader function as a compatibility wrapper.
- Do not tune extraction geometry or regexes.

### Validation

- Run PDF, DB, image, and threading tests.
- Compare extracted items and database/asset outputs to baseline.
- Manually test new PDF selection, current PDF reuse, update, skip, apply-to-all, and cancellation.

### Checkpoint 9

Required evidence:

- PDF parsing and persistence are callable without Tkinter.
- Current extraction outputs match baseline fixtures.
- Manual import decisions behave identically.
- Commit suggestion: `refactor: extract PDF import service`

Do not begin Phase 10 until Checkpoint 9 is committed.

---

## Phase 10 — Extract backup and reduce `MainWindow`

### Purpose

Make the UI a composition and coordination layer.

### Implementation

- Create `services/backup_service.py` with explicit source/destination paths and a typed result manifest.
- Split large UI layout sections into focused panels or controllers.
- Move workflow coordination into small UI adapters:
  - PDF import workflow.
  - Excel import workflow.
  - Export workflow.
  - Backup workflow.
- Preserve existing widget attributes and command bindings until dependents are migrated.
- Keep strong `PhotoImage` references.
- Do not adopt a new UI framework or perform a full MVC rewrite.

Target responsibility for `MainWindow`:

- construct application-level variables;
- compose panels;
- construct services;
- wire top-level events;
- manage application lifecycle.

### Validation

- Run the full automated suite.
- Complete the entire manual UI checklist.
- Verify background operations do not directly touch Tkinter.
- Verify close/restart behavior and image rendering.

### Checkpoint 10

Required evidence:

- All former workflows remain accessible.
- `MainWindow` is materially smaller and contains no parsing, SQL, or workbook-writing logic.
- Full manual UI regression passes.
- Commit suggestion: `refactor: reduce main window to UI coordination`

Do not begin Phase 11 until Checkpoint 10 is committed.

---

## Phase 11 — Improve error and resource handling

### Purpose

Make failures actionable and resources deterministic after structural seams are stable.

### Implementation

- Inventory every broad exception handler.
- Classify each as:
  - intentional best effort;
  - user-recoverable error;
  - programming/unexpected error.
- Replace broad catches with specific exceptions where behavior is understood.
- Add operation and path context to reported failures.
- Close SQLite, PyMuPDF, PIL, workbook, and temporary-file resources deterministically.
- Ensure worker errors reach the established UI error path.
- Protect delayed callbacks from destroyed widgets/windows.

Because this phase can alter visible error behavior, review each change separately and add a failure-path test first.

### Validation

- Run full success-path and failure-path tests.
- Test missing, unreadable, malformed, and locked files with disposable fixtures.
- Verify no file or DB locks remain after failures.
- Run relevant manual error scenarios.

### Checkpoint 11

Required evidence:

- Every changed exception path has a test.
- User messages remain actionable and do not expose unnecessary internals.
- No resource leaks or locked fixtures remain.
- Commit suggestion: `refactor: make failures and resources explicit`

Do not begin Phase 12 until Checkpoint 11 is committed.

---

## Phase 12 — Resolve legacy code and dependencies

### Purpose

Remove ambiguity caused by unwired implementations.

### Implementation

For each legacy module, document and choose one action: remove, archive, migrate a required capability, or keep temporarily under a clearly labeled legacy boundary.

Review:

- `db/update_db_from_pdf.py`
- `extracter/extract_key_info_from_pdf.py`
- `matcher/pdf_matcher.py`
- `ui/controllers/pdf_viewer_controller.py`
- `utils/pdf_exporter.py`
- `config/settings.py`

Search all tracked source, build configuration, documentation, and scripts before removal.

After code decisions, map every requirement to an active import or documented external need. Remove a dependency only when source execution, tests, documentation workflows, and the frozen build prove it is unnecessary.

### Validation

- Run full tests and imports.
- Build the executable.
- Exercise every active workflow.
- Confirm PyInstaller contains required dynamic/native packages.
- Confirm no script or documented command relies on removed code.

### Checkpoint 12

Required evidence:

- Every legacy module has a recorded disposition.
- Removed dependencies are proven unused.
- Source and frozen applications pass smoke tests.
- Commit suggestion: `chore: resolve legacy modules and dependencies`

Do not begin Phase 13 until Checkpoint 12 is committed.

---

## Phase 13 — Verified naming and encoding cleanup

### Purpose

Improve readability without mixing uncertain text repair into structural work.

### Implementation

- Rename misleading methods and variables with temporary compatibility wrappers.
- Remove obsolete compatibility wrappers only after all callers and tests migrate.
- Remove harmless placeholder expressions after verification.
- Correct Vietnamese strings only when the intended text is verified by documentation, UI context, or an approved native-language review.
- Keep all edited files UTF-8.
- Do not perform global search/replace or whole-file encoding conversion.

### Validation

- Test old compatibility entry points while they remain supported.
- Compile and import every changed module.
- Complete the full UI text and workflow checklist.
- Obtain native-language review for corrected Vietnamese text where possible.

### Checkpoint 13

Required evidence:

- Naming reflects actual responsibilities.
- No speculative encoding changes are present.
- UI text has been manually reviewed.
- Commit suggestion: `refactor: clarify names and verified UI text`

Do not begin Phase 14 until Checkpoint 13 is committed.

---

## Phase 14 — Full regression and frozen release validation

### Purpose

Prove the completed refactor preserves the supported application.

### Implementation

- Run the entire automated suite from a clean checkout/environment.
- Run all workflows with disposable representative data.
- Build through `build_exe.ps1`.
- Test the complete `dist/SmartCatalog/` folder in a normal writable location.
- Verify first-launch directory creation.
- Verify restart and persisted PDF selection.
- Verify PDF import, Excel import, image workflows, backup, export, and workbook reopening.
- Compare representative final DB and workbook results with the pre-refactor baseline.
- Update architecture and contributor documentation to match final code.

### Final checkpoint

Required evidence:

- All phase checkpoints are present.
- Automated suite passes cleanly.
- Full manual checklist passes.
- Frozen build passes.
- No unexplained baseline difference remains.
- Known limitations and deferred behavior changes are documented.
- Commit suggestion: `docs: finalize refactored architecture`

The refactor is complete only after this final checkpoint is committed.

## Handling discovered bugs

If a likely bug is discovered during refactoring:

1. Add a characterization test that demonstrates current behavior.
2. Do not fix it inside the structural refactor.
3. Record it in a separate bug backlog with severity and user impact.
4. Complete or revert the current structural phase.
5. Fix the bug in a separate, explicitly approved change with its own tests and checkpoint.

Exceptions are limited to data-loss, security, or unrecoverable corruption risks. Those require stopping the refactor and obtaining explicit direction before proceeding.

## Rollback policy

- Each phase must be independently revertible.
- Do not squash phase checkpoints until final acceptance.
- Never use destructive Git commands against unrelated user work.
- If a phase cannot pass its gate, revert only that phase to the last validated checkpoint.
- Preserve failing fixtures and diagnostic evidence when they expose a real regression.

## Definition of done

The project is considered successfully refactored when:

- Active responsibilities are separated into clear UI, service, loader, domain, and persistence layers.
- `MainWindow` coordinates UI instead of implementing business workflows.
- `CatalogDB` remains compatible while its internals are focused and testable.
- PDF, Excel, image, database, and export behavior is covered by characterization tests.
- Every phase has a validated Git checkpoint.
- Source and frozen applications pass full regression testing.
- No live runtime/user data was used or modified during development.
- Any intentional behavior change is documented and delivered separately.
