from __future__ import annotations

import sqlite3
from typing import Callable


def list_linked_asset_paths_by_item(
    conn: sqlite3.Connection,
) -> dict[int, list[str]]:
    rows = conn.execute(
        """
        SELECT l.item_id AS item_id, a.asset_path AS asset_path
        FROM item_asset_links l
        JOIN assets a ON a.id = l.asset_id
        ORDER BY l.item_id ASC, l.is_primary DESC, l.id ASC
        """
    ).fetchall()

    paths_by_item: dict[int, list[str]] = {}
    for row in rows:
        item_id = int(row["item_id"])
        paths_by_item.setdefault(item_id, []).append(str(row["asset_path"]))
    return paths_by_item


def list_assets_for_page(
    conn: sqlite3.Connection,
    *,
    pdf_path: str,
    page: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, pdf_path, page, asset_path, x0, y0, x1, y1, source, sha256, created_at
        FROM assets
        WHERE pdf_path=? AND page=?
        ORDER BY id ASC
        """,
        (pdf_path, int(page)),
    ).fetchall()


def list_asset_paths_for_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    resolve_path: Callable[[str], str],
) -> list[str]:
    rows = conn.execute(
        """
        SELECT a.asset_path
        FROM item_asset_links l
        JOIN assets a ON a.id = l.asset_id
        WHERE l.item_id=?
        ORDER BY l.is_primary DESC, l.id ASC
        """,
        (int(item_id),),
    ).fetchall()
    return [resolve_path(str(row["asset_path"])) for row in rows]


def list_image_sources_for_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    resolve_path: Callable[[str], str],
) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT a.asset_path AS asset_path, a.source AS source
        FROM item_asset_links l
        JOIN assets a ON a.id = l.asset_id
        WHERE l.item_id=?
        ORDER BY l.is_primary DESC, l.id ASC
        """,
        (int(item_id),),
    ).fetchall()
    return [
        (resolve_path(str(row["asset_path"])), str(row["source"] or ""))
        for row in rows
    ]


def list_asset_links_for_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT asset_id, is_primary, verified, match_method, score
        FROM item_asset_links
        WHERE item_id=?
        ORDER BY is_primary DESC, id ASC
        """,
        (item_id,),
    ).fetchall()


def link_asset_to_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    asset_id: int,
    match_method: str,
    score: float | None,
    verified: bool,
    is_primary: bool,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO item_asset_links(item_id, asset_id, match_method, score, verified, is_primary)
        VALUES(?,?,?,?,?,?)
        """,
        (
            int(item_id),
            int(asset_id),
            match_method,
            score,
            1 if verified else 0,
            1 if is_primary else 0,
        ),
    )


def unlink_asset_from_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    asset_id: int,
) -> None:
    conn.execute(
        "DELETE FROM item_asset_links WHERE item_id=? AND asset_id=?",
        (int(item_id), int(asset_id)),
    )


def clear_asset_links_for_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
) -> None:
    conn.execute("DELETE FROM item_asset_links WHERE item_id=?", (item_id,))


def set_primary_asset_for_item(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    asset_id: int,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO item_asset_links(item_id, asset_id, match_method, score, verified, is_primary)
        VALUES(?, ?, 'manual', NULL, 1, 0)
        """,
        (item_id, asset_id),
    )
    conn.execute("UPDATE item_asset_links SET is_primary=0 WHERE item_id=?", (item_id,))
    conn.execute(
        "UPDATE item_asset_links SET is_primary=1 WHERE item_id=? AND asset_id=?",
        (item_id, asset_id),
    )


def upsert_asset(
    conn: sqlite3.Connection,
    *,
    pdf_path: str,
    page: int,
    asset_path: str,
    bbox: tuple[float, float, float, float] | None,
    source: str,
    sha256: str,
) -> int:
    row = conn.execute(
        "SELECT id FROM assets WHERE pdf_path=? AND page=? AND asset_path=?",
        (pdf_path, int(page), asset_path),
    ).fetchone()
    if row:
        return int(row["id"])

    x0 = y0 = x1 = y1 = None
    if bbox is not None:
        x0, y0, x1, y1 = bbox
    cursor = conn.execute(
        """
        INSERT INTO assets(pdf_path, page, asset_path, x0, y0, x1, y1, source, sha256)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (pdf_path, int(page), asset_path, x0, y0, x1, y1, source, sha256),
    )
    return int(cursor.lastrowid)


def reorder_asset_links_for_item_by_paths(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    ordered_paths: list[str],
    resolve_path: Callable[[str], str],
) -> bool:
    rows = conn.execute(
        """
        SELECT l.asset_id, l.match_method, l.score, l.verified, l.is_primary, a.asset_path
        FROM item_asset_links l
        JOIN assets a ON a.id = l.asset_id
        WHERE l.item_id=?
        ORDER BY l.is_primary DESC, l.id ASC
        """,
        (int(item_id),),
    ).fetchall()
    if not rows:
        return False

    buckets: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        key = str(resolve_path(str(row["asset_path"] or "")))
        buckets.setdefault(key, []).append(row)

    ordered_rows: list[sqlite3.Row] = []
    used_asset_ids: set[int] = set()
    for path in ordered_paths or []:
        queue = buckets.get(str(path or ""))
        if queue:
            picked = queue.pop(0)
            asset_id = int(picked["asset_id"])
            if asset_id not in used_asset_ids:
                used_asset_ids.add(asset_id)
                ordered_rows.append(picked)

    for row in rows:
        asset_id = int(row["asset_id"])
        if asset_id not in used_asset_ids:
            used_asset_ids.add(asset_id)
            ordered_rows.append(row)
    if not ordered_rows:
        return False

    conn.execute("DELETE FROM item_asset_links WHERE item_id=?", (int(item_id),))
    for row in ordered_rows:
        conn.execute(
            """
            INSERT INTO item_asset_links(item_id, asset_id, match_method, score, verified, is_primary)
            VALUES(?,?,?,?,?,?)
            """,
            (
                int(item_id),
                int(row["asset_id"]),
                str(row["match_method"] or "manual"),
                row["score"],
                int(row["verified"] or 0),
                int(row["is_primary"] or 0),
            ),
        )
    return True
