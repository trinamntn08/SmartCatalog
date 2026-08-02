from __future__ import annotations

import hashlib
import io
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
from PIL import Image

from tests import support as _test_support  # Ensures src/ is importable.
from tests.support.fixtures import TemporaryProject

from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.loader.extract_item import CatalogItem, extract_items_from_page
from smartcatalog.ui.controllers.pdf_import_adapter import build_or_update_db_from_pdf
from smartcatalog.loader.pdf_image_extractor import (
    distance_between_rects,
    handle_jpeg2000_conversion,
    nearest_image_for_code_on_page,
    save_image_bytes_as_png,
)
from smartcatalog.services.pdf_import import import_pdf_catalog


def png_bytes(
    color: tuple[int, int, int, int],
    *,
    size: tuple[int, int] = (40, 30),
) -> bytes:
    buffer = io.BytesIO()
    with Image.new("RGBA", size, color) as image:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def add_catalog_headers(page: fitz.Page) -> None:
    for y, text in (
        (30, "Deutsche Kategorie"),
        (45, "English Category"),
        (60, "Categoria Espanola"),
        (75, "Categoria Italiana"),
    ):
        page.insert_text((36, y), text, fontsize=10)


def add_catalog_item(
    page: fitz.Page,
    *,
    x: float,
    y: float,
    code: str,
    author: str,
    dimension: str,
    english_description: str,
) -> None:
    page.insert_text((x, y - 20), author, fontsize=9)
    page.insert_text((x, y), code, fontsize=9)
    page.insert_text((x + 75, y), dimension, fontsize=9)
    for offset, text in (
        (20, "Deutsche Beschreibung"),
        (28, english_description),
        (36, "Descripcion"),
        (44, "Descrizione"),
    ):
        page.insert_text((x, y + offset), text, fontsize=6)


def create_extraction_pdf(
    path: Path,
    *,
    blank_first_page: bool = False,
    include_images: bool = False,
    multiple_columns: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        if blank_first_page:
            blank = document.new_page(width=600, height=500)
            blank.insert_text((36, 36), "No products on this page")

        page = document.new_page(width=600, height=500)
        add_catalog_headers(page)
        add_catalog_item(
            page,
            x=70,
            y=260,
            code="12-345-67",
            author="BUCK",
            dimension="18 cm",
            english_description="English small description",
        )
        if multiple_columns:
            add_catalog_item(
                page,
                x=350,
                y=260,
                code="98-765-43",
                author="CLAR",
                dimension="220 mm",
                english_description="Second English description",
            )
        if include_images:
            page.insert_image(
                fitz.Rect(75, 130, 145, 200),
                stream=png_bytes((200, 20, 20, 255)),
            )
            # Below the code: current nearest-image policy deliberately ignores it.
            page.insert_image(
                fitz.Rect(75, 300, 145, 370),
                stream=png_bytes((20, 20, 200, 255)),
            )
            if multiple_columns:
                page.insert_image(
                    fitz.Rect(355, 130, 425, 200),
                    stream=png_bytes((20, 180, 20, 255)),
                )
        document.save(path)
    finally:
        document.close()
    return path


def _nearest_image_bytes(path: Path, *, page_index: int, code: str) -> bytes:
    document = fitz.open(path)
    try:
        page = document[page_index]
        item = next(
            item for item in extract_items_from_page(page) if item.code == code
        )
        nearest = nearest_image_for_code_on_page(page, fitz.Rect(item.bbox))
        if nearest is None:
            raise AssertionError(f"No nearest image found for fixture code {code}")
        return nearest[0]
    finally:
        document.close()


class ImmediateStatus:
    def __init__(self) -> None:
        self.values: list[str] = []

    def after(self, _delay: int, callback) -> None:
        callback()

    def set(self, value: str) -> None:
        self.values.append(value)


class PDFTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.project.__enter__()
        self.addCleanup(self.project.__exit__, None, None, None)
        self.data_dir = self.project.create_runtime_layout()
        self.db = CatalogDB(
            self.data_dir / "sql" / "catalog.db",
            data_dir=self.data_dir,
        )

    def state_for(self, pdf_path: Path):
        return SimpleNamespace(
            catalog_pdf_path=pdf_path,
            db=self.db,
            assets_dir=self.data_dir / "assets",
        )

    def create_blank_pdf(self, name: str = "blank.pdf") -> Path:
        path = self.project.path(name)
        document = fitz.open()
        try:
            document.new_page(width=300, height=200)
            document.save(path)
        finally:
            document.close()
        return path


class PDFFieldExtractionCharacterizationTests(PDFTestCase):
    def test_single_item_fields_are_extracted_from_generated_layout(self) -> None:
        path = create_extraction_pdf(self.project.path("single.pdf"))
        document = fitz.open(path)
        try:
            items = extract_items_from_page(document[0])
        finally:
            document.close()

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.code, "12-345-67")
        self.assertEqual(item.category, "English Category")
        self.assertEqual(item.author, "BUCK")
        self.assertEqual(item.dimension, "18 cm")
        self.assertEqual(item.small_description, "English small description")
        self.assertLess(item.bbox[0], item.bbox[2])
        self.assertLess(item.bbox[1], item.bbox[3])

    def test_two_column_layout_keeps_fields_with_their_code(self) -> None:
        path = create_extraction_pdf(
            self.project.path("columns.pdf"),
            multiple_columns=True,
        )
        document = fitz.open(path)
        try:
            items = extract_items_from_page(document[0])
        finally:
            document.close()

        by_code = {item.code: item for item in items}
        self.assertEqual(set(by_code), {"12-345-67", "98-765-43"})
        self.assertEqual(
            (
                by_code["12-345-67"].author,
                by_code["12-345-67"].dimension,
                by_code["12-345-67"].small_description,
            ),
            ("BUCK", "18 cm", "English small description"),
        )
        self.assertEqual(
            (
                by_code["98-765-43"].author,
                by_code["98-765-43"].dimension,
                by_code["98-765-43"].small_description,
            ),
            ("CLAR", "220 mm", "Second English description"),
        )

    def test_page_without_product_code_returns_no_items(self) -> None:
        path = create_extraction_pdf(
            self.project.path("blank-first.pdf"),
            blank_first_page=True,
        )
        document = fitz.open(path)
        try:
            self.assertEqual(extract_items_from_page(document[0]), [])
        finally:
            document.close()


