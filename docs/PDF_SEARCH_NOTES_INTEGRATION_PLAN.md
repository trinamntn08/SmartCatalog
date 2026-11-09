# PDF Search and Notes Integration Plan

Status: planned; no application implementation has started.

Prepared: 2026-11-09.

Target branch: `feature/pdf-search-notes-integration`, created from `master`.

## 1. Objective and agreed direction

Integrate the PDF Keyword Search with Notes application into SmartCatalog as a
native tool using the existing Tkinter application, dependencies, packaging,
and architecture. Users should search many keywords or product codes, review
matching pages, and save a highlighted PDF and an Excel page report from one
application.

The main catalog workspace remains the product list and product editor. Add a
Vietnamese toolbar action, **Tìm & ghi chú PDF**, opening a resizable search
workspace owned by the existing Tk root. Do not start another Tk root, run a
second application, or depend on an installed copy of the old tool.

This document specifies future behavior. Its checkboxes are implementation
work, not claims that the feature or its validation is complete.

## 2. Investigation evidence and constraints

The source application reviewed was
`D:/dev/code_catalog_old/findCatalogWithNotes/main.py`, together with its
README, user guide, and code review. That path identifies the investigation
source only; production code must never depend on this developer path.

Relevant active SmartCatalog files:

| File | Integration relevance |
| --- | --- |
| `src/smartcatalog/ui/main_window.py` | Toolbar, catalog selection, editor state, busy state and window composition |
| `src/smartcatalog/ui/pdf_crop_window.py` | Whole-document PDF navigation, search, zoom, visible-page rendering and crop interaction |
| `src/smartcatalog/ui/controllers/workflows_controller.py` | Existing workflow and background/UI dispatch patterns |
| `src/smartcatalog/state.py` | Current catalog PDF, configured data paths and runtime state |
| `src/smartcatalog/domain/models.py` | Product model with one source page per item |
| `src/smartcatalog/services/workbook_product_reader.py` | Existing code/quantity workbook reader; not a keyword/note reader |
| `src/smartcatalog/db/schema.py` | Items, assets and links; no search-history model |
| `tests/test_pdf_crop_search.py` | Existing PDF search and layout regression coverage |
| `requirements.in`, `SmartCatalog.spec` | Existing PyMuPDF/openpyxl dependencies and frozen packaging |

Both applications use Tkinter, PyMuPDF and openpyxl. SmartCatalog targets
Python 3.13 and pinned libraries; compatibility of adapted behavior must be
verified there. No additional core dependency is currently expected. The old
PyPDF2 import and runtime package-install fallback are unnecessary.

Follow root and scoped `AGENTS.md` files before implementation. In particular:

- Do not inspect, import, or revive anything under `to_integrate/`.
- Do not use the live catalog or runtime files as test fixtures.
- Keep services independent of Tkinter and persistence behind `CatalogDB`.
- Preserve imports, exports, validation protections, dirty-state handling,
  image order, provenance, Unicode and source/frozen operation.
- Do not revive removed legacy PDF viewers or exporters. Annotated source PDF
  output is a new workflow, separate from formatted catalog Excel export.

An unrelated untracked workbook, `KQ xuất.xlsx`, existed before this branch.
Leave it untouched and exclude it from feature commits.

## 3. Scope and delivery order

### Initial delivery: Excel-driven tool

- Choose the current catalog PDF or another searchable PDF.
- Select an `.xlsx` workbook, worksheet, header/data start row and columns.
- Default to the legacy layout: A keyword, B matching pages, C optional note,
  with data starting on row 2. Allow the note column to be omitted.
- Search in a worker, show progress and support cancellation.
- Review found/missing rows and individual occurrences in a PDF preview.
- Configure highlights and visible notes, then export independent outputs.
- Produce a highlighted PDF and a safe Excel results copy or standalone report.

### Follow-on delivery on this feature branch: catalog selection

- Launch with selected product codes as the keyword source.
- Provide explicit selected/filtered/all scope where supported by the current
  table selection model. Inspect that model before introducing multi-selection.
- Offer descriptions as notes only through an explicit language/source choice;
  default catalog notes to blank.
- Keep product codes, descriptions, images, validation and source pages intact.

### Deferred scope

OCR; fuzzy matching; multi-PDF batch jobs; permanent search history; automatic
source-page replacement; automatic product creation; database note storage;
popup PDF comments; rich-text notes; arbitrary legacy Excel formats.

No database migration is needed for either planned delivery. Persistent
history, if requested later, needs its own schema and portability design.

## 4. Proposed UI and manipulation

