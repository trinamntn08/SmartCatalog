from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  description_excel TEXT NOT NULL DEFAULT '',
  description_vietnames_from_excel TEXT NOT NULL DEFAULT '',
  pdf_path TEXT NOT NULL DEFAULT '',
  page INTEGER,
  validated INTEGER NOT NULL DEFAULT 0,
  validated_at TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  dimension TEXT NOT NULL DEFAULT '',
  small_description TEXT NOT NULL DEFAULT '',
  shape TEXT NOT NULL DEFAULT '',
  blade_tip TEXT NOT NULL DEFAULT '',
  surface_treatment TEXT NOT NULL DEFAULT '',
  material TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_items_code_unique ON items(code);

CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pdf_path TEXT NOT NULL,
  page INTEGER NOT NULL,
  asset_path TEXT NOT NULL,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL,
  source TEXT NOT NULL DEFAULT 'extract',
  sha256 TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assets_pdf_page ON assets(pdf_path, page);
CREATE INDEX IF NOT EXISTS idx_assets_asset_path ON assets(asset_path);

CREATE TABLE IF NOT EXISTS item_asset_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  asset_id INTEGER NOT NULL,
  match_method TEXT NOT NULL DEFAULT 'heuristic',
  score REAL,
  verified INTEGER NOT NULL DEFAULT 0,
  is_primary INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_item_asset_unique ON item_asset_links(item_id, asset_id);
CREATE INDEX IF NOT EXISTS idx_item_asset_item ON item_asset_links(item_id);
CREATE INDEX IF NOT EXISTS idx_item_asset_asset ON item_asset_links(asset_id);
"""


ITEM_COMPATIBILITY_COLUMNS = {
    "category": "TEXT NOT NULL DEFAULT ''",
    "author": "TEXT NOT NULL DEFAULT ''",
    "dimension": "TEXT NOT NULL DEFAULT ''",
    "small_description": "TEXT NOT NULL DEFAULT ''",
    "shape": "TEXT NOT NULL DEFAULT ''",
    "blade_tip": "TEXT NOT NULL DEFAULT ''",
    "surface_treatment": "TEXT NOT NULL DEFAULT ''",
    "material": "TEXT NOT NULL DEFAULT ''",
    "description_excel": "TEXT NOT NULL DEFAULT ''",
    "description_vietnames_from_excel": "TEXT NOT NULL DEFAULT ''",
    "pdf_path": "TEXT NOT NULL DEFAULT ''",
    "validated": "INTEGER NOT NULL DEFAULT 0",
    "validated_at": "TEXT NOT NULL DEFAULT ''",
}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def ensure_compatibility_columns(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    for column, ddl in ITEM_COMPATIBILITY_COLUMNS.items():
        try:
            cursor.execute(f"ALTER TABLE items ADD COLUMN {column} {ddl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
