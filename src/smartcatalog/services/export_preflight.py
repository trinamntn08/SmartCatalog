from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

from smartcatalog.utils.code_normalization import (
    build_unique_normalized_code_index,
    normalize_code_soft,
)
from smartcatalog.utils.filename_utils import sanitize_filename
from smartcatalog.utils.hashing import sha256_bytes

from .workbook_product_reader import WorkbookProductRow


@dataclass
class ExportPreflightItem:
    code: str
    item_id: Optional[int] = None
    description_vi: str = ""
    description_en: str = ""
    pdf_description: str = ""
    image_paths: list[str] = field(default_factory=list)
    persisted_image_paths: list[str] = field(default_factory=list)
    require_description_vi: bool = True
    require_description_en: bool = True
    missing_vi: bool = False
    missing_en: bool = False
    missing_images: bool = False
    unknown_code: bool = False

    def __post_init__(self) -> None:
        if self.image_paths and not self.persisted_image_paths:
            self.persisted_image_paths = list(self.image_paths)

    @property
    def has_issue(self) -> bool:
        return bool(
            self.missing_vi
            or self.missing_en
            or self.missing_images
            or self.unknown_code
        )

    @property
    def effective_description_en(self) -> str:
        """Return the English text that export will use and review should show."""
        return self.description_en or self.pdf_description

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


def validate_export_preflight_image(source_path: str | Path) -> str:
    """Validate a staged review image without changing catalog state."""
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Không tìm thấy tệp ảnh: {source}")
    supported_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    if source.suffix.casefold() not in supported_suffixes:
        raise ValueError("Vui lòng chọn ảnh PNG, JPG, WEBP hoặc BMP.")
    try:
        with Image.open(source) as selected_image:
            selected_image.verify()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError("Không thể đọc tệp ảnh đã chọn.") from exc
    return str(source)


def save_export_preflight_changes(
    issue: ExportPreflightItem,
    *,
    db,
    description_vi: str,
    description_en: str,
    image_paths: list[str],
) -> None:
    """Persist staged descriptions and ordered images from export review."""
    description_vi = str(description_vi or "").strip()
    description_en = str(description_en or "").strip()
    if not issue.description_en and description_en == issue.pdf_description:
        description_en = ""

    data_dir = getattr(db, "data_dir", None)
    if data_dir is None:
        raise RuntimeError("Chưa cấu hình thư mục dữ liệu catalog.")

    output_dir = Path(data_dir) / "assets" / "manual_import"
    output_dir.mkdir(parents=True, exist_ok=True)
    persisted_paths = set(issue.persisted_image_paths)
    saved_paths: list[str] = []
    created_paths: list[Path] = []
    seen_paths: set[str] = set()
    try:
        for path in image_paths:
            source = Path(validate_export_preflight_image(path))
            if str(source) in persisted_paths:
                saved_path = str(source)
            else:
                image_bytes = source.read_bytes()
                image_hash = sha256_bytes(image_bytes)
                destination = output_dir / (
                    f"{sanitize_filename(issue.code)}_{image_hash[:12]}"
                    f"{source.suffix.casefold()}"
                )
                if not destination.exists():
                    try:
                        shutil.copy2(source, destination)
                    except Exception:
                        destination.unlink(missing_ok=True)
                        raise
                    created_paths.append(destination)
                saved_path = str(destination)
            if saved_path not in seen_paths:
                seen_paths.add(saved_path)
                saved_paths.append(saved_path)

        item = db.get_item_by_code(issue.code)
        if item is None:
            db.upsert_by_code(code=issue.code, page=None)
            item = db.get_item_by_code(issue.code)
        if item is None:
            raise RuntimeError(f"Không thể tạo sản phẩm {issue.code}.")

        conn = db.connect()
        try:
            updated = db.update_excel_descriptions_by_code(
                code=issue.code,
                description_vi=description_vi,
                description_en=description_en,
                conn=conn,
            )
            if not updated:
                raise RuntimeError(f"Không thể cập nhật sản phẩm {issue.code}.")

            existing_paths = db.list_asset_paths_for_item(int(item.id), conn=conn)
            existing_links = db.list_asset_links_for_item(int(item.id), conn=conn)
            link_by_path = dict(zip(existing_paths, existing_links))
            db.clear_asset_links_for_item(int(item.id), conn=conn)

            for index, saved_path in enumerate(saved_paths):
                previous = link_by_path.get(saved_path)
                if previous is None:
                    asset_id = db.upsert_asset(
                        pdf_path=str(getattr(item, "pdf_path", "") or ""),
                        page=int(getattr(item, "page", 0) or 0),
                        asset_path=saved_path,
                        bbox=None,
                        source="add",
                        sha256=sha256_bytes(Path(saved_path).read_bytes()),
                        conn=conn,
                    )
                    match_method = "manual"
                    score = None
                    verified = True
                else:
                    asset_id = int(previous["asset_id"])
                    match_method = str(previous["match_method"] or "manual")
                    score = previous["score"]
                    verified = bool(previous["verified"])
                db.link_asset_to_item(
                    item_id=int(item.id),
                    asset_id=int(asset_id),
                    match_method=match_method,
                    score=score,
                    verified=verified,
                    is_primary=(index == 0),
                    conn=conn,
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except Exception:
        for created_path in created_paths:
            created_path.unlink(missing_ok=True)
        raise

    saved_item = db.get_item_by_code(issue.code)
    if saved_item is None:
        raise RuntimeError(f"Không thể tải lại sản phẩm {issue.code}.")
    issue.item_id = int(saved_item.id)
    issue.image_paths = [
        str(path)
        for path in list(getattr(saved_item, "images", []) or [])
        if Path(path).is_file()
    ]
    issue.persisted_image_paths = list(issue.image_paths)
    issue.description_vi = description_vi
    issue.description_en = description_en
    issue.unknown_code = False
    issue.missing_vi = bool(
        issue.require_description_vi and not issue.description_vi
    )
    issue.missing_en = bool(
        issue.require_description_en and not issue.effective_description_en
    )
    issue.missing_images = not bool(issue.image_paths)


def save_export_preflight_descriptions(
    issue: ExportPreflightItem,
    *,
    db,
    description_vi: str,
    description_en: str,
) -> None:
    """Persist edited descriptions, creating an unknown workbook code."""
    save_export_preflight_changes(
        issue,
        db=db,
        description_vi=description_vi,
        description_en=description_en,
        image_paths=list(issue.persisted_image_paths),
    )


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
                ExportPreflightItem(
                    code=product.code,
                    require_description_vi=include_description_vi,
                    require_description_en=include_description_en,
                    unknown_code=True,
                )
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
                persisted_image_paths=list(image_paths),
                require_description_vi=include_description_vi,
                require_description_en=include_description_en,
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