```text
SmartCatalog toolbar: [...existing actions...] [Tìm & ghi chú PDF]

PDF Search & Notes
--------------------------------------------------------------------
PDF:      [Current catalog.pdf                         ] [Browse]
Source:   [Excel workbook / Catalog products]
Workbook: [Path                                        ] [Browse]
Sheet:    [...]  Header/data row: [...]  Keyword: [A]  Note: [C]
[Search] [Cancel]                               [Note options v]
-------------------------------+------------------------------------
Keyword      Pages      Status | PDF preview
ABC-123      12, 38      Found  | [Previous hit] [Next hit] [Zoom]
DEF-456      --          Missing| Selected occurrence highlighted
-------------------------------+------------------------------------
Progress / counts / warnings
[Save highlighted PDF] [Save Excel results] [Open output folder]
```

The wireframe is conceptual. Use Vietnamese labels consistent with the app,
keyboard navigation, resizable panes and scrollable results. Keep advanced
formatting collapsed initially to avoid crowding the product editor.

### Main workflow

1. Open or focus the single existing search window.
2. Default its PDF selector to `state.catalog_pdf_path`, if available.
3. Browsing a different PDF changes only the tool's session input; it must not
   call the catalog import or change the persisted active catalog PDF.
4. Select a source and inspect a small read-only row preview before searching.
5. Snapshot paths, rows and options on the UI thread, validate, then run.
6. Display row status, sorted unique 1-based pages and occurrence counts.
7. Selecting a row navigates to its first hit; next/previous moves through its
   occurrences. Missing rows remain visible and can be filtered.
8. Choose output paths and export either or both outputs. Report each result
   independently and allow retrying a failed export.

### Formatting and preview

Preserve the old defaults where practical: top-right notes, X/Y offsets of
5 PDF points, black text, 8-point font, and teal highlights. Offer four note
positions, supported colors and validated font size/offset fields. State that
offsets are PDF points, not preview pixels.

Notes are visible text near matches, not popup comments. A blank note means
highlight only. Preview must show selected hit bounds and provide a way to
inspect the final annotation placement before delivery. Changing only note
formatting should not rescan the document text.

### State and responsiveness

Use explicit idle, searching, ready, exporting, cancelled and failed states.
Prevent concurrent jobs in the tool. Disable input changes while their job is
running; keep cancel and window repaint available. Coordinate with the main
busy state for catalog-source snapshots and existing long workflows. Do not
change the catalog database while deriving product rows.

Workers own their PDF/workbook resources. All Tk widgets, variables, dialogs,
and `ImageTk` objects stay on the UI thread. Dispatch completion/progress via
the established UI mechanism; ignore stale job completions after close or a
new run. Closing during work signals cancellation and safely releases worker
resources without calling destroyed widgets.

Opening this read-only tool should not discard an unsaved product edit. A
catalog source uses saved values and states this clearly; any action that
changes product selection must retain existing dirty-state prompts.

## 5. Search and row semantics

- Maintain an input row identifier (worksheet and physical row, or product ID),
  original keyword spelling and note. Preserve duplicate rows independently.
- Trim keywords for searching; skip blank rows with a visible summary.
- Preserve literal product codes, leading zeros and punctuation. Warn when a
  numeric Excel cell has already lost meaningful formatting or precision.
- Define formula-cell handling explicitly: use available cached values and
  warn on unavailable results; never calculate formulas in this feature.
- Convert numeric/boolean notes to documented display strings; handle empty
  cells consistently. Validate unsupported/error values before export.
- Provide case-insensitive literal matching for legacy keyword use and a
  whole-code mode for catalog codes. Do not interpret user text as regex.
- Define whole-code boundaries around letters, digits and code punctuation,
  with examples such as `ABC-12` versus `ABC-123` and `XABC-12`.
- Specify whitespace, line-break and hyphenation handling through fixtures.
  Use one accepted-hit model for page results, counts, preview and export;
  never count text-substring matches separately from highlightable matches.
- Reuse PyMuPDF text/geometry capabilities and verify mappings for rotated
  pages, wrapped phrases and repeated occurrences. Unsupported cases must be
  reported rather than silently producing contradictory results.
- Internal PDF indexes are 0-based; UI/report page numbers are 1-based.
- A keyword can have many page hits. Never write a comma-separated page list
  into `CatalogItem.page`, which represents one source page.
- Search extracted text only. Detect textless documents and warn about OCR;
  distinguish that condition from a successful search with no matching rows.

Search once per unique keyword/mode where safe, then map hits back to original
rows. Export one highlight per physical occurrence; retain distinct duplicate
notes and show all non-empty notes in input order in a combined note block at
that occurrence. Warn if that block cannot fit. Identical duplicate note text
can be displayed once if the results retain every original input row.

## 6. Proposed architecture and contracts

Names below are proposed; confirm them against scoped guidance at each step.

