# Startup and responsiveness review

Reviewed on 2026-11-09 after a report of slow launch. The review covered the
active startup, state/settings, database/path mapping, product list, image
panels, PDF import/crop, Excel import/export, backup, and executable packaging
paths. User data and the unrelated workbook in the worktree were not inspected.

This records the investigation and fixes at Git revision `f1ffdd0`. For the
current packaging and delivery process, use [BUILD_EXE.md](../BUILD_EXE.md).

## Confirmed causes and changes

1. **The initial catalog was loaded twice.** `MainWindow.__init__` queued a
   refresh, while `start_ui` performed another refresh before dismissing the
   splash. Startup now owns the initial refresh. A Windows smoke test with a
   generated 10,000-product catalog observed exactly one database read.
2. **Repeated paths caused repeated Windows filesystem calls.** `list_items`
   resolved each item's PDF and image paths through `Path.resolve()`. Thousands
   of products commonly share one PDF. A profile attributed most catalog-read
   time to Windows path resolution. The method now resolves each distinct path
   once per invocation. The cache expires when the read finishes; portability,
   missing-file behavior, special tokens, image order, and fresh filesystem
   resolution on later reads are retained.
3. **Heavy imports preceded the splash.** Importing the entry module pulled in
   the UI, pandas/openpyxl, Pillow, and PyMuPDF before Tk showed anything.
   Loading the main window now happens during splash boot. This brings visual
   feedback forward; it defers dependency loading rather than eliminating it.
4. **Every search key rebuilt the table and normalized all product text.**
   Search now waits 180 ms after the latest key release, reuses bounded
   normalization/date-format caches, skips product-text normalization for an
   empty search, and removes old rows in a single Tk call. Cache keys include
   the text itself, so edited/replaced products cannot reuse obsolete text.
5. **Selection repeated image work.** Product selection requested page images
   both directly and through form reload. The form now makes the sole request.
   Thumbnail selection updates existing borders and the preview instead of
   rebuilding the grid and decoding all its source images again.

These changes do not alter the schema, matching rules, import protections,
transaction boundaries, or saved catalog format.

## Measurements

Windows, Python 3.13.14, local generated SQLite catalog, 10,000 products with
Vietnamese descriptions and validation timestamps. Products share one relative
PDF path pointing to a deliberately absent fixture file. Tk uses a real hidden
Treeview. These figures measure individual operations, not end-to-end EXE
launch, cold disk startup, or the reporting user's machine.

The original database/list-controller functions were loaded in memory from
Git revision `36bc7e3` and run with the same generated fixture and benchmark.
The entry-import comparison used a separate Python process. Single-run times
are indicative; machine load and disk caches affect results.

| Operation | Before | After |
| --- | ---: | ---: |
| Entry-module import, before splash | 0.722 s | 0.079 s |
| Catalog read, one invocation | 2.681 s | 0.105 s |
| Initial table construction | 0.619 s | 0.111 s |
| First populated search | 0.724 s | 0.490 s |
| Repeated populated search | 0.654 s | 0.164 s |
| Search with no matches | 0.318 s | 0.041 s |

Search timings exclude the intentional 180 ms typing delay. Search caches hold
at most 16,384 text entries and 2,048 timestamp entries. Larger working sets
can evict entries, reducing cache benefits without changing search results.

Repeat the current benchmark from the repository root:

```powershell
.\.venv-agent\Scripts\python.exe tests/benchmark_performance.py --items 10000
```

The benchmark creates and removes its own temporary database and never opens
the configured catalog. It requires an available Tk desktop. For comparisons,
run the same fixture on each revision with the same interpreter and machine;
do not put timing thresholds into the normal regression suite.

## Further improvements and review findings

| Priority | Finding | Recommended next step |
| --- | --- | --- |
| Next for very large catalogs | Startup still reads every item and image reference and inserts every table row on the UI thread. Unique image paths still require individual resolution. | Measure a backed-up representative catalog, then consider lightweight list records, background reads, and paginated or incremental table rendering. Preserve selection, unsaved prompts, and worker/database-switch ordering. |
| Next for long sessions | Page-image candidates retain full extracted bytes for every visited page without an eviction budget. The cached PDF also remains open after the main window closes until process teardown; this caused a disposable smoke fixture's immediate cleanup to fail. | Add a byte-budgeted cache and explicit document/worker shutdown. The document lock currently covers opening/switching, not the entire extraction, so coordinate lifetime and concurrent requests together. |
| Import-specific | PDF import searches/extracts page images again for each product; item upserts commit per item under the established contract. | Profile representative layouts; cache page image geometry/bytes per page before considering changes to transaction policy. Preserve validated/Excel-image skips and KB-001 separately. |
| Import-specific | Excel import loads the workbook and rereads sheets through pandas for descriptions and header detection. | Reuse a workbook/sheet parse while retaining tolerant headers, cross-sheet precedence, duplicate handling, and embedded-image anchors. |
| Image-specific | Thumbnail decoding and crop-page rasterization still happen on the UI thread. The cropper already limits retained pages to those near the viewport. | Measure large images and complex PDF pages, then move decoding/rasterization to isolated workers; construct PhotoImages only on Tk's thread. |
| Lower priority | Many standalone DB calls rerun schema setup and attempt existing-column additions. | Replace repeated duplicate-column attempts with explicit metadata checks in a separately tested compatibility change. Retain each public method's commit contract. |

PDF/Excel import, export, and backup orchestration already runs in workers.
The full-list database query already retrieves linked images in bulk, and
code matching uses indexes/maps. No dependency or packaging rewrite is needed
for the confirmed launch fixes. Hardware, network-drive storage, and antivirus
were not established as causes; client-machine measurements are still needed
if slow launch persists after these changes.

## Validation

- The canonical `tools/check.ps1` passed: dependency consistency, compilation,
  imports, Ruff, the complete discovered suite, architecture boundaries,
  whitespace, UTF-8, and documentation links. Both fresh-schema and older-schema
  upgrade tests are included. Sandbox restrictions on temporary directories
  required running disposable-data checks outside the sandbox.
- Added regression coverage for repeated-path work per read and refresh scope,
  deferred startup imports, Vietnamese token search, edits/replaced items,
  dates, sorting, coalesced typing, refresh cancellation, unsaved-switch
  cancellation, page-image request count, and thumbnail selection/reference
  retention.
- Visible source-mode Windows smoke test with a disposable 10,000-item catalog:
  launch/table display, search, product selection, thumbnail selection,
  edit/save, unsaved-switch cancellation, and clean window close passed.
  The existing cached PDF lifetime issue described above prevented immediate
  fixture-directory cleanup until the Python process exited.
- The checked-in PyInstaller spec built successfully into temporary work/output
  directories. The frozen EXE displayed the empty first-launch catalog and,
  after restart, a generated 10,000-product catalog. Existing `build/`, `dist/`,
  and configured user-data directories were not used for this check.
- PDF/Excel import, backup, and workbook export behavior was checked by the
  regression suite. Full manual import/export, crop, image rotation/reorder,
  desktop Excel inspection, and testing on the reporting user's PC were not
  performed as part of this change.
