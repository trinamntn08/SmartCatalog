from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

import fitz
from openpyxl import load_workbook
from PIL import Image

from tests.support.fixtures import (
    TemporaryProject,
    create_image_fixture,
    create_pdf_fixture,
    create_sqlite_fixture,
    create_xlsx_fixture,
)
from tests.support.snapshots import (
    sha256_file,
    snapshot_sqlite,
    snapshot_workbook,
    snapshot_xlsx_package,
    write_snapshot,
)


class TemporaryProjectTests(unittest.TestCase):
    def test_context_creates_and_removes_isolated_directory(self) -> None:
        project_root: Path
        with TemporaryProject() as project:
            project_root = project.path()
            self.assertTrue(project_root.is_dir())
            self.assertNotIn("SmartCatalog_V2", str(project_root))

            data_dir = project.create_runtime_layout()
            self.assertEqual(
                data_dir,
                project_root / "config" / "database",
            )
            self.assertTrue((data_dir / "sql").is_dir())
            self.assertTrue((data_dir / "assets" / "excel_import").is_dir())

        self.assertFalse(project_root.exists())

    def test_path_requires_active_context(self) -> None:
        project = TemporaryProject()
        with self.assertRaises(RuntimeError):
            project.path("config")


class FixtureBuilderTests(unittest.TestCase):
    def test_sqlite_fixture_and_snapshot(self) -> None:
        with TemporaryProject() as project:
            db_path = create_sqlite_fixture(project.path("fixtures", "sample.db"))
            snapshot = snapshot_sqlite(db_path)

            self.assertEqual(
                snapshot["tables"]["sample"]["rows"],
                [[1, "A-001", "one"], [2, "B-002", "two"]],
            )
            with closing(sqlite3.connect(db_path)) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM sample").fetchone()[0],
                    2,
                )

    def test_workbook_fixture_and_snapshots(self) -> None:
        with TemporaryProject() as project:
            workbook_path = create_xlsx_fixture(project.path("fixtures", "catalog.xlsx"))
            snapshot = snapshot_workbook(workbook_path)
            package = snapshot_xlsx_package(workbook_path)

            self.assertEqual(snapshot["sheets"][0]["title"], "Catalog")
            self.assertIn(["A2", "A-001"], snapshot["sheets"][0]["cells"])
            self.assertIn("xl/workbook.xml", package)

            workbook = load_workbook(workbook_path, read_only=True)
            try:
                self.assertEqual(workbook["Catalog"]["C3"].value, 3)
            finally:
                workbook.close()

    def test_image_fixture_and_hash(self) -> None:
        with TemporaryProject() as project:
            image_path = create_image_fixture(project.path("fixtures", "image.png"))
            first_hash = sha256_file(image_path)
            second_hash = sha256_file(image_path)

            with Image.open(image_path) as image:
                self.assertEqual(image.size, (32, 24))
                self.assertEqual(image.mode, "RGB")
            self.assertEqual(first_hash, second_hash)

    def test_pdf_fixture(self) -> None:
        with TemporaryProject() as project:
            pdf_path = create_pdf_fixture(project.path("fixtures", "catalog.pdf"))
            document = fitz.open(pdf_path)
            try:
                self.assertEqual(len(document), 1)
                self.assertIn("Product A-001", document[0].get_text())
            finally:
                document.close()

    def test_snapshot_writer_uses_utf8_json(self) -> None:
        with TemporaryProject() as project:
            snapshot_path = write_snapshot(
                project.path("snapshots", "sample.json"),
                {"description": "Sản phẩm"},
            )
            content = snapshot_path.read_text(encoding="utf-8")
            self.assertIn("Sản phẩm", content)


if __name__ == "__main__":
    unittest.main()