| Proposed module | Responsibility |
| --- | --- |
| `domain/pdf_search.py` | Immutable input rows, options, hits, row results and job/export results |
| `loader/keyword_workbook.py` | Sheet inspection and configured keyword/note reading with row provenance |
| `services/pdf_keyword_search.py` | UI-free search, accepted occurrence geometry, progress and cancellation |
| `services/pdf_annotation_export.py` | Highlight/note placement and safe annotated-PDF writing |
| `services/keyword_results_export.py` | Workbook copy or standalone results workbook |
| `ui/controllers/pdf_search_controller.py` | Input snapshots, lifecycle, dialogs, dispatch and export coordination |
| `ui/pdf_search_window.py` | Tool composition, options, results and controls |
| `ui/widgets/pdf_document_view.py` | Shared navigation/rendering component extracted only as necessary |

Minimum result information: source row identity, keyword, note, per-occurrence
page index and geometry, unique pages, warnings and terminal status. Export
results carry actual output paths and per-output success/failure. Cancellation
is a distinct outcome, not success or a generic failure.

Refactor the active crop viewer incrementally. Keep a compatibility adapter
for `search_pdf_pages()` and its existing tests if implementation moves into
a service. Extract navigation/rendering separately from product-specific crop
saving. The search viewer must work without an item ID or selected product;
only crop actions should require those. Existing crop shortcuts, image links,
page navigation and strong image references must continue working.

Do not turn the existing code/quantity workbook reader into a generic mutating
reader. Reuse header normalization helpers where suitable, while keeping
keyword/note parsing and report writing explicit.

## 7. File safety, notes and error behavior

### Source and output protection

- Never save over the input PDF or selected workbook in the initial delivery.
- Default to sibling names such as `name_highlighted.pdf` and
  `name_search_results.xlsx`, derived with `pathlib`, including uppercase PDF
  extensions. Resolve and compare paths to reject source/output collisions.
- Let the user choose another destination. Require overwrite confirmation for
  existing output files and detect collisions between the two outputs.
- Write to temporary sibling files, close and validate them, then publish each
  completed file. Clean temporary outputs after failure or cancellation.
- Two output files are not a single atomic transaction. Report partial success
  truthfully and retain a successfully published output when the other fails.
- Verify the source has not changed since search (document identity including
  size/time and stronger validation if needed). Require a rerun on changes.
- Handle locked files, unwritable folders, damaged/encrypted PDFs, missing
  paths and unavailable cached formula values with actionable messages.
- Do not copy arbitrary external search PDFs into managed catalog storage.

### Workbook output modes

1. **Results copy:** write pages only to the explicitly mapped results column
   in the selected worksheet of a new copy. Preserve row order and formulas
   elsewhere; warn if this column already contains values.
2. **Standalone report:** include source row, keyword, note, pages, occurrence
   count, status and warnings. Use this for catalog-source searches too.

Openpyxl cannot guarantee fidelity for every advanced Excel object. Verify
supported representative copies in desktop Excel; offer the standalone report
when fidelity is uncertain. Do not promise lossless copying of arbitrary
workbooks, embedded objects or unsupported features. Preserve original files
in all cases. Write external keyword/note text as literal cells, not formulas.

### Note placement

Use Unicode-capable font handling and verify Vietnamese glyphs in preview,
export and frozen mode. If a distributable font is necessary, check its
license, add it as an intentional packaged asset and resolve it in both modes.

Measure note layout, check text insertion results, clamp bounds on every page
edge and account for rotation. Expand/reflow within defined limits; report
unplaceable notes rather than silently dropping or clipping text. Decide and
test deterministic collision handling for nearby notes. Final summary includes
unplaced/overflow notes and links them to result rows/pages.

## 8. Ordered implementation steps and gates

### Step 0 — Baseline and fixtures

- [ ] Read applicable scoped guidance; record worktree state and base commit.
- [ ] Run the existing canonical checks before modifying application code.
- [ ] Generate disposable PDFs/workbooks covering ordinary, duplicate,
  missing, multiline and Vietnamese cases; use no live runtime data.
- [ ] Record existing crop/search behavior and relevant manual checks.

Gate: baseline results recorded, unrelated work preserved, fixtures disposable.

### Step 1 — Domain and workbook inputs

- [ ] Introduce typed contracts and cancellation/progress interfaces.
- [ ] Implement worksheet/column selection, row identity and input validation.
- [ ] Test duplicates, blank rows, notes, formulas, leading zeros and errors.

Gate: inputs can be read without Tkinter or database writes; every row remains
traceable to its source.

### Step 2 — Search service

- [ ] Implement literal and whole-code matching with occurrence geometry.
- [ ] Unify result pages, counts and highlight geometry.
- [ ] Add cancellation checkpoints between pages/keyword batches.
- [ ] Preserve the active viewer search contract via a small adapter if moved.
- [ ] Test punctuation, partial codes, Unicode, multiline text, repeated hits,
  rotated pages, empty/textless documents and cleanup on exceptions.