class PDFImageCharacterizationTests(PDFTestCase):
    def test_distance_uses_rectangle_centers(self) -> None:
        self.assertEqual(
            distance_between_rects(
                fitz.Rect(0, 0, 10, 10),
                fitz.Rect(30, 40, 40, 50),
            ),
            50.0,
        )

    def test_nearest_image_prefers_above_and_ignores_below_code(self) -> None:
        path = self.project.path("nearest.pdf")
        document = fitz.open()
        try:
            page = document.new_page(width=400, height=400)
            far_rect = fitz.Rect(20, 20, 70, 70)
            near_rect = fitz.Rect(130, 110, 190, 170)
            below_rect = fitz.Rect(130, 250, 190, 310)
            page.insert_image(far_rect, stream=png_bytes((200, 20, 20, 255)))
            page.insert_image(near_rect, stream=png_bytes((20, 200, 20, 255)))
            page.insert_image(below_rect, stream=png_bytes((20, 20, 200, 255)))
            document.save(path)
        finally:
            document.close()

        reopened = fitz.open(path)
        try:
            result = nearest_image_for_code_on_page(
                reopened[0],
                fitz.Rect(130, 200, 200, 220),
            )
        finally:
            reopened.close()

        self.assertIsNotNone(result)
        image_bytes, extension, selected_rect = result
        self.assertEqual(extension, "png")
        # PyMuPDF aspect-fits the source image inside the requested rectangle.
        self.assertTrue(near_rect.contains(selected_rect))
        self.assertAlmostEqual(
            (selected_rect.x0 + selected_rect.x1) / 2,
            (near_rect.x0 + near_rect.x1) / 2,
        )
        self.assertAlmostEqual(
            (selected_rect.y0 + selected_rect.y1) / 2,
            (near_rect.y0 + near_rect.y1) / 2,
        )
        with Image.open(io.BytesIO(image_bytes)) as selected:
            self.assertEqual(selected.convert("RGB").getpixel((0, 0)), (20, 200, 20))

    def test_page_with_code_and_no_image_returns_none(self) -> None:
        path = create_extraction_pdf(self.project.path("no-image.pdf"))
        document = fitz.open(path)
        try:
            item = extract_items_from_page(document[0])[0]
            result = nearest_image_for_code_on_page(
                document[0],
                fitz.Rect(item.bbox),
            )
        finally:
            document.close()
        self.assertIsNone(result)

    def test_conversion_and_png_save_preserve_current_output_contract(self) -> None:
        source = png_bytes((10, 20, 30, 120), size=(16, 12))
        passthrough, extension = handle_jpeg2000_conversion(source, "png")
        converted, converted_extension = handle_jpeg2000_conversion(source, "jp2")
        output = self.project.path("converted", "output.png")
        save_image_bytes_as_png(source, output)

        self.assertIs(passthrough, source)
        self.assertEqual(extension, "png")
        self.assertEqual(converted_extension, "png")
        self.assertTrue(converted.startswith(b"\x89PNG"))
        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (16, 12))


