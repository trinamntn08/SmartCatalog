# SmartCatalog User Guide

[Documentation index](README.md)

## What SmartCatalog does

SmartCatalog helps you build, review, and export a medical product catalog.
Product information usually comes from a PDF catalog and one or more Excel
workbooks. The application keeps the working catalog in its own database.

## Recommended workflow

1. Back up existing data if the application already contains a catalog.
2. Import the catalog PDF.
3. Import Excel descriptions and embedded images.
4. Review product information and images.
5. Mark verified products as validated.
6. Back up the completed catalog.
7. Export the required Excel workbook and inspect it before delivery.

## Import a PDF catalog

1. Select the PDF import action from the top toolbar.
2. Choose a new PDF, or confirm that the currently selected PDF should be
   reused.
3. When an existing product code is found, choose whether to update it. The
   same decision can be applied to all remaining existing items.
4. Wait for the background import to finish.
5. Review extracted fields and images before validating products.

PDF page numbers displayed by SmartCatalog start at 1. Validated items and
items with Excel-sourced images receive additional protection during a PDF
re-import.

## Import an Excel catalog

1. Select the Excel import action.
2. Choose an `.xlsx` or supported `.xls` workbook.
3. Decide whether existing matching products should be updated.
4. Wait for the import summary.
5. Review missing or ambiguous product codes.

SmartCatalog detects header rows and common Vietnamese or English column names
across multiple sheets. Exact product-code matches are preferred. A normalized
match is used only when it identifies one unique product.

Existing non-empty user descriptions are not automatically replaced by the
description dictionary. Embedded workbook images are deduplicated before being
linked to products.

## Review and edit products

- Use search, filters, sorting, column movement, and column visibility to find
  products.
- Select a row to load its editable fields and images.
- Save before selecting another product if you want to keep your changes.
- Use Add for products missing from imported sources.
- Delete only disposable or confirmed-unwanted products.
- Mark a product as validated only after checking its fields and images.

The product code is the unique business key used for matching imports and
exports. Change it carefully.

## Manage images

For the selected product you can:

- add an image file;
- assign an image candidate extracted from the current PDF page;
- crop a region directly from the PDF;
- rotate an image;
- remove an image link;
- drag images into the required order.

The first image in the saved UI order becomes the primary image. Provenance
labels identify images imported from Excel, extracted from PDF, cropped, or
added manually.

## Back up data

Use the built-in backup action and choose a destination outside the active
application folder. A backup can include:

- the SQLite catalog database;
- product assets;
- copied catalog PDFs;
- application settings.

Do not manually delete `config\database\` to reset the program. That directory
contains the working catalog and associated user data.

## Export an Excel catalog

1. Select the export action.
2. Choose the input workbook containing product codes and quantities.
3. Choose Vietnamese, English, or bilingual descriptions and image-order
   options.
4. Resolve missing descriptions, images, or codes in the pre-export review.
5. Continue or cancel the export.
6. Open the resulting workbook in desktop Excel.
7. Check descriptions, image order, branding, page layout, and print settings.

The export performs exact matching first, then unique normalized matching.
Unknown and incomplete rows may be highlighted for review.

## Application data locations

In source mode, data is stored under the project directory. In the Windows
release, data is stored beside `SmartCatalog.exe`:

```text
config/database/
├── sql/catalog.db
├── settings.json
├── catalog_pdfs/
└── assets/
    ├── excel_import/
    ├── pdf_import/
    └── manual_import/
```

The release package intentionally starts without the development database or
imported user content. First launch creates the writable directory structure.

## Troubleshooting

- If the application starts with an empty catalog, confirm whether you launched
  the source version or a separate release folder. Each location has its own
  `config\database\sql\catalog.db`.
- If a PDF or Excel operation takes time, wait for the status bar; long work
  runs in the background.
- If export data is missing, check the product code and the pre-export review.
- If an image is blank, reselect the product and confirm that the underlying
  asset file still exists.
- If a workbook is locked, close it in Excel before importing or exporting.

For maintenance or build issues, use the [developer guide](DEVELOPMENT.md).
