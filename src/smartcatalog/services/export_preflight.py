from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from smartcatalog.utils.code_normalization import (
    build_unique_normalized_code_index,
    normalize_code_soft,
)

from .workbook_product_reader import WorkbookProductRow


@dataclass
class ExportPreflightItem:
    code: str
    item_id: Optional[int] = None
    description_vi: str = ""
    description_en: str = ""
    pdf_description: str = ""
    image_paths: list[str] = field(default_factory=list)
    missing_vi: bool = False
    missing_en: bool = False
    missing_images: bool = False
    unknown_code: bool = False

    @property
    def has_issue(self) -> bool:
        return bool(
            self.missing_vi
            or self.missing_en
            or self.missing_images
            or self.unknown_code
        )

    def status_text(self) -> str:
        statuses: list[str] = []
        if self.unknown_code:
            statuses.append("Mã không tồn tại")
        if self.missing_vi:
            statuses.append("Thiếu VI")
        if self.missing_en:
            statuses.append("Thiếu EN")
        if self.missing_images:
            statuses.append("Thiếu ảnh")
        return ", ".join(statuses) or "Sẵn sàng"


@dataclass(frozen=True)
class ExportPreflight:
    rows: tuple[WorkbookProductRow, ...]
    issues: tuple[ExportPreflightItem, ...]


def save_export_preflight_descriptions(
    issue: ExportPreflightItem,
    *,
    db,
    description_vi: str,
    description_en: str,
) -> None:
    """Persist edited descriptions, creating an unknown workbook code."""
    description_vi = str(description_vi or "").strip()
    description_en = str(description_en or "").strip()

    updated = db.update_excel_descriptions_by_code(
        code=issue.code,
        description_vi=description_vi,
        description_en=description_en,
    )
    if not updated:
        db.upsert_by_code(
            code=issue.code,
            page=None,
            description_excel=description_en,
            description_vietnames_from_excel=description_vi,
        )

    saved_item = db.get_item_by_code(issue.code)
    if saved_item is None:
        raise RuntimeError(f"Could not save catalog item {issue.code}.")

    issue.item_id = int(saved_item.id)
    issue.description_vi = description_vi
    issue.description_en = description_en
    issue.unknown_code = False
    issue.missing_vi = not bool(description_vi)
    issue.missing_en = not bool(description_en)
    issue.missing_images = not bool(saved_item.images)


def prepare_export_preflight(
    rows: tuple[WorkbookProductRow, ...],
    *,
    db,
    include_description_vi: bool,
    include_description_en: bool,
) -> ExportPreflight:
    items = db.list_items()
    code_to_item = {str(item.code): item for item in items}
    exact_codes = set(code_to_item)
    normalized_index = build_unique_normalized_code_index(list(exact_codes))
    preflight_items: list[ExportPreflightItem] = []

    for product in rows:
        matched_code = _match_code(product.code, exact_codes, normalized_index)
        item = code_to_item.get(matched_code) if matched_code else None
        if item is None:
            preflight_items.append(
                ExportPreflightItem(code=product.code, unknown_code=True)
            )
            continue

        description_vi = str(
            getattr(item, "description_vietnames_from_excel", "") or ""
        ).strip()
        description_en = str(
            getattr(item, "description_excel", "") or ""
        ).strip()
        pdf_description = str(getattr(item, "description", "") or "").strip()
        effective_en = description_en or pdf_description
        image_paths = [
            str(path)
            for path in list(getattr(item, "images", []) or [])
            if Path(path).is_file()
        ]
        preflight_items.append(
            ExportPreflightItem(
                code=str(item.code),
                item_id=int(item.id),
                description_vi=description_vi,
                description_en=description_en,
                pdf_description=pdf_description,
                image_paths=image_paths,
                missing_vi=bool(include_description_vi and not description_vi),
                missing_en=bool(include_description_en and not effective_en),
                missing_images=not bool(image_paths),
            )
        )

    return ExportPreflight(rows=rows, issues=tuple(preflight_items))


def _match_code(
    code: str,
    exact_codes: set[str],
    normalized_index: dict[str, str],
) -> str:
    if code in exact_codes:
        return code
    return normalized_index.get(normalize_code_soft(code), "")
