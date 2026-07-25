from __future__ import annotations

import sqlite3
import datetime
from typing import Callable

from smartcatalog.domain.models import CatalogItem

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def get_item_columns(conn: sqlite3.Connection) -> set[str]:
    columns = set()
    for row in conn.execute("PRAGMA table_info(items)").fetchall():
        columns.add(row[1] if not isinstance(row, dict) else row["name"])
    return columns


def list_item_rows(
    conn: sqlite3.Connection,
) -> tuple[list[str], list[sqlite3.Row]]:
    columns = get_item_columns(conn)
    selected = ["id", "code", "description", "page"]
    for optional in [
        "category",
        "author",
        "dimension",
        "small_description",
        "shape",
        "blade_tip",
        "surface_treatment",
        "material",
        "images",
        "description_excel",
        "pdf_path",
        "validated",
        "validated_at",
    ]:
        if optional in columns:
            selected.append(optional)
    if "description_vietnames_from_excel" in columns:
        selected.append("description_vietnames_from_excel")
    rows = conn.execute(
        f"SELECT {', '.join(selected)} FROM items ORDER BY id"
    ).fetchall()
    return selected, rows


def get_item_row_by_code(
    conn: sqlite3.Connection,
    *,
    code: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, code, description, page,
               description_excel, pdf_path, category, author, dimension, small_description,
               shape, blade_tip, surface_treatment, material,
               description_vietnames_from_excel, validated, validated_at
        FROM items
        WHERE code=?
        """,
        (code,),
    ).fetchone()


def map_catalog_item(
    get_value: Callable[[str, object], object],
    *,
    images: list[str],
    resolve_path: Callable[[str], str],
) -> CatalogItem:
    page = get_value("page", None)
    return CatalogItem(
        id=int(get_value("id", 0)),
        code=str(get_value("code", "") or ""),
        description=str(get_value("description", "") or ""),
        description_excel=str(get_value("description_excel", "") or ""),
        description_vietnames_from_excel=str(
            get_value("description_vietnames_from_excel", "") or ""
        ),
        pdf_path=resolve_path(str(get_value("pdf_path", "") or "")),
        page=(int(page) if page not in (None, "") else None),
        images=images,
        validated=bool(int(get_value("validated", 0) or 0)),
        validated_at=str(get_value("validated_at", "") or ""),
        category=str(get_value("category", "") or ""),
        author=str(get_value("author", "") or ""),
        dimension=str(get_value("dimension", "") or ""),
        small_description=str(get_value("small_description", "") or ""),
        shape=str(get_value("shape", "") or ""),
        blade_tip=str(get_value("blade_tip", "") or ""),
        surface_treatment=str(get_value("surface_treatment", "") or ""),
        material=str(get_value("material", "") or ""),
    )


def update_description_by_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    description: str,
) -> bool:
    cursor = conn.execute(
        "UPDATE items SET description_excel=? WHERE code=?",
        (description, code),
    )
    return cursor.rowcount > 0


def update_excel_descriptions_by_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    description_vi: str,
    description_en: str,
    only_fill_empty: bool,
) -> bool:
    if only_fill_empty:
        cursor = conn.execute(
            """
            UPDATE items
            SET description_vietnames_from_excel =
                    CASE
                        WHEN TRIM(COALESCE(description_vietnames_from_excel, '')) = ''
                        THEN ?
                        ELSE description_vietnames_from_excel
                    END,
                description_excel =
                    CASE
                        WHEN TRIM(COALESCE(description_excel, '')) = ''
                        THEN ?
                        ELSE description_excel
                    END
            WHERE code=?
            """,
            (description_vi, description_en, code),
        )
    else:
        cursor = conn.execute(
            """
            UPDATE items
            SET description_vietnames_from_excel=?,
                description_excel=?
            WHERE code=?
            """,
            (description_vi, description_en, code),
        )
    return bool(cursor.rowcount)


def upsert_by_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    page: int | None,
    category: str,
    author: str,
    dimension: str,
    small_description: str,
    shape: str,
    blade_tip: str,
    surface_treatment: str,
    material: str,
    validated: bool,
    validated_at: str | None,
    description: str,
    description_excel: str | None,
    description_vietnames_from_excel: str | None,
    pdf_path: str | None,
    store_path: Callable[[str], str],
) -> int:
    row = conn.execute(
        "SELECT id, description_excel, description_vietnames_from_excel, pdf_path, validated, validated_at FROM items WHERE code=?",
        (code,),
    ).fetchone()

    existing_validated = bool(int(row["validated"] or 0)) if row else False
    existing_validated_at = str((row["validated_at"] if row else "") or "")
    if validated_at is not None:
        validated_at_value = str(validated_at or "").strip()
    elif not validated:
        validated_at_value = ""
    elif existing_validated and existing_validated_at:
        validated_at_value = existing_validated_at
    else:
        validated_at_value = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if row:
        item_id = int(row["id"])
        if description_excel is None:
            description_excel = str(row["description_excel"] or "")
        if description_vietnames_from_excel is None:
            description_vietnames_from_excel = str(
                row["description_vietnames_from_excel"] or ""
            )
        if pdf_path is None:
            pdf_path = str(row["pdf_path"] or "")
        conn.execute(
            """
            UPDATE items
            SET description=?,
                description_excel=?,
                description_vietnames_from_excel=?,
                pdf_path=?,
                page=?,
                category=?,
                author=?,
                dimension=?,
                small_description=?,
                shape=?,
                blade_tip=?,
                surface_treatment=?,
                material=?,
                validated=?,
                validated_at=?
            WHERE id=?
            """,
            (
                description,
                description_excel,
                description_vietnames_from_excel,
                store_path(str(pdf_path or "")),
                page,
                category,
                author,
                dimension,
                small_description,
                shape,
                blade_tip,
                surface_treatment,
                material,
                1 if validated else 0,
                validated_at_value,
                item_id,
            ),
        )
        return item_id

    cursor = conn.execute(
        """
        INSERT INTO items(
            code,
            description,
            description_excel,
            description_vietnames_from_excel,
            pdf_path,
            page,
            validated,
            validated_at,
            category,
            author,
            dimension,
            small_description,
            shape,
            blade_tip,
            surface_treatment,
            material
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            code,
            description,
            "" if description_excel is None else description_excel,
            (
                ""
                if description_vietnames_from_excel is None
                else description_vietnames_from_excel
            ),
            store_path(str(pdf_path or "")),
            page,
            1 if validated else 0,
            validated_at_value,
            category,
            author,
            dimension,
            small_description,
            shape,
            blade_tip,
            surface_treatment,
            material,
        ),
    )
    return int(cursor.lastrowid)
