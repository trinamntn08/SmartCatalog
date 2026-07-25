from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import fitz

from smartcatalog.loader.extract_item import extract_items_from_page
from smartcatalog.loader.pdf_image_extractor import (
    handle_jpeg2000_conversion,
    nearest_image_for_code_on_page,
    save_image_bytes_as_png,
)
from smartcatalog.state import AppState
from smartcatalog.utils.hashing import sha256_bytes


@dataclass(frozen=True)
class PdfImportResult:
    scanned: int
    updated: int
    skipped_validated: int
    skipped_excel: int
    skipped_existing: int
    images_added: int


StatusCallback = Callable[[str], None]
ExistingItemDecision = Callable[[str], bool]


def import_pdf_catalog(
    state: AppState,
    *,
    page_start: int = 1,
    page_end: Optional[int] = None,
    on_existing_item_decision: Optional[ExistingItemDecision] = None,
    status_callback: Optional[StatusCallback] = None,
    preview_callback: Optional[StatusCallback] = None,
    page_extractor=extract_items_from_page,
) -> PdfImportResult:
    if not state.catalog_pdf_path:
        raise RuntimeError(
            "Chưa đặt state.catalog_pdf_path. Vui lòng chọn PDF trước."
        )
    if state.db is None:
        raise RuntimeError(
            "Chưa có state.db. Vui lòng tạo CatalogDB trong main.py và gán vào state."
        )

    pdf_path = Path(state.catalog_pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không tìm thấy PDF: {pdf_path}")

    _report(status_callback, f"Đang mở PDF: {pdf_path.name}")
    connection = state.db.connect()
    document = None
    try:
        document = fitz.open(str(pdf_path))
        total_pages = len(document)
        start_index = max(0, page_start - 1)
        end_index = (
            page_end - 1 if page_end is not None else total_pages - 1
        )
        end_index = min(end_index, total_pages - 1)

        updated = 0
        scanned = 0
        skipped_validated = 0
        skipped_excel = 0
        skipped_existing = 0
        images_added = 0

        for page_index in range(start_index, end_index + 1):
            scanned += 1
            page_number = page_index + 1
            page = document[page_index]
            items = page_extractor(page)
            if not items:
                if scanned % 50 == 0:
                    _report(
                        status_callback,
                        f"Đang quét trang {page_number}/{end_index + 1}...",
                    )
                continue

            for item in items:
                existing = state.db.get_item_by_code(item.code, conn=connection)
                has_any_images = False
                has_excel_images = False
                if existing:
                    sources = state.db.list_image_sources_for_item(
                        existing.id,
                        conn=connection,
                    )
                    has_any_images = bool(sources)
                    has_excel_images = any(
                        source == "excel" for _path, source in sources
                    )
                    if existing.validated:
                        skipped_validated += 1
                        continue
                    if has_excel_images:
                        skipped_excel += 1
                        continue
                    if callable(on_existing_item_decision) and not bool(
                        on_existing_item_decision(item.code)
                    ):
                        skipped_existing += 1
                        continue

                description = " | ".join(
                    part
                    for part in (
                        item.category,
                        item.author,
                        item.dimension,
                        item.small_description,
                    )
                    if part
                )
                item_id = state.db.upsert_by_code(
                    code=item.code,
                    page=page_number,
                    category=item.category,
                    author=item.author,
                    dimension=item.dimension,
                    small_description=item.small_description,
                    validated=bool(existing.validated) if existing else False,
                    description=description,
                    pdf_path=str(pdf_path),
                    conn=connection,
                )
                updated += 1

                if not has_any_images:
                    nearest = nearest_image_for_code_on_page(
                        page,
                        fitz.Rect(item.bbox),
                    )
                    if nearest:
                        image_bytes, image_ext, image_rect = nearest
                        image_bytes, image_ext = handle_jpeg2000_conversion(
                            image_bytes,
                            image_ext,
                        )
                        image_hash = sha256_bytes(image_bytes)
                        safe_code = item.code.replace("/", "_")
                        output_dir = (
                            state.assets_dir
                            / "pdf_import"
                            / f"p{page_number:04d}"
                        )
                        output_path = (
                            output_dir
                            / f"{safe_code}_{image_hash[:12]}.png"
                        )
                        if not output_path.exists():
                            save_image_bytes_as_png(image_bytes, output_path)

                        asset_id = state.db.upsert_asset(
                            pdf_path=str(pdf_path),
                            page=page_number,
                            asset_path=str(output_path),
                            bbox=(
                                image_rect.x0,
                                image_rect.y0,
                                image_rect.x1,
                                image_rect.y1,
                            ),
                            source="extract",
                            sha256=image_hash,
                            conn=connection,
                        )
                        state.db.link_asset_to_item(
                            item_id=int(item_id),
                            asset_id=int(asset_id),
                            match_method="keyword_nearest",
                            score=None,
                            verified=False,
                            is_primary=False,
                            conn=connection,
                        )
                        images_added += 1

            if page_number % 10 == 0:
                _report(
                    status_callback,
                    f"Đã xử lý trang {page_number}/{end_index + 1} | "
                    f"sản phẩm đã cập nhật: {updated}",
                )
                _report(
                    preview_callback,
                    _preview_text(
                        page_number,
                        items,
                        images_added=images_added,
                        skipped_validated=skipped_validated,
                        skipped_excel=skipped_excel,
                        skipped_existing=skipped_existing,
                    ),
                )

        result = PdfImportResult(
            scanned=scanned,
            updated=updated,
            skipped_validated=skipped_validated,
            skipped_excel=skipped_excel,
            skipped_existing=skipped_existing,
            images_added=images_added,
        )
        _report(
            status_callback,
            f"✅ Xong. Trang đã quét: {result.scanned}. "
            f"Sản phẩm đã cập nhật: {result.updated}. "
            f"Bỏ qua validated: {result.skipped_validated}. "
            f"Bỏ qua excel: {result.skipped_excel}. "
            f"Giữ nguyên mã đã có: {result.skipped_existing}. "
            f"Đã gán ảnh: {result.images_added}.",
        )
        return result
    finally:
        try:
            if document is not None:
                document.close()
        finally:
            connection.close()


def _report(callback: Optional[StatusCallback], text: str) -> None:
    if callback is not None:
        callback(text)


def _preview_text(
    page_number: int,
    items,
    *,
    images_added: int,
    skipped_validated: int,
    skipped_excel: int,
    skipped_existing: int,
) -> str:
    return (
        f"Trang {page_number}\n"
        f"Tìm thấy {len(items)} mã sản phẩm\n"
        f"Ảnh đã gán: {images_added}\n"
        f"Bỏ qua (đã kiểm duyệt): {skipped_validated}\n"
        f"Bỏ qua (đã có ảnh Excel): {skipped_excel}\n"
        f"Giữ nguyên mã đã có: {skipped_existing}\n\n"
        f"Ví dụ:\n"
        + "\n".join(
            f"- {item.code}: {item.category} | {item.author} | "
            f"{item.small_description} | {item.dimension}"
            for item in items[:8]
        )
    )
