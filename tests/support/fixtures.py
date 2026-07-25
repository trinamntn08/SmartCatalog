from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz
from openpyxl import Workbook
from PIL import Image


@dataclass(slots=True)
class TemporaryProject:
    """Disposable project layout that never uses the repository runtime data."""

    prefix: str = "smartcatalog-test-"
    _temporary_directory: Optional[tempfile.TemporaryDirectory[str]] = None
    root: Optional[Path] = None

    def __enter__(self) -> "TemporaryProject":
        self._temporary_directory = tempfile.TemporaryDirectory(prefix=self.prefix)
        self.root = Path(self._temporary_directory.name).resolve()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
        self._temporary_directory = None

    def path(self, *parts: str) -> Path:
        if self.root is None:
            raise RuntimeError("TemporaryProject must be used as a context manager")
        return self.root.joinpath(*parts)

    def create_runtime_layout(self) -> Path:
        data_dir = self.path("config", "database")
        for relative in (
            ("sql",),
            ("catalog_pdfs",),
            ("assets", "excel_import"),
            ("assets", "pdf_import"),
            ("assets", "manual_import"),
        ):
            data_dir.joinpath(*relative).mkdir(parents=True, exist_ok=True)
        return data_dir


def create_sqlite_fixture(path: Path) -> Path:
    """Create a small generic database used to exercise snapshot helpers."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE sample (
                    id INTEGER PRIMARY KEY,
                    code TEXT NOT NULL,
                    value TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.executemany(
                "INSERT INTO sample(id, code, value) VALUES(?, ?, ?)",
                ((1, "A-001", "one"), (2, "B-002", "two")),
            )
    return path


def create_xlsx_fixture(path: Path) -> Path:
    """Create a deterministic workbook without touching application data."""

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalog"
    sheet.append(("Product Code", "Description", "Qty."))
    sheet.append(("A-001", "First item", 2))
    sheet.append(("B-002", "Second item", 3))
    workbook.save(path)
    workbook.close()
    return path


def create_image_fixture(
    path: Path,
    *,
    size: tuple[int, int] = (32, 24),
    color: tuple[int, int, int] = (20, 100, 180),
) -> Path:
    """Create a small RGB PNG fixture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with Image.new("RGB", size, color) as image:
        image.save(path, format="PNG")
    return path


def create_pdf_fixture(path: Path, *, text: str = "Product A-001") -> Path:
    """Create a one-page PDF suitable for basic harness and geometry tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        page = document.new_page(width=300, height=200)
        page.insert_text((36, 72), text)
        document.save(path)
    finally:
        document.close()
    return path
