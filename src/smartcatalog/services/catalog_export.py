from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from smartcatalog.utils.code_normalization import (
    build_unique_normalized_code_index,
    normalize_code_soft,
)
from smartcatalog.utils.post_processing import (
    DEFAULT_SHEET_NAME,
    PostProcessingRow,
    apply_post_processing_branding,
    write_post_processing_sheet,
)

from .workbook_product_reader import WorkbookProductRow


@dataclass(frozen=True)
class CatalogExportOptions:
    include_description_vi: bool
    include_description_en: bool
    preserve_image_order: bool


@dataclass(frozen=True)
class CatalogExportResult:
    xlsx_path: str
    matched: int
    total: int
    images_found: int
    missing_vi: int
    missing_en: int
    missing_images: int
    missing_codes: tuple[str, ...]


def export_catalog(
    xlsx_path: str | Path,
    rows: tuple[WorkbookProductRow, ...],
    *,
    db,
    project_dir: str | Path,
    options: CatalogExportOptions,
) -> CatalogExportResult:
    items = db.list_items()
    code_to_item = {str(item.code): item for item in items}
    exact_codes = set(code_to_item)
    normalized_index = build_unique_normalized_code_index(list(exact_codes))

    matched = 0
    images_found = 0
    missing_vi = 0
    missing_en = 0
    missing_images = 0
    missing_codes: list[str] = []
    output_rows: list[PostProcessingRow] = []

    for index, product in enumerate(rows, start=1):
        matched_code = _match_code(product.code, exact_codes, normalized_index)
        item = code_to_item.get(matched_code) if matched_code else None
        if item is None:
            missing_codes.append(product.code)
        else:
            matched += 1

        description_vi = ""
        description_en = ""
        if item is not None:
            if options.include_description_vi and getattr(
                item, "description_vietnames_from_excel", ""
            ):
                description_vi = str(
                    item.description_vietnames_from_excel or ""
                ).strip()
            if options.include_description_en and getattr(
                item, "description_excel", ""
            ):
                description_en = str(item.description_excel or "").strip()
            if (
                options.include_description_en
                and not description_en
                and getattr(item, "description", "")
            ):
                description_en = str(item.description or "").strip()
            if options.include_description_vi and not description_vi:
                missing_vi += 1
            if options.include_description_en and not description_en:
                missing_en += 1

        primary_description = ""
        secondary_description = ""
        if options.include_description_vi and options.include_description_en:
            primary_description = description_vi
            secondary_description = description_en
        elif options.include_description_vi:
            primary_description = description_vi
        elif options.include_description_en:
            primary_description = description_en

        primary_missing = bool(
            (options.include_description_vi and not description_vi)
            if options.include_description_vi
            else (options.include_description_en and not description_en)
        )
        secondary_missing = bool(
            options.include_description_vi
            and options.include_description_en
            and not description_en
        )
        image_paths = (
            [
                str(path)
                for path in list(item.images or [])
                if Path(path).is_file()
            ]
            if item is not None
            else []
        )
        if item is not None and not image_paths:
            missing_images += 1
        if image_paths:
            images_found += 1

        output_rows.append(
            PostProcessingRow(
                number=index,
                code=product.code,
                qty=product.quantity,
                desc_primary=primary_description,
                desc_secondary=secondary_description,
                image_paths=image_paths,
                highlight_missing_desc=bool(item is None or primary_missing),
                force_secondary_row=bool(
                    options.include_description_vi
                    and options.include_description_en
                ),
                highlight_missing_secondary=secondary_missing,
            )
        )

    path = Path(xlsx_path)
    workbook = load_workbook(path)
    try:
        old_output_names = {"form đầu ra", "post processing"}
        for worksheet in list(workbook.worksheets[1:]):
            if worksheet.title.strip().casefold() in old_output_names:
                workbook.remove(worksheet)
        write_post_processing_sheet(
            workbook,
            output_rows,
            preserve_image_order=options.preserve_image_order,
            sheet_name=DEFAULT_SHEET_NAME,
            index=1,
        )
        workbook.save(path)
    finally:
        workbook.close()

    apply_post_processing_branding(path, project_dir=project_dir)
    return CatalogExportResult(
        xlsx_path=str(path),
        matched=matched,
        total=len(rows),
        images_found=images_found,
        missing_vi=missing_vi,
        missing_en=missing_en,
        missing_images=missing_images,
        missing_codes=tuple(missing_codes),
    )


def _match_code(
    code: str,
    exact_codes: set[str],
    normalized_index: dict[str, str],
) -> str:
    if code in exact_codes:
        return code
    return normalized_index.get(normalize_code_soft(code), "")
