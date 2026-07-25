from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from smartcatalog.db.asset_repository import list_linked_asset_paths_by_item
from smartcatalog.db.catalog_db import CatalogDB, SCHEMA_SQL
from smartcatalog.db.item_repository import get_item_columns, table_exists
from smartcatalog.db.path_mapper import DatabasePathMapper
from smartcatalog.db.schema import ensure_compatibility_columns, ensure_schema


class SchemaBoundaryTests(unittest.TestCase):
    def test_catalog_db_reexports_the_existing_schema_constant(self):
        from smartcatalog.db.schema import SCHEMA_SQL as extracted_schema

        self.assertIs(SCHEMA_SQL, extracted_schema)

    def test_schema_helpers_create_and_upgrade_the_current_schema(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            ensure_schema(connection)
            ensure_compatibility_columns(connection)

            self.assertTrue(table_exists(connection, "items"))
            self.assertTrue(table_exists(connection, "assets"))
            self.assertTrue(table_exists(connection, "item_asset_links"))
            self.assertIn("description_vietnames_from_excel", get_item_columns(connection))
        finally:
            connection.close()


class PathMapperBoundaryTests(unittest.TestCase):
    def test_catalog_facade_and_extracted_mapper_are_equivalent(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            data_dir.mkdir()
            database = CatalogDB(Path(directory) / "catalog.db", data_dir=data_dir)
            mapper = DatabasePathMapper(data_dir)
            values = [
                "",
                "excel:Sheet1",
                "assets/image.png",
                str(data_dir / "assets" / "image.png"),
                str(Path(directory) / "outside.png"),
            ]

            for value in values:
                self.assertEqual(database.to_db_path(value), mapper.to_db_path(value))
                self.assertEqual(database.from_db_path(value), mapper.from_db_path(value))


class RepositoryBoundaryTests(unittest.TestCase):
    def test_linked_asset_map_preserves_primary_then_link_id_order(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            ensure_schema(connection)
            item_id = connection.execute(
                "INSERT INTO items(code) VALUES('10-100-10')"
            ).lastrowid
            first = connection.execute(
                "INSERT INTO assets(pdf_path, page, asset_path) VALUES('', 1, 'first.png')"
            ).lastrowid
            primary = connection.execute(
                "INSERT INTO assets(pdf_path, page, asset_path) VALUES('', 1, 'primary.png')"
            ).lastrowid
            connection.execute(
                "INSERT INTO item_asset_links(item_id, asset_id, is_primary) VALUES(?,?,0)",
                (item_id, first),
            )
            connection.execute(
                "INSERT INTO item_asset_links(item_id, asset_id, is_primary) VALUES(?,?,1)",
                (item_id, primary),
            )

            self.assertEqual(
                list_linked_asset_paths_by_item(connection),
                {item_id: ["primary.png", "first.png"]},
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
