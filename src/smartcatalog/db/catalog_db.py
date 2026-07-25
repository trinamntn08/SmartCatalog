# smartcatalog/db/catalog_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple

from smartcatalog.domain.models import CatalogItem
from smartcatalog.db.path_mapper import DatabasePathMapper
from smartcatalog.db.asset_repository import (
    clear_asset_links_for_item as repository_clear_asset_links_for_item,
    link_asset_to_item as repository_link_asset_to_item,
    list_asset_links_for_item as repository_list_asset_links_for_item,
    list_asset_paths_for_item as repository_list_asset_paths_for_item,
    list_assets_for_page as repository_list_assets_for_page,
    list_image_sources_for_item as repository_list_image_sources_for_item,
    list_linked_asset_paths_by_item,
    reorder_asset_links_for_item_by_paths as repository_reorder_asset_links,
    set_primary_asset_for_item as repository_set_primary_asset_for_item,
    unlink_asset_from_item as repository_unlink_asset_from_item,
    upsert_asset as repository_upsert_asset,
)
from smartcatalog.db.item_repository import (
    get_item_columns,
    get_item_row_by_code,
    list_item_rows,
    map_catalog_item,
    table_exists,
    upsert_by_code as repository_upsert_by_code,
    update_description_by_code as repository_update_description,
    update_excel_descriptions_by_code as repository_update_excel_descriptions,
)
from smartcatalog.db.schema import (
    SCHEMA_SQL,
    ensure_compatibility_columns,
    ensure_schema,
)


