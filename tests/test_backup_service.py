from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from tests import support as _test_support
from tests.support.fixtures import TemporaryProject

from smartcatalog.services.backup_service import backup_catalog
from smartcatalog.ui.controllers.workflows_controller import (
    WorkflowsControllerMixin,
)
from smartcatalog.ui.main_window import MainWindow


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.project.__enter__()
        self.addCleanup(self.project.__exit__, None, None, None)

    def test_backup_copies_database_assets_pdfs_and_settings(self) -> None:
        database = self.project.path("runtime", "sql", "catalog.db")
        database.parent.mkdir(parents=True)
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE sample(value TEXT)")
            connection.execute("INSERT INTO sample VALUES('preserved')")
            connection.commit()
        finally:
            connection.close()

        assets = self.project.path("runtime", "assets")
        assets.mkdir(parents=True)
        (assets / "image.png").write_bytes(b"asset")
        pdfs = self.project.path("runtime", "catalog_pdfs")
        pdfs.mkdir(parents=True)
        (pdfs / "catalog.pdf").write_bytes(b"pdf")
        settings = self.project.path("runtime", "settings.json")
        settings.write_text('{"selected": true}', encoding="utf-8")

        manifest = backup_catalog(
            database_path=database,
            assets_dir=assets,
            catalog_pdfs_dir=pdfs,
            settings_path=settings,
            backup_dir=self.project.path("backup"),
        )

        with sqlite3.connect(manifest.database_path) as backup_connection:
            value = backup_connection.execute(
                "SELECT value FROM sample"
            ).fetchone()[0]
        self.assertEqual(value, "preserved")
        self.assertEqual((manifest.assets_path / "image.png").read_bytes(), b"asset")
        self.assertEqual(
            (manifest.catalog_pdfs_path / "catalog.pdf").read_bytes(),
            b"pdf",
        )
        self.assertEqual(
            manifest.settings_path.read_text(encoding="utf-8"),
            '{"selected": true}',
        )

    def test_backup_manifest_marks_missing_optional_sources(self) -> None:
        database = self.project.path("catalog.db")
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE sample(value TEXT)")

        manifest = backup_catalog(
            database_path=database,
            assets_dir=self.project.path("missing-assets"),
            catalog_pdfs_dir=self.project.path("missing-pdfs"),
            settings_path=self.project.path("missing-settings.json"),
            backup_dir=self.project.path("backup"),
        )

        self.assertTrue(manifest.database_path.is_file())
        self.assertIsNone(manifest.assets_path)
        self.assertIsNone(manifest.catalog_pdfs_path)
        self.assertIsNone(manifest.settings_path)

    def test_main_window_uses_extracted_workflow_controller(self) -> None:
        self.assertIs(
            MainWindow.on_backup_data,
            WorkflowsControllerMixin.on_backup_data,
        )
        self.assertIs(
            MainWindow.on_build_excel_db,
            WorkflowsControllerMixin.on_build_excel_db,
        )
        self.assertIs(
            MainWindow.on_search_images_from_excel,
            WorkflowsControllerMixin.on_search_images_from_excel,
        )
