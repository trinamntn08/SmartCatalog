from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from smartcatalog.state import AppState


class AppStatePathTests(unittest.TestCase):
    def test_first_launch_uses_default_database_path_without_settings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            state = AppState(project_dir=Path(directory))

            self.assertEqual(
                state.db_path,
                state.data_dir / "sql" / "catalog.db",
            )
            self.assertFalse((state.data_dir / "settings.json").exists())

    def test_legacy_settings_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory)
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
                data_dir / "sql" / "catalog.db",
            )
            self.assertEqual(
                settings_path.read_text(encoding="utf-8"),
                '{"database_path": "sql/alternate.db"}',
            )

    def test_catalog_pdf_selection_is_kept_for_current_session(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory)
            source_pdf = project_dir / "source.pdf"
            source_pdf.write_bytes(b"%PDF-test")
            state = AppState(project_dir=project_dir)

            state.set_catalog_pdf(str(source_pdf))

            expected = state.data_dir / "catalog_pdfs" / "source.pdf"
            self.assertEqual(state.catalog_pdf_path, expected)
            self.assertTrue(expected.is_file())
            self.assertFalse((state.data_dir / "settings.json").exists())

    def test_new_state_returns_to_default_after_runtime_database_switch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory)
            state = AppState(project_dir=project_dir)
            state.db_path = project_dir / "another.db"

            restarted_state = AppState(project_dir=project_dir)

            self.assertEqual(
                restarted_state.db_path,
                restarted_state.data_dir / "sql" / "catalog.db",
            )


if __name__ == "__main__":
    unittest.main()