Gate: deterministic accepted hits, correct page numbering, no UI dependency.

### Step 3 — Safe output services

- [ ] Implement staged PDF writing and validated highlight/note placement.
- [ ] Implement results-copy and standalone workbook output.
- [ ] Add independent export results and accurate partial-failure reporting.
- [ ] Test filename cases, collisions, locked/unwritable paths, note overflow,
  source mutation, cancellation and unchanged input-file hashes.
- [ ] Visually inspect generated PDFs and representative Excel copies.

Gate: no source overwrites; every missing note or failed output is reported.

### Step 4 — Shared PDF viewer component

- [ ] Separate document navigation/rendering from item-specific crop saving.
- [ ] Support selected-hit overlays and occurrence navigation.
- [ ] Keep worker documents separate from the preview document.
- [ ] Verify zoom/scroll coordinate mapping, rendering cache cleanup and close.
- [ ] Re-run crop search/layout tests and manually check crop/save/link behavior.

Gate: existing crop workflow remains intact; preview works without a product.

### Step 5 — Excel-driven UI integration

- [ ] Add the toolbar action, single tool window and Vietnamese labels.
- [ ] Wire input preview, advanced options, row filters and hit navigation.
- [ ] Add progress, cancel, stale-job guards and independent export controls.
- [ ] Handle window closure and concurrent main-app work safely.
- [ ] Exercise the full Excel-to-search-to-review-to-export workflow.

Gate: initial delivery is usable entirely within SmartCatalog and reports
success, cancellation, warnings and partial failure accurately.

### Step 6 — Catalog product source

- [ ] Inspect existing selection/filter APIs and define explicit source scope.
- [ ] Add product-code snapshots and optional VI/EN description notes.
- [ ] Default to whole-code matching; expose an explicit literal alternative.
- [ ] Handle empty selection, missing PDF, saved-versus-unsaved values and
  database switching while the tool exists.
- [ ] Export a standalone report without mutating catalog records.

Gate: selected/filtered/all scopes match their labels; source product records
and the active catalog PDF remain unchanged.

### Step 7 — Regression, packaging and documentation

- [ ] Run `.\tools\check.ps1` and focused new workflow checks.
- [ ] Manually smoke-test affected existing catalog workflows on disposable
  data: selection/edit/save, dirty prompts, import/export, crop/images,
  validation, database switch, backup and restart as relevant.
- [ ] Build with the supported `build_exe.ps1` workflow in a safe build area;
  remember it recreates `dist/` and must not contain user files.
- [ ] Smoke-test the complete frozen folder on a disposable installation,
  including Vietnamese notes and output opening.
- [ ] Update user guide, architecture and documentation index for actual
  delivered behavior. Record limitations and all unperformed checks.

Gate: source and frozen flows pass; no runtime/user files enter the patch.

## 9. Acceptance criteria

- [ ] One SmartCatalog process and one Tk root provide the entire workflow.
- [ ] Existing Excel A/B/C input works through defaults without preprocessing.
- [ ] Users can inspect found and missing rows and navigate every accepted hit.
- [ ] Duplicate input rows keep their notes and source-row identity.
- [ ] Exported pages/counts agree with preview and PDF highlight locations.
- [ ] Whole-code mode avoids the documented partial-code false positives.
- [ ] Notes render Vietnamese correctly; overflow/collision failures are visible.
- [ ] Neither source file nor catalog records are modified by search/export.
- [ ] Input hashes and disposable DB snapshots substantiate that protection.
- [ ] Cancellation leaves no misleading completed files or success message.
- [ ] A failed output does not hide a successful output or block its retry.
- [ ] Original crop, catalog import/edit/export and validation behavior passes
  the relevant regression and manual checks.
- [ ] The frozen distribution runs without the old application or developer
  filesystem paths.

## 10. Checkpoints, review and rollback

Use small reviewable commits in dependency order: contracts/inputs, search,
outputs, viewer extraction, Excel UI, catalog source, release/docs. Keep viewer
refactoring separate from new feature behavior so regressions are attributable.
Each implementation checkpoint records commands, results, manual evidence and
remaining limitations; unchecked work must remain described as planned.

Before final review, inspect the diff and status, check whitespace and links,
and confirm that only intended source, tests, build assets and documentation
changed. Do not stage unrelated workbooks or generated/runtime directories.

Rollback is a code/packaging rollback because the planned feature introduces
no schema changes and writes only user-selected output copies. Preserve user
outputs and the complete existing `config/database/` directory during upgrades
or rollback. Never reset the database to disable the tool.

## 11. Planning-stage validation

This planning change creates a branch and documentation only. No application
code, settings, catalog database, imported files or build outputs are changed.
Application tests, GUI smoke tests and frozen builds are implementation gates;
they have not been run as evidence for this plan. The implementation phases
must record their own actual results.
