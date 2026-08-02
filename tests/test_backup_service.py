from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import support as _test_support
from tests.support.fixtures import TemporaryProject

from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.services.backup_service import BackupError, backup_catalog
from smartcatalog.state import AppState
from smartcatalog.ui.controllers.workflows_controller import (
    WorkflowsControllerMixin,
    _database_data_dir,
)
from smartcatalog.ui.main_window import MainWindow


class BackupServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.project.__enter__()
        self.addCleanup(self.project.__exit__, None, None, None)

    def test_backup_copies_database_assets_and_pdfs(self) -> None:
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
        manifest = backup_catalog(
            database_path=database,
            assets_dir=assets,
            catalog_pdfs_dir=pdfs,
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

    def test_selected_database_uses_its_portable_folder_as_data_root(self) -> None:
        backup_database = self.project.path("moved", "catalog.db")
        nested_database = self.project.path("config", "database", "sql", "catalog.db")

        self.assertEqual(_database_data_dir(backup_database), backup_database.parent)
        self.assertEqual(
            _database_data_dir(nested_database),
            nested_database.parent.parent,
        )

    def test_database_switch_is_reopened_on_next_startup(self) -> None:
        project_dir = self.project.path("application")
        selected_database = self.project.path("backup", "catalog.db")
        selected_database.parent.mkdir(parents=True)
        selected_db = CatalogDB(
            selected_database,
            data_dir=selected_database.parent,
        )
        selected_db.upsert_by_code(code="PERSISTED-001", page=1)
        state = AppState(project_dir=project_dir)
        items_tree = SimpleNamespace(
            selection=lambda: (),
            selection_remove=lambda _selection: None,
        )
        window = SimpleNamespace(
            state=state,
            _busy=SimpleNamespace(get=lambda: False),
            _set_status=lambda _message: None,
            items_tree=items_tree,
            _clear_item_form=lambda: None,
            refresh_items=lambda: None,
            _update_pdf_tools_label=lambda: None,
        )

        WorkflowsControllerMixin._switch_database(window, selected_database)

        restarted_state = AppState(project_dir=project_dir)
        restarted_db = CatalogDB(
            restarted_state.db_path,
            data_dir=restarted_state.data_dir,
        )
        self.assertEqual(restarted_state.db_path, selected_database)
        self.assertIsNotNone(restarted_db.get_item_by_code("PERSISTED-001"))

    def test_backup_manifest_marks_missing_optional_sources(self) -> None:
        database = self.project.path("catalog.db")
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE sample(value TEXT)")

        manifest = backup_catalog(
            database_path=database,
            assets_dir=self.project.path("missing-assets"),
            catalog_pdfs_dir=self.project.path("missing-pdfs"),
            backup_dir=self.project.path("backup"),
        )

        self.assertTrue(manifest.database_path.is_file())
        self.assertIsNone(manifest.assets_path)
        self.assertIsNone(manifest.catalog_pdfs_path)

    def test_backup_converts_paths_under_data_directory_to_relative(self) -> None:
        runtime = self.project.path("runtime")
        database = runtime / "sql" / "catalog.db"
        database.parent.mkdir(parents=True)
        assets = runtime / "assets"
        assets.mkdir()
        image = assets / "image.png"
        image.write_bytes(b"asset")
        pdfs = runtime / "catalog_pdfs"
        pdfs.mkdir()
        pdf = pdfs / "catalog.pdf"
        pdf.write_bytes(b"pdf")
        with closing(sqlite3.connect(database)) as connection:
            connection.execute(
                "CREATE TABLE items(code TEXT, pdf_path TEXT)"
            )
            connection.execute(
                "CREATE TABLE assets(pdf_path TEXT, asset_path TEXT)"
            )
            connection.execute(
                "INSERT INTO items VALUES(?, ?)",
                ("ABC", str(pdf.resolve())),
            )
            connection.execute(
                "INSERT INTO assets VALUES(?, ?)",
                (str(pdf.resolve()), str(image.resolve())),
            )
            connection.commit()

        manifest = backup_catalog(
            database_path=database,
            assets_dir=assets,
            catalog_pdfs_dir=pdfs,
            backup_dir=self.project.path("backup"),
        )

        with closing(sqlite3.connect(manifest.database_path)) as connection:
            item_pdf = connection.execute(
                "SELECT pdf_path FROM items"
            ).fetchone()[0]
            asset_pdf, asset_path = connection.execute(
                "SELECT pdf_path, asset_path FROM assets"
            ).fetchone()
        self.assertEqual(item_pdf, str(Path("catalog_pdfs") / "catalog.pdf"))
        self.assertEqual(asset_pdf, str(Path("catalog_pdfs") / "catalog.pdf"))
        self.assertEqual(asset_path, str(Path("assets") / "image.png"))

    def test_missing_database_error_includes_source_path(self) -> None:
        missing_database = self.project.path("missing", "catalog.db")

        with self.assertRaisesRegex(
            BackupError,
            str(missing_database).replace("\\", "\\\\"),
        ):
            backup_catalog(
                database_path=missing_database,
                assets_dir=self.project.path("assets"),
                catalog_pdfs_dir=self.project.path("catalog_pdfs"),
                backup_dir=self.project.path("backup"),
            )

    def test_delayed_backup_error_callback_keeps_exception_context(self) -> None:
        database = self.project.path("catalog.db")
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("CREATE TABLE sample(value TEXT)")
        callbacks: list[object] = []

        class DelayedRoot:
            @staticmethod
            def after(_delay: int, callback) -> None:
                callbacks.append(callback)

        window = SimpleNamespace(
            root=DelayedRoot(),
            state=SimpleNamespace(
                db_path=database,
                assets_dir=self.project.path("assets"),
                data_dir=self.project.path(),
            ),
            _run_bg=lambda _title, work: work(),
        )
        error = BackupError("database is locked")

        with (
            patch(
                "smartcatalog.ui.controllers.workflows_controller."
                "filedialog.askdirectory",
                return_value=str(self.project.path()),
            ),
            patch(
                "smartcatalog.ui.controllers.workflows_controller.backup_catalog",
                side_effect=error,
            ),
            patch(
                "smartcatalog.ui.controllers.workflows_controller."
                "messagebox.showerror"
            ) as show_error,
        ):
            MainWindow.on_backup_data(window)
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        self.assertIn("database is locked", show_error.call_args.args[1])

    def test_main_window_uses_extracted_workflow_controller(self) -> None:
        self.assertIs(
            MainWindow.on_backup_data,
            WorkflowsControllerMixin.on_backup_data,
        )
        self.assertIs(
            MainWindow.on_import_pdf_catalog,
            WorkflowsControllerMixin.on_import_pdf_catalog,
        )
        self.assertIs(
            MainWindow.on_import_excel_catalog,
            WorkflowsControllerMixin.on_import_excel_catalog,
        )
        self.assertIs(
            MainWindow.on_export_catalog,
            WorkflowsControllerMixin.on_export_catalog,
        )
