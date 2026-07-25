from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.state import AppState


class AppStateSettingsTests(unittest.TestCase):
    def test_first_launch_writes_default_database_path_to_settings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            state = AppState(project_dir=Path(directory))

            settings = json.loads(state.settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["database_path"], str(Path("sql") / "catalog.db"))
            self.assertEqual(
                state.db_path,
                state.data_dir / "sql" / "catalog.db",
            )

    def test_database_path_is_loaded_from_settings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory)
            data_dir = project_dir / "config" / "database"
            data_dir.mkdir(parents=True)
            (data_dir / "settings.json").write_text(
                json.dumps(
                    {
                        "database_path": str(Path("sql") / "alternate.db"),
                        "catalog_pdf_path": "",
                    }
                ),
                encoding="utf-8",
            )

            state = AppState(project_dir=project_dir)

            self.assertEqual(
                state.db_path,
                data_dir / "sql" / "alternate.db",
            )

    def test_legacy_settings_are_upgraded_without_losing_pdf_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            project_dir = Path(directory)
            data_dir = project_dir / "config" / "database"
            pdf_path = data_dir / "catalog_pdfs" / "catalog.pdf"
            pdf_path.parent.mkdir(parents=True)
            pdf_path.touch()
            settings_path = data_dir / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {"catalog_pdf_path": str(Path("catalog_pdfs") / "catalog.pdf")}
                ),
                encoding="utf-8",
            )

            state = AppState(project_dir=project_dir)

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["database_path"], str(Path("sql") / "catalog.db"))
            self.assertEqual(
                settings["catalog_pdf_path"],
                str(Path("catalog_pdfs") / "catalog.pdf"),
            )
            self.assertEqual(state.catalog_pdf_path, pdf_path)

    def test_complete_data_bundle_reopens_from_settings_after_move(self) -> None:
        with tempfile.TemporaryDirectory(prefix="smartcatalog-state-") as directory:
            root = Path(directory)
            source_project = root / "source"
            source_data = source_project / "config" / "database"
            source_data.mkdir(parents=True)
            (source_data / "settings.json").write_text(
                json.dumps(
                    {
                        "database_path": str(Path("sql") / "portable.db"),
                        "catalog_pdf_path": "",
                    }
                ),
                encoding="utf-8",
            )

            source_state = AppState(project_dir=source_project)
            source_db = CatalogDB(
                source_state.db_path,
                data_dir=source_state.data_dir,
            )
            source_pdf = source_state.data_dir / "catalog_pdfs" / "catalog.pdf"
            source_pdf.touch()
            source_image = (
                source_state.assets_dir / "manual_import" / "product.png"
            )
            source_image.touch()
            item_id = source_db.upsert_by_code(
                code="PORTABLE-001",
                page=1,
                pdf_path=str(source_pdf),
            )
            asset_id = source_db.upsert_asset(
                pdf_path=str(source_pdf),
                page=1,
                asset_path=str(source_image),
                source="add",
            )
            source_db.link_asset_to_item(
                item_id=item_id,
                asset_id=asset_id,
                is_primary=True,
            )

            destination_project = root / "destination"
            destination_data = destination_project / "config" / "database"
            shutil.copytree(source_state.data_dir, destination_data)

            destination_state = AppState(project_dir=destination_project)
            destination_db = CatalogDB(
                destination_state.db_path,
                data_dir=destination_state.data_dir,
            )
            item = destination_db.get_item_by_code("PORTABLE-001")

            self.assertEqual(
                destination_state.db_path,
                destination_data / "sql" / "portable.db",
            )
            self.assertIsNotNone(item)
            assert item is not None
            self.assertEqual(
                item.pdf_path,
                str(destination_data / "catalog_pdfs" / "catalog.pdf"),
            )
            self.assertEqual(
                item.images,
                [str(destination_data / "assets" / "manual_import" / "product.png")],
            )


if __name__ == "__main__":
    unittest.main()