class PDFImportCharacterizationTests(PDFTestCase):
    def test_extracted_service_returns_typed_counts_without_tkinter(self) -> None:
        path = create_extraction_pdf(
            self.project.path("service.pdf"),
            blank_first_page=True,
            include_images=False,
        )
        statuses: list[str] = []

        result = import_pdf_catalog(
            self.state_for(path),
            status_callback=statuses.append,
        )

        self.assertEqual(result.scanned, 2)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.skipped_validated, 0)
        self.assertEqual(result.skipped_excel, 0)
        self.assertEqual(result.skipped_existing, 0)
        self.assertEqual(result.images_added, 0)
        self.assertTrue(statuses[-1].startswith("✅ Xong."))

    def test_known_pdf_import_image_link_rollback_kb001(self) -> None:
        path = create_extraction_pdf(
            self.project.path("import.pdf"),
            blank_first_page=True,
            include_images=True,
        )
        status = ImmediateStatus()

        build_or_update_db_from_pdf(
            self.state_for(path),
            status_message=status,
        )

        item = self.db.get_item_by_code("12-345-67")
        self.assertIsNotNone(item)
        self.assertEqual(item.page, 2)
        self.assertEqual(item.pdf_path, str(path))
        self.assertEqual(item.category, "English Category")
        self.assertEqual(item.author, "BUCK")
        self.assertEqual(item.dimension, "18 cm")
        self.assertEqual(item.small_description, "English small description")
        self.assertEqual(item.images, [])

        with closing(self.db.connect()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM item_asset_links").fetchone()[0],
                0,
            )

        # Known behavior KB-001 writes the PNG before the uncommitted asset/link rows
        # are rolled back when the caller-owned connection closes.
        written = list(
            (self.data_dir / "assets" / "pdf_import" / "p0002").glob(
                "12-345-67_*.png"
            )
        )
        self.assertEqual(len(written), 1)
        hash_suffix = hashlib.sha256(
            _nearest_image_bytes(path, page_index=1, code="12-345-67")
        ).hexdigest()[:12]
        self.assertTrue(written[0].stem.endswith(hash_suffix))
        self.assertTrue(status.values)

    def test_repeated_import_updates_item_but_does_not_replace_existing_image(self) -> None:
        path = create_extraction_pdf(
            self.project.path("repeat.pdf"),
            include_images=True,
        )
        state = self.state_for(path)
        build_or_update_db_from_pdf(state)
        before = self.db.get_item_by_code("12-345-67")

        decisions: list[str] = []
        build_or_update_db_from_pdf(
            state,
            on_existing_item_decision=lambda code: decisions.append(code) or True,
        )
        after = self.db.get_item_by_code("12-345-67")

        self.assertEqual(decisions, ["12-345-67"])
        self.assertEqual(after.id, before.id)
        self.assertEqual(after.images, before.images)
        with closing(self.db.connect()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM item_asset_links").fetchone()[0],
                0,
            )
        self.assertEqual(
            len(
                list(
                    (self.data_dir / "assets" / "pdf_import" / "p0001").glob(
                        "12-345-67_*.png"
                    )
                )
            ),
            1,
        )

    def test_existing_item_callback_can_preserve_current_values(self) -> None:
        path = create_extraction_pdf(self.project.path("skip-existing.pdf"))
        self.db.upsert_by_code(
            code="12-345-67",
            page=99,
            description="Keep me",
            category="Existing",
        )
        decisions: list[str] = []

        build_or_update_db_from_pdf(
            self.state_for(path),
            on_existing_item_decision=lambda code: decisions.append(code) or False,
        )
        item = self.db.get_item_by_code("12-345-67")

        self.assertEqual(decisions, ["12-345-67"])
        self.assertEqual(item.page, 99)
        self.assertEqual(item.description, "Keep me")
        self.assertEqual(item.category, "Existing")

    def test_validated_item_skips_before_update_callback(self) -> None:
        path = create_extraction_pdf(self.project.path("validated.pdf"))
        self.db.upsert_by_code(
            code="12-345-67",
            page=88,
            description="Validated value",
            validated=True,
            validated_at="2025-01-02 03:04:05",
        )
        decisions: list[str] = []

        build_or_update_db_from_pdf(
            self.state_for(path),
            on_existing_item_decision=lambda code: decisions.append(code) or True,
        )
        item = self.db.get_item_by_code("12-345-67")

        self.assertEqual(decisions, [])
        self.assertEqual(item.page, 88)
        self.assertEqual(item.description, "Validated value")
        self.assertTrue(item.validated)

    def test_excel_image_skips_before_update_callback(self) -> None:
        path = create_extraction_pdf(
            self.project.path("excel-protected.pdf"),
            include_images=True,
        )
        item_id = self.db.upsert_by_code(
            code="12-345-67",
            page=77,
            description="Excel protected",
        )
        asset_id = self.db.upsert_asset(
            pdf_path="excel:source.xlsx",
            page=0,
            asset_path=str(self.data_dir / "assets" / "excel_import" / "image.png"),
            source="excel",
        )
        self.db.link_asset_to_item(
            item_id=item_id,
            asset_id=asset_id,
            match_method="excel",
            verified=True,
            is_primary=True,
        )
        decisions: list[str] = []

        build_or_update_db_from_pdf(
            self.state_for(path),
            on_existing_item_decision=lambda code: decisions.append(code) or True,
        )
        item = self.db.get_item_by_code("12-345-67")

        self.assertEqual(decisions, [])
        self.assertEqual(item.page, 77)
        self.assertEqual(item.description, "Excel protected")
        self.assertEqual(self.db.list_image_sources_for_item(item.id)[0][1], "excel")

    def test_item_with_non_excel_image_updates_without_replacing_image(self) -> None:
        path = create_extraction_pdf(
            self.project.path("manual-image.pdf"),
            include_images=True,
        )
        item_id = self.db.upsert_by_code(
            code="12-345-67",
            page=66,
            description="Old description",
        )
        manual_path = self.data_dir / "assets" / "manual_import" / "manual.png"
        manual_path.write_bytes(png_bytes((100, 100, 100, 255)))
        asset_id = self.db.upsert_asset(
            pdf_path=str(path),
            page=1,
            asset_path=str(manual_path),
            source="add",
        )
        self.db.link_asset_to_item(
            item_id=item_id,
            asset_id=asset_id,
            match_method="manual",
            verified=True,
            is_primary=True,
        )

        build_or_update_db_from_pdf(
            self.state_for(path),
            on_existing_item_decision=lambda _code: True,
        )
        item = self.db.get_item_by_code("12-345-67")

        self.assertEqual(item.page, 1)
        self.assertNotEqual(item.description, "Old description")
        self.assertEqual(item.images, [str(manual_path)])
        self.assertEqual(self.db.list_image_sources_for_item(item.id)[0][1], "add")

    def test_failure_closes_pdf_and_database_connection(self) -> None:
        path = self.create_blank_pdf("failure.pdf")

        with (
            patch(
                "smartcatalog.ui.controllers.pdf_import_adapter.extract_items_from_page",
                side_effect=RuntimeError("characterized failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "characterized failure"),
        ):
            build_or_update_db_from_pdf(self.state_for(path))

        renamed = path.with_name("renamed-after-failure.pdf")
        path.rename(renamed)
        self.assertTrue(renamed.is_file())
        with closing(self.db.connect()) as conn:
            conn.execute(
                "INSERT INTO items(code, description) VALUES(?, ?)",
                ("99-999-99", "Connection is writable"),
            )
            conn.commit()

    def test_missing_state_inputs_raise_current_errors(self) -> None:
        missing_pdf_state = SimpleNamespace(
            catalog_pdf_path=None,
            db=self.db,
            assets_dir=self.data_dir / "assets",
        )
        with self.assertRaises(RuntimeError):
            build_or_update_db_from_pdf(missing_pdf_state)

        no_db_state = SimpleNamespace(
            catalog_pdf_path=self.create_blank_pdf("no-db.pdf"),
            db=None,
            assets_dir=self.data_dir / "assets",
        )
        with self.assertRaises(RuntimeError):
            build_or_update_db_from_pdf(no_db_state)

        absent_state = self.state_for(self.project.path("absent.pdf"))
        with self.assertRaises(FileNotFoundError):
            build_or_update_db_from_pdf(absent_state)


if __name__ == "__main__":
    unittest.main()
