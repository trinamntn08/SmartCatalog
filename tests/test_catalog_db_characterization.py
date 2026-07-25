from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from tests import support as _test_support  # Ensures src/ is importable.
from tests.support.fixtures import TemporaryProject
from tests.support.snapshots import snapshot_sqlite

from smartcatalog.db.catalog_db import CatalogDB


EXPECTED_ITEM_COLUMNS = {
    "id",
    "code",
    "description",
    "description_excel",
    "description_vietnames_from_excel",
    "pdf_path",
    "page",
    "validated",
    "validated_at",
    "category",
    "author",
    "dimension",
    "small_description",
    "shape",
    "blade_tip",
    "surface_treatment",
    "material",
}


class CatalogDBTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.project.__enter__()
        self.addCleanup(self.project.__exit__, None, None, None)
        self.data_dir = self.project.create_runtime_layout()
        self.db_path = self.data_dir / "sql" / "catalog.db"

    def create_db(self) -> CatalogDB:
        return CatalogDB(self.db_path, data_dir=self.data_dir)

    def create_item(self, db: CatalogDB, code: str = "A-001", **values) -> int:
        defaults = {
            "page": 3,
            "description": "Base description",
            "description_excel": "English",
            "description_vietnames_from_excel": "Tiếng Việt",
            "pdf_path": str(self.data_dir / "catalog_pdfs" / "catalog.pdf"),
        }
        defaults.update(values)
        return db.upsert_by_code(code=code, **defaults)

    def create_asset(
        self,
        db: CatalogDB,
        name: str,
        *,
        source: str = "extract",
        conn=None,
    ) -> int:
        return db.upsert_asset(
            pdf_path=str(self.data_dir / "catalog_pdfs" / "catalog.pdf"),
            page=3,
            asset_path=str(self.data_dir / "assets" / "pdf_import" / name),
            bbox=(1.0, 2.0, 30.0, 40.0),
            source=source,
            sha256=f"hash-{name}",
            conn=conn,
        )


class SchemaCharacterizationTests(CatalogDBTestCase):
    def test_fresh_schema_contains_expected_tables_columns_and_indexes(self) -> None:
        self.create_db()
        snapshot = snapshot_sqlite(self.db_path)

        self.assertEqual(
            set(snapshot["tables"]),
            {"assets", "item_asset_links", "items"},
        )
        item_columns = {
            column["name"]
            for column in snapshot["tables"]["items"]["columns"]
        }
        self.assertEqual(item_columns, EXPECTED_ITEM_COLUMNS)

        with closing(sqlite3.connect(self.db_path)) as conn:
            indexes = {
                row[1]
                for row in conn.execute("PRAGMA index_list(items)").fetchall()
            }
            self.assertIn("idx_items_code_unique", indexes)
            foreign_keys = conn.execute(
                "PRAGMA foreign_key_list(item_asset_links)"
            ).fetchall()
            self.assertEqual(
                {row[2] for row in foreign_keys},
                {"assets", "items"},
            )

    def test_existing_minimal_items_schema_is_upgraded_in_place(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        page INTEGER
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO items(code, description, page) VALUES(?, ?, ?)",
                    ("OLD-001", "Legacy", 7),
                )

        db = self.create_db()
        items = db.list_items()
        snapshot = snapshot_sqlite(self.db_path)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].code, "OLD-001")
        self.assertEqual(items[0].description, "Legacy")
        self.assertEqual(items[0].page, 7)
        self.assertEqual(
            {column["name"] for column in snapshot["tables"]["items"]["columns"]},
            EXPECTED_ITEM_COLUMNS,
        )

    def test_product_code_unique_index_rejects_duplicate_rows(self) -> None:
        db = self.create_db()
        self.create_item(db)

        with closing(db.connect()) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO items(code, description) VALUES(?, ?)",
                    ("A-001", "Duplicate"),
                )


class PathCharacterizationTests(CatalogDBTestCase):
    def test_path_mapping_preserves_current_portability_rules(self) -> None:
        db = self.create_db()
        inside = self.data_dir / "assets" / "manual_import" / "item.png"
        outside = self.project.path("external", "item.png")

        self.assertEqual(
            db.to_db_path(str(inside)),
            str(Path("assets") / "manual_import" / "item.png"),
        )
        self.assertEqual(db.from_db_path(db.to_db_path(str(inside))), str(inside))
        self.assertEqual(db.to_db_path(str(outside)), str(outside))
        self.assertEqual(db.from_db_path("assets/image.png"), str(self.data_dir / "assets" / "image.png"))
        self.assertEqual(db.to_db_path("excel:Sheet1!A2"), "excel:Sheet1!A2")
        self.assertEqual(db.from_db_path("excel:Sheet1!A2"), "excel:Sheet1!A2")
        self.assertEqual(db.to_db_path(""), "")
        self.assertEqual(db.from_db_path(""), "")

    def test_item_paths_are_stored_relative_and_returned_absolute(self) -> None:
        db = self.create_db()
        pdf_path = self.data_dir / "catalog_pdfs" / "catalog.pdf"
        self.create_item(db, pdf_path=str(pdf_path))

        with closing(db.connect()) as conn:
            stored = conn.execute(
                "SELECT pdf_path FROM items WHERE code='A-001'"
            ).fetchone()["pdf_path"]
        loaded = db.get_item_by_code("A-001")

        self.assertEqual(stored, str(Path("catalog_pdfs") / "catalog.pdf"))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.pdf_path, str(pdf_path))