class CatalogDB:
    """
    Thread-safe DB wrapper:
    - DO NOT store a shared sqlite connection on self.
    - Each thread should use its own connection (connect()).
    """

    def __init__(self, db_path: str | Path, data_dir: Optional[str | Path] = None):
        self.db_path = str(db_path)
        self._path_mapper = DatabasePathMapper(data_dir)
        self.data_dir = self._path_mapper.data_dir

        conn = self.connect()
        try:
            self._ensure_schema(conn)
            self._ensure_columns(conn)  # migration safety for old DBs
        finally:
            conn.close()

    # -------------------------
    # Path normalization (portability)
    # -------------------------

    def to_db_path(self, p: str) -> str:
        """
        Convert an absolute path under data_dir to a relative path.
        Leave non-path tokens like 'excel:...' untouched.
        """
        return self._path_mapper.to_db_path(p)

    def from_db_path(self, p: str) -> str:
        """
        Resolve a relative DB path to an absolute path under data_dir.
        """
        return self._path_mapper.from_db_path(p)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        ensure_schema(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """
        If DB existed before we added new columns, add them safely.
        (Tables/assets/links are created with IF NOT EXISTS already.)
        """
        ensure_compatibility_columns(conn)

    # ==========================================================================================
    # Read
    # ==========================================================================================

    def _table_exists(self, conn, name: str) -> bool:
        return table_exists(conn, name)

    def _get_item_columns(self, conn) -> set[str]:
        return get_item_columns(conn)

    def list_items(self):
        """
        Return List[CatalogItem] with ALL fields the UI expects.

        Images priority:
        1) assets linked to item (item_asset_links JOIN assets)
        2) fallback items.images (json or ';' separated) if that column exists
        """
        import json

        conn = self.connect()
        try:
            select_cols, rows = list_item_rows(conn)

            has_assets = self._table_exists(conn, "assets")
            has_links = self._table_exists(conn, "item_asset_links")

            # ------------------------------------------------------------
            # Build images maps in BULK (avoid N+1 queries)
            # ------------------------------------------------------------
            linked_assets_map: dict[int, list[str]] = {}
            if has_assets and has_links:
                linked_assets_map = list_linked_asset_paths_by_item(conn)

            # ------------------------------------------------------------
            # Build CatalogItem list
            # ------------------------------------------------------------
            items: list[CatalogItem] = []

            for r in rows:
                # sqlite row can be tuple or Row/dict depending on your connect()
                def get(k, default=None):
                    try:
                        return r[k]
                    except Exception:
                        idx = select_cols.index(k)
                        return r[idx] if idx < len(r) else default

                item_id = int(get("id"))

                # images: links -> items.images fallback
                images: list[str] = []
                if item_id in linked_assets_map:
                    images = [self.from_db_path(p) for p in linked_assets_map[item_id]]
                else:
                    # fallback: items.images (json list or ';' separated)
                    if "images" in select_cols:
                        raw = get("images", "") or ""
                        if isinstance(raw, (list, tuple)):
                            images = [self.from_db_path(p) for p in list(raw)]
                        else:
                            s = str(raw).strip()
                            if s.startswith("["):
                                try:
                                    images = [self.from_db_path(p) for p in list(json.loads(s))]
                                except Exception:
                                    images = []
                            elif s:
                                images = [self.from_db_path(p) for p in s.split(";") if p.strip()]

                items.append(
                    map_catalog_item(
                        get,
                        images=images,
                        resolve_path=self.from_db_path,
                    )
                )

            return items

        finally:
            conn.close()

    def get_item_by_code(self, code: str, conn: Optional[sqlite3.Connection] = None) -> Optional[CatalogItem]:
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            r = get_item_row_by_code(conn, code=code)
            if not r:
                return None

            item_id = int(r["id"])

            images = self.list_asset_paths_for_item(item_id, conn=conn)

            return map_catalog_item(
                lambda key, default=None: r[key] if key in r.keys() else default,
                images=images,
                resolve_path=self.from_db_path,
            )
        finally:
            if owns:
                conn.close()

    # ==========================================================================================
    # New: Assets + Links (foundation for manual assignment later)
    # ==========================================================================================

    def upsert_asset(
        self,
        *,
        pdf_path: str,
        page: int,
        asset_path: str,
        bbox: Tuple[float, float, float, float] | None = None,
        source: str = "extract",
        sha256: str = "",
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """
        Insert asset if not exists. Dedup key = (pdf_path, page, asset_path).
        Returns asset_id.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            pdf_db = self.to_db_path(pdf_path)
            asset_db = self.to_db_path(asset_path)
            asset_id = repository_upsert_asset(
                conn,
                pdf_path=pdf_db,
                page=page,
                asset_path=asset_db,
                bbox=bbox,
                source=source,
                sha256=sha256,
            )
            if owns:
                conn.commit()
            return asset_id
        finally:
            if owns:
                conn.close()

    def list_assets_for_page(
        self,
        *,
        pdf_path: str,
        page: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[sqlite3.Row]:
        """
        Returns asset rows for a page (candidates list).
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            return repository_list_assets_for_page(
                conn,
                pdf_path=self.to_db_path(pdf_path),
                page=page,
            )
        finally:
            if owns:
                conn.close()

    def link_asset_to_item(
        self,
        *,
        item_id: int,
        asset_id: int,
        match_method: str = "heuristic",
        score: float | None = None,
        verified: bool = False,
        is_primary: bool = False,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """
        Create link (idempotent). Can later be called from UI (manual assign).
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            repository_link_asset_to_item(
                conn,
                item_id=item_id,
                asset_id=asset_id,
                match_method=match_method,
                score=score,
                verified=verified,
                is_primary=is_primary,
            )
            if owns:
                conn.commit()
        finally:
            if owns:
                conn.close()

    def unlink_asset_from_item(
        self,
        *,
        item_id: int,
        asset_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            repository_unlink_asset_from_item(
                conn,
                item_id=item_id,
                asset_id=asset_id,
            )
            conn.commit()
        finally:
            if owns:
                conn.close()

    def list_asset_paths_for_item(
        self,
        item_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[str]:
        """
        New preferred image list: assets linked to item.
        Ordered by primary first then link order.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            return repository_list_asset_paths_for_item(
                conn,
                item_id=item_id,
                resolve_path=self.from_db_path,
            )
        finally:
            if owns:
                conn.close()

    def list_image_sources_for_item(
        self,
        item_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[tuple[str, str]]:
        """
        Returns list of (path, source) for the item, ordered like the UI.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            return repository_list_image_sources_for_item(
                conn,
                item_id=item_id,
                resolve_path=self.from_db_path,
            )
        finally:
            if owns:
                conn.close()

    # ---------- Asset links (new) ----------
    def list_asset_links_for_item(self, item_id: int, conn: Optional[sqlite3.Connection] = None) -> List[sqlite3.Row]:
        """
        Returns rows of (asset_id, is_primary, verified, match_method, score).
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            return repository_list_asset_links_for_item(
                conn,
                item_id=item_id,
            )
        finally:
            if owns:
                conn.close()

    def clear_asset_links_for_item(self, item_id: int, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Remove all asset links for an item (manual reset).
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            repository_clear_asset_links_for_item(conn, item_id=item_id)
            if owns:
                conn.commit()
        finally:
            if owns:
                conn.close()

    def set_primary_asset_for_item(self, item_id: int, asset_id: int, conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Mark exactly one linked asset as primary.
        Safe even if multiple exist; we set all to 0 then set this one to 1.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            repository_set_primary_asset_for_item(
                conn,
                item_id=item_id,
                asset_id=asset_id,
            )
            conn.commit()
        finally:
            if owns:
                conn.close()

    def reorder_asset_links_for_item_by_paths(
        self,
        item_id: int,
        ordered_paths: List[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """
        Reorder item_asset_links for an item to match ordered_paths.
        Keeps link metadata (match_method, score, verified, is_primary).
        Returns True when reorder was applied, False when no links exist.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            reordered = repository_reorder_asset_links(
                conn,
                item_id=item_id,
                ordered_paths=ordered_paths,
                resolve_path=self.from_db_path,
            )
            if not reordered:
                return False
            conn.commit()
            return True
        finally:
            if owns:
                conn.close()


    # ==========================================================================================
    # Write (existing, kept)
    # ==========================================================================================

    def upsert_by_code(
        self,
        *,
        code: str,
        page: Optional[int],
        category: str = "",
        author: str = "",
        dimension: str = "",
        small_description: str = "",
        shape: str = "",
        blade_tip: str = "",
        surface_treatment: str = "",
        material: str = "",
        validated: bool = False,
        validated_at: Optional[str] = None,
        description: str = "",
        description_excel: Optional[str] = None,
        description_vietnames_from_excel: Optional[str] = None,
        pdf_path: Optional[str] = None,
        image_paths: List[str] | None = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """
        Insert/update items by code.
        Returns item_id.
        """
        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            item_id = repository_upsert_by_code(
                conn,
                code=code,
                page=page,
                category=category,
                author=author,
                dimension=dimension,
                small_description=small_description,
                shape=shape,
                blade_tip=blade_tip,
                surface_treatment=surface_treatment,
                material=material,
                validated=validated,
                validated_at=validated_at,
                description=description,
                description_excel=description_excel,
                description_vietnames_from_excel=description_vietnames_from_excel,
                pdf_path=pdf_path,
                store_path=self.to_db_path,
            )
            conn.commit()
            return item_id
        finally:
            if owns:
                conn.close()

    def insert_asset(
        self,
        *,
        file_path: str,
        page: int,
        xref: int | None = None,
        width: int | None = None,
        height: int | None = None,
        source: str = "page_extract",
        pdf_path: str | None = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """
        Compatibility method used by CandidatesControllerMixin.

        assets schema:
          assets(pdf_path, page, asset_path, x0,y0,x1,y1, source, sha256, created_at)

        We store:
          - pdf_path: MUST be stable. Caller (UI) should pass state.catalog_pdf_path.
          - page: 1-based page
          - asset_path: file_path
          - source: 'extract' | 'manual_crop' | 'page_extract'

        xref/width/height currently ignored (not in schema). Kept for API compatibility.
        Returns asset_id.
        """
        if not file_path:
            raise ValueError("insert_asset: file_path is empty")

        # IMPORTANT: DB layer has no AppState; caller should pass pdf_path.
        pdf_path_str = str(pdf_path or "").strip()

        return self.upsert_asset(
            pdf_path=pdf_path_str,
            page=int(page),
            asset_path=str(file_path),
            bbox=None,
            source=str(source or "extract"),
            sha256="",
            conn=conn,
        )


    # ==========================================================================================
    # Write: update description from Excel
    # ==========================================================================================

    def update_description_by_code(
        self,
        *,
        code: str,
        description: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """
        Update items.description_excel for a given code.
        Returns True if something was updated, False if code not found.
        """
        code = (code or "").strip()
        description = (description or "").strip()
        if not code:
            return False

        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            updated = repository_update_description(
                conn,
                code=code,
                description=description,
            )
            conn.commit()
            return updated
        finally:
            if owns:
                conn.close()

    def update_excel_descriptions_by_code(
        self,
        *,
        code: str,
        description_vi: str,
        description_en: str,
        only_fill_empty: bool = False,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """
        Update the bilingual Excel descriptions for one product code.

        When only_fill_empty is True, existing non-empty descriptions are kept.
        Returns True when the item exists.
        """
        code = str(code or "").strip()
        if not code:
            return False

        owns = conn is None
        if conn is None:
            conn = self.connect()
            self._ensure_schema(conn)
            self._ensure_columns(conn)

        try:
            updated = repository_update_excel_descriptions(
                conn,
                code=code,
                description_vi=str(description_vi or "").strip(),
                description_en=str(description_en or "").strip(),
                only_fill_empty=only_fill_empty,
            )
            if owns:
                conn.commit()
            return updated
        finally:
            if owns:
                conn.close()

