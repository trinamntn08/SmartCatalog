from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.state import AppState


class AppStateSettingsTests(unittest.TestCase):
    def test_first_launch_writes_default_database_path_to_settings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            state = AppState(project_dir=Path(directory))

            self.assertEqual(
                state.db_path,
                state.data_dir / "sql" / "catalog.db",
            )
            settings = json.loads(state.settings_path.read_text(encoding="utf-8"))
            self.assertEqual(
                settings["database_path"],
                str(Path("sql") / "catalog.db"),
            )

    def test_database_path_is_loaded_from_settings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory).resolve()
            data_dir = project_dir / "config" / "database"
            data_dir.mkdir(parents=True)
            settings_path = data_dir / "settings.json"
            settings_path.write_text(
                '{"database_path": "sql/alternate.db"}',
                encoding="utf-8",
            )

            state = AppState(project_dir=project_dir)

            self.assertEqual(
                state.db_path,
                (data_dir / "sql" / "alternate.db").resolve(),
            )

    def test_catalog_pdf_selection_is_restored_after_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory).resolve()
            source_pdf = project_dir / "source.pdf"
            source_pdf.write_bytes(b"%PDF-test")
            state = AppState(project_dir=project_dir)

            state.set_catalog_pdf(str(source_pdf))

            expected = state.data_dir / "catalog_pdfs" / "source.pdf"
            self.assertEqual(state.catalog_pdf_path, expected)
            self.assertTrue(expected.is_file())
            restarted_state = AppState(project_dir=project_dir)
            self.assertEqual(restarted_state.catalog_pdf_path, expected)

    def test_selected_backup_database_is_restored_after_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory).resolve()
            backup_database = project_dir / "backups" / "catalog.db"
            backup_database.parent.mkdir(parents=True)
            backup_db = CatalogDB(backup_database, data_dir=backup_database.parent)
            backup_db.upsert_by_code(code="RESTORED-001", page=1)
            backup_database = backup_database.resolve()
            state = AppState(project_dir=project_dir)
            state.set_database_path(backup_database)

            restarted_state = AppState(project_dir=project_dir)
            restarted_db = CatalogDB(
                restarted_state.db_path,
                data_dir=restarted_state.data_dir,
            )

            self.assertEqual(restarted_state.db_path, backup_database)
            self.assertEqual(restarted_state.data_dir, backup_database.parent)
            self.assertEqual(
                restarted_state.assets_dir,
                backup_database.parent / "assets",
            )
            self.assertIsNotNone(restarted_db.get_item_by_code("RESTORED-001"))
            settings = json.loads(
                restarted_state.settings_path.read_text(encoding="utf-8")
            )
            self.assertEqual(settings["database_path"], str(backup_database))


if __name__ == "__main__":
    unittest.main()