class ItemCharacterizationTests(CatalogDBTestCase):
    def test_item_round_trip_maps_all_supported_fields(self) -> None:
        db = self.create_db()
        item_id = self.create_item(
            db,
            category="Category",
            author="Author",
            dimension="10 x 20",
            small_description="Small",
            shape="Round",
            blade_tip="Sharp",
            surface_treatment="Polished",
            material="Steel",
            validated=True,
            validated_at="2025-01-02 03:04:05",
        )

        item = db.get_item_by_code("A-001")

        self.assertIsNotNone(item)
        self.assertEqual(item.id, item_id)
        self.assertEqual(item.code, "A-001")
        self.assertEqual(item.page, 3)
        self.assertEqual(item.description, "Base description")
        self.assertEqual(item.description_excel, "English")
        self.assertEqual(item.description_vietnames_from_excel, "Tiếng Việt")
        self.assertEqual(item.category, "Category")
        self.assertEqual(item.author, "Author")
        self.assertEqual(item.dimension, "10 x 20")
        self.assertEqual(item.small_description, "Small")
        self.assertEqual(item.shape, "Round")
        self.assertEqual(item.blade_tip, "Sharp")
        self.assertEqual(item.surface_treatment, "Polished")
        self.assertEqual(item.material, "Steel")
        self.assertTrue(item.validated)
        self.assertEqual(item.validated_at, "2025-01-02 03:04:05")
        self.assertEqual(item.images, [])

    def test_partial_upsert_preserves_optional_descriptions_and_pdf_path(self) -> None:
        db = self.create_db()
        item_id = self.create_item(db)

        updated_id = db.upsert_by_code(
            code="A-001",
            page=4,
            description="Changed",
            description_excel=None,
            description_vietnames_from_excel=None,
            pdf_path=None,
        )
        item = db.get_item_by_code("A-001")

        self.assertEqual(updated_id, item_id)
        self.assertEqual(item.description, "Changed")
        self.assertEqual(item.description_excel, "English")
        self.assertEqual(item.description_vietnames_from_excel, "Tiếng Việt")
        self.assertTrue(item.pdf_path.endswith(str(Path("catalog_pdfs") / "catalog.pdf")))

    def test_validation_timestamp_is_preserved_or_cleared_by_current_rules(self) -> None:
        db = self.create_db()
        self.create_item(
            db,
            validated=True,
            validated_at="2025-01-02 03:04:05",
        )

        db.upsert_by_code(
            code="A-001",
            page=3,
            validated=True,
            validated_at=None,
        )
        preserved = db.get_item_by_code("A-001")
        self.assertEqual(preserved.validated_at, "2025-01-02 03:04:05")

        db.upsert_by_code(
            code="A-001",
            page=3,
            validated=False,
            validated_at=None,
        )
        cleared = db.get_item_by_code("A-001")
        self.assertFalse(cleared.validated)
        self.assertEqual(cleared.validated_at, "")

    def test_bilingual_fill_only_preserves_nonempty_values(self) -> None:
        db = self.create_db()
        self.create_item(db, description_excel="", description_vietnames_from_excel="Existing VI")

        found = db.update_excel_descriptions_by_code(
            code="A-001",
            description_vi="New VI",
            description_en="New EN",
            only_fill_empty=True,
        )
        item = db.get_item_by_code("A-001")

        self.assertTrue(found)
        self.assertEqual(item.description_vietnames_from_excel, "Existing VI")
        self.assertEqual(item.description_excel, "New EN")

        db.update_excel_descriptions_by_code(
            code="A-001",
            description_vi="Replacement VI",
            description_en="Replacement EN",
            only_fill_empty=False,
        )
        replaced = db.get_item_by_code("A-001")
        self.assertEqual(replaced.description_vietnames_from_excel, "Replacement VI")
        self.assertEqual(replaced.description_excel, "Replacement EN")


class AssetCharacterizationTests(CatalogDBTestCase):
    def test_assets_deduplicate_and_links_are_idempotent(self) -> None:
        db = self.create_db()
        item_id = self.create_item(db)
        asset_id = self.create_asset(db, "one.png")
        duplicate_id = self.create_asset(db, "one.png")

        db.link_asset_to_item(item_id=item_id, asset_id=asset_id)
        db.link_asset_to_item(item_id=item_id, asset_id=asset_id)

        self.assertEqual(duplicate_id, asset_id)
        with closing(db.connect()) as conn:
            asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            link_count = conn.execute("SELECT COUNT(*) FROM item_asset_links").fetchone()[0]
        self.assertEqual(asset_count, 1)
        self.assertEqual(link_count, 1)

    def test_primary_and_link_id_define_current_image_order(self) -> None:
        db = self.create_db()
        item_id = self.create_item(db)
        first = self.create_asset(db, "first.png")
        second = self.create_asset(db, "second.png", source="excel")
        third = self.create_asset(db, "third.png", source="add")
        for asset_id in (first, second, third):
            db.link_asset_to_item(
                item_id=item_id,
                asset_id=asset_id,
                match_method="manual",
                verified=True,
            )

        db.set_primary_asset_for_item(item_id, second)
        ordered = db.list_image_sources_for_item(item_id)

        self.assertEqual(
            [Path(path).name for path, _source in ordered],
            ["second.png", "first.png", "third.png"],
        )
        self.assertEqual([source for _path, source in ordered], ["excel", "extract", "add"])

    def test_reorder_rebuilds_links_and_preserves_metadata(self) -> None:
        db = self.create_db()
        item_id = self.create_item(db)
        first = self.create_asset(db, "first.png")
        second = self.create_asset(db, "second.png")
        db.link_asset_to_item(
            item_id=item_id,
            asset_id=first,
            match_method="keyword_nearest",
            score=0.75,
            verified=False,
            is_primary=True,
        )
        db.link_asset_to_item(
            item_id=item_id,
            asset_id=second,
            match_method="manual",
            score=None,
            verified=True,
            is_primary=False,
        )
        paths = db.list_asset_paths_for_item(item_id)

        changed = db.reorder_asset_links_for_item_by_paths(
            item_id,
            [paths[1], paths[0]],
        )
        links = db.list_asset_links_for_item(item_id)

        self.assertTrue(changed)
        # Primary status still sorts the original primary first despite rebuilt link IDs.
        self.assertEqual([int(row["asset_id"]) for row in links], [first, second])
        by_asset = {int(row["asset_id"]): row for row in links}
        self.assertEqual(by_asset[first]["match_method"], "keyword_nearest")
        self.assertEqual(by_asset[first]["score"], 0.75)
        self.assertEqual(by_asset[first]["verified"], 0)
        self.assertEqual(by_asset[first]["is_primary"], 1)
        self.assertEqual(by_asset[second]["match_method"], "manual")
        self.assertEqual(by_asset[second]["verified"], 1)

    def test_deleting_item_cascades_links_but_retains_asset(self) -> None:
        db = self.create_db()
        item_id = self.create_item(db)
        asset_id = self.create_asset(db, "one.png")
        db.link_asset_to_item(item_id=item_id, asset_id=asset_id)

        with closing(db.connect()) as conn:
            with conn:
                conn.execute("DELETE FROM items WHERE id=?", (item_id,))

        with closing(db.connect()) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM item_asset_links").fetchone()[0],
                0,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 1)


class TransactionCharacterizationTests(CatalogDBTestCase):
    def test_upsert_by_code_commits_even_with_caller_connection(self) -> None:
        db = self.create_db()
        conn = db.connect()
        try:
            db.upsert_by_code(code="COMMIT-001", page=1, conn=conn)
            conn.rollback()
        finally:
            conn.close()

        self.assertIsNotNone(db.get_item_by_code("COMMIT-001"))

    def test_upsert_asset_does_not_commit_with_caller_connection(self) -> None:
        db = self.create_db()
        conn = db.connect()
        try:
            self.create_asset(db, "rollback.png", conn=conn)
            conn.rollback()
        finally:
            conn.close()

        with closing(db.connect()) as check_conn:
            count = check_conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        self.assertEqual(count, 0)

    def test_bilingual_update_does_not_commit_with_caller_connection(self) -> None:
        db = self.create_db()
        self.create_item(db)
        conn = db.connect()
        try:
            db.update_excel_descriptions_by_code(
                code="A-001",
                description_vi="Rolled back VI",
                description_en="Rolled back EN",
                conn=conn,
            )
            conn.rollback()
        finally:
            conn.close()

        item = db.get_item_by_code("A-001")
        self.assertEqual(item.description_vietnames_from_excel, "Tiếng Việt")
        self.assertEqual(item.description_excel, "English")


if __name__ == "__main__":
    unittest.main()
