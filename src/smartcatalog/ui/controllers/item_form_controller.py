# smartcatalog/ui/controllers/item_form_controller.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pathlib import Path
import os
from tkinter import messagebox


class ItemFormControllerMixin:
    """
    Item form behavior:
    - Load selected item into form vars + UI panels
    - Save current form into selected item + DB
    - Persist selected item (used by other controllers)

    Assumes MainWindow provides:
      - self._selected, self.state (db, selected_item_id, items_cache)
      - form vars: var_code, var_page, var_category, var_author, var_dimension, var_small_description,
                   var_shape, var_blade_tip, var_surface_treatment, var_material
      - self.description_excel_text (ScrolledText)
      - self.description_vietnames_from_excel_text (ScrolledText)
      - self._set_preview_text(), self._set_status()
      - self.items_tree (Treeview)
      - thumbnail methods: _render_thumbnails(), _clear_thumbnails()
      - page images method: _render_candidates_for_page(page_index_0based)
      - refresh_items()
    """

    def _reload_selected_into_form(self) -> None:
        it = getattr(self, "_selected", None)
        if not it:
            return

        # Basic fields
        self.var_code.set(it.code or "")
        self.var_page.set("" if it.page is None else str(it.page))

        # Structured fields
        self.var_category.set(getattr(it, "category", "") or "")
        self.var_author.set(getattr(it, "author", "") or "")
        self.var_dimension.set(getattr(it, "dimension", "") or "")
        self.var_small_description.set(getattr(it, "small_description", "") or "")
        self.var_shape.set(getattr(it, "shape", "") or "")
        self.var_blade_tip.set(getattr(it, "blade_tip", "") or "")
        self.var_surface_treatment.set(getattr(it, "surface_treatment", "") or "")
        self.var_material.set(getattr(it, "material", "") or "")

        # Description from Excel
        self.description_excel_text.delete("1.0", "end")
        self.description_excel_text.insert("1.0", it.description_excel or "")
        self.description_vietnames_from_excel_text.delete("1.0", "end")
        self.description_vietnames_from_excel_text.insert("1.0", it.description_vietnames_from_excel or "")
        self.var_validated.set(bool(getattr(it, "validated", False)))

        # Thumbnails (linked images for item)
        source_map = {}
        try:
            if getattr(self.state, "db", None):
                pairs = self.state.db.list_image_sources_for_item(int(it.id))
                source_map = {os.path.normcase(os.path.normpath(p)): s for p, s in pairs}
        except Exception:
            source_map = {}

        self._render_thumbnails(it.images or [], source_map=source_map)

        # Page Images (from PDF page, async + cached in candidates controller)
        if getattr(it, "page", None):
            try:
                self._render_candidates_for_page(int(it.page) - 1)  # DB is 1-based
            except Exception:
                # Candidates view should never crash the whole selection
                pass

        # Preview text (debug panel)
        img_lines = "\n".join([f"- {p}" for p in (it.images or [])[:8]])
        if it.images and len(it.images) > 8:
            img_lines += f"\n... ({len(it.images) - 8} more)"

        src_lines = ""
        try:
            if source_map:
                pairs = [(p, source_map.get(p, "")) for p in (it.images or [])[:8]]
                src_lines = "\n".join([f"- {Path(p).name}: {s}" for p, s in pairs if s])
        except Exception:
            src_lines = ""

        self._set_preview_text(
            f"ITEM\n"
            f"ID: {it.id}\n"
            f"CODE: {it.code}\n"
            f"PAGE: {it.page}\n\n"
            f"CATEGORY: {getattr(it, 'category', '')}\n"
            f"SHAPE: {getattr(it, 'shape', '')}\n"
            f"BLADE TIP: {getattr(it, 'blade_tip', '')}\n"
            f"SURFACE TREATMENT: {getattr(it, 'surface_treatment', '')}\n"
            f"MATERIAL: {getattr(it, 'material', '')}\n"
            f"AUTHOR: {getattr(it, 'author', '')}\n"
            f"DIMENSION: {getattr(it, 'dimension', '')}\n"
            f"SMALL DESCRIPTION: {getattr(it, 'small_description', '')}\n\n"
            f"DESCRIPTION FROM EXCEL (EN):\n{it.description_excel}\n\n"
            f"DESCRIPTION FROM EXCEL (VI):\n{getattr(it, 'description_vietnames_from_excel', '')}\n\n"
            f"IMAGES ({len(it.images or [])}):\n{img_lines}\n\n"
            f"NGUỒN ẢNH:\n{src_lines}"
        )
        self._capture_selected_snapshot()

    def _capture_selected_snapshot(self) -> None:
        it = getattr(self, "_selected", None)
        if not it:
            self._selected_snapshot = None
            return
        self._selected_snapshot = {
            "id": int(getattr(it, "id", 0) or 0),
            "code": str(getattr(it, "code", "") or ""),
            "page": getattr(it, "page", None),
            "category": str(getattr(it, "category", "") or ""),
            "author": str(getattr(it, "author", "") or ""),
            "dimension": str(getattr(it, "dimension", "") or ""),
            "small_description": str(getattr(it, "small_description", "") or ""),
            "shape": str(getattr(it, "shape", "") or ""),
            "blade_tip": str(getattr(it, "blade_tip", "") or ""),
            "surface_treatment": str(getattr(it, "surface_treatment", "") or ""),
            "material": str(getattr(it, "material", "") or ""),
            "description_excel": str(getattr(it, "description_excel", "") or ""),
            "description_vietnames_from_excel": str(getattr(it, "description_vietnames_from_excel", "") or ""),
            "validated": bool(getattr(it, "validated", False)),
            "validated_at": str(getattr(it, "validated_at", "") or ""),
            "images": list(getattr(it, "images", []) or []),
        }

    def _restore_selected_from_snapshot(self) -> None:
        snap = getattr(self, "_selected_snapshot", None)
        it = getattr(self, "_selected", None)
        if not it or not snap:
            return
        it.code = snap["code"]
        it.page = snap["page"]
        it.category = snap["category"]
        it.author = snap["author"]
        it.dimension = snap["dimension"]
        it.small_description = snap["small_description"]
        it.shape = snap["shape"]
        it.blade_tip = snap["blade_tip"]
        it.surface_treatment = snap["surface_treatment"]
        it.material = snap["material"]
        it.description_excel = snap["description_excel"]
        it.description_vietnames_from_excel = snap["description_vietnames_from_excel"]
        it.validated = snap["validated"]
        it.validated_at = snap["validated_at"]
        it.images = list(snap["images"])
        self._reload_selected_into_form()

    def _is_selected_dirty(self) -> bool:
        it = getattr(self, "_selected", None)
        snap = getattr(self, "_selected_snapshot", None)
        if not it or not snap:
            return False

        code = (self.var_code.get() or "").strip()
        page_str = (self.var_page.get() or "").strip()
        page_val = None
        if page_str:
            try:
                page_val = int(page_str)
            except ValueError:
                page_val = page_str

        current = {
            "code": code,
            "page": page_val,
            "category": (self.var_category.get() or "").strip(),
            "author": (self.var_author.get() or "").strip(),
            "dimension": (self.var_dimension.get() or "").strip(),
            "small_description": (self.var_small_description.get() or "").strip(),
            "shape": (self.var_shape.get() or "").strip(),
            "blade_tip": (self.var_blade_tip.get() or "").strip(),
            "surface_treatment": (self.var_surface_treatment.get() or "").strip(),
            "material": (self.var_material.get() or "").strip(),
            "description_excel": (self.description_excel_text.get("1.0", "end-1c") or "").strip(),
            "description_vietnames_from_excel": (
                self.description_vietnames_from_excel_text.get("1.0", "end-1c") or ""
            ).strip(),
            "validated": bool(self.var_validated.get()),
            "images": list(getattr(it, "images", []) or []),
        }
        original = {
            "code": snap["code"],
            "page": snap["page"],
            "category": snap["category"],
            "author": snap["author"],
            "dimension": snap["dimension"],
            "small_description": snap["small_description"],
            "shape": snap["shape"],
            "blade_tip": snap["blade_tip"],
            "surface_treatment": snap["surface_treatment"],
            "material": snap["material"],
            "description_excel": snap["description_excel"],
            "description_vietnames_from_excel": snap["description_vietnames_from_excel"],
            "validated": snap["validated"],
            "images": list(snap["images"]),
        }
        return current != original

    def _handle_unsaved_before_switch(self) -> bool:
        if not self._is_selected_dirty():
            return True
        ans = messagebox.askyesnocancel(
            "Thay đổi chưa lưu",
            "Bạn có thay đổi chưa lưu.\nBạn có muốn lưu trước khi chuyển sản phẩm không?",
        )
        if ans is None:
            return False
        if ans:
            return bool(self.on_save_item())
        self._restore_selected_from_snapshot()
        return True

    def _persist_item_images_to_db(self, item_id: int) -> None:
        it = getattr(self, "_selected", None)
        if not it or not getattr(self.state, "db", None):
            return

        db = self.state.db
        page = int(getattr(it, "page", 0) or 0)
        pdf_path = str(getattr(it, "pdf_path", "") or "")
        if not pdf_path and getattr(self.state, "catalog_pdf_path", None):
            pdf_path = str(self.state.catalog_pdf_path)

        source_map = dict(getattr(self, "_last_rendered_source_map", None) or {})

        conn = db.connect()
        try:
            db.clear_asset_links_for_item(int(item_id), conn=conn)
            for idx, path in enumerate(list(getattr(it, "images", []) or [])):
                nkey = os.path.normcase(os.path.normpath(str(path)))
                source = str(source_map.get(nkey, "") or "add").strip().lower() or "add"
                try:
                    asset_id = db.upsert_asset(
                        pdf_path=pdf_path,
                        page=page,
                        asset_path=str(path),
                        bbox=None,
                        source=source,
                        sha256="",
                        conn=conn,
                    )
                    db.link_asset_to_item(
                        item_id=int(item_id),
                        asset_id=int(asset_id),
                        match_method=("excel" if source == "excel" else "manual"),
                        score=None,
                        verified=True,
                        is_primary=(idx == 0),
                        conn=conn,
                    )
                except Exception:
                    continue
            conn.commit()
        finally:
            conn.close()

    def _persist_selected(self) -> None:
        if not getattr(self, "_selected", None) or not getattr(self.state, "db", None):
            return

        it = self._selected
        self.state.db.upsert_by_code(
            code=it.code,
            page=it.page,
            category=getattr(it, "category", "") or "",
            author=getattr(it, "author", "") or "",
            dimension=getattr(it, "dimension", "") or "",
            small_description=getattr(it, "small_description", "") or "",
            shape=getattr(it, "shape", "") or "",
            blade_tip=getattr(it, "blade_tip", "") or "",
            surface_treatment=getattr(it, "surface_treatment", "") or "",
            material=getattr(it, "material", "") or "",
            description=it.description or "",
            description_excel=it.description_excel or "",
            description_vietnames_from_excel=getattr(it, "description_vietnames_from_excel", "") or "",
            pdf_path=getattr(it, "pdf_path", "") or "",
            validated=bool(getattr(it, "validated", False)),
            validated_at=str(getattr(it, "validated_at", "") or ""),
            image_paths=it.images or [],
        )

    def on_save_item(self) -> bool:
        it = getattr(self, "_selected", None)
        if not it:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn sản phẩm ở danh sách bên trái.")
            return False

        code = (self.var_code.get() or "").strip()
        if not code:
            messagebox.showerror("Không hợp lệ", "Mã không được để trống.")
            return False

        page_str = (self.var_page.get() or "").strip()
        page_val: Optional[int] = None
        if page_str:
            try:
                page_val = int(page_str)
            except ValueError:
                messagebox.showerror("Không hợp lệ", "Trang phải là số nguyên.")
                return False

        # Update selected item in memory
        it.code = code
        it.page = page_val

        it.category = (self.var_category.get() or "").strip()
        it.author = (self.var_author.get() or "").strip()
        it.dimension = (self.var_dimension.get() or "").strip()
        it.small_description = (self.var_small_description.get() or "").strip()
        it.shape = (self.var_shape.get() or "").strip()
        it.blade_tip = (self.var_blade_tip.get() or "").strip()
        it.surface_treatment = (self.var_surface_treatment.get() or "").strip()
        it.material = (self.var_material.get() or "").strip()
        was_validated = bool(getattr(it, "validated", False))
        new_validated = bool(self.var_validated.get())
        it.validated = new_validated
        if new_validated:
            if not was_validated or not str(getattr(it, "validated_at", "") or "").strip():
                it.validated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            it.validated_at = ""

        # Description from Excel
        desc_excel = (self.description_excel_text.get("1.0", "end-1c") or "").strip()
        it.description_excel = desc_excel
        desc_vi_excel = (self.description_vietnames_from_excel_text.get("1.0", "end-1c") or "").strip()
        it.description_vietnames_from_excel = desc_vi_excel

        # Persist to DB
        if getattr(self.state, "db", None):
            old_item_id = int(getattr(it, "id", 0) or 0)
            item_id = self.state.db.upsert_by_code(
                code=it.code,
                page=it.page,
                category=it.category,
                author=it.author,
                dimension=it.dimension,
                small_description=it.small_description,
                shape=it.shape,
                blade_tip=it.blade_tip,
                surface_treatment=it.surface_treatment,
                material=it.material,
                description=it.description,
                description_excel=it.description_excel,
                description_vietnames_from_excel=getattr(it, "description_vietnames_from_excel", "") or "",
                pdf_path=getattr(it, "pdf_path", "") or "",
                validated=bool(getattr(it, "validated", False)),
                validated_at=str(getattr(it, "validated_at", "") or ""),
                image_paths=it.images or [],
            )
            self._persist_item_images_to_db(int(item_id))
            new_item_id = int(item_id)
            it.id = new_item_id

            # Fast path: avoid full list reload for normal save of current item.
            # Fallback to full refresh only when item identity changed unexpectedly.
            if new_item_id == old_item_id:
                try:
                    if hasattr(self, "items_tree") and self.items_tree.exists(str(new_item_id)):
                        validated_at = ""
                        if bool(getattr(it, "validated", False)):
                            fmt = getattr(self, "_format_validated_at_vi", None)
                            raw = str(getattr(it, "validated_at", "") or "")
                            validated_at = fmt(raw) if callable(fmt) else raw
                        self.items_tree.item(
                            str(new_item_id),
                            values=(
                                it.id,
                                it.code,
                                "" if it.page is None else it.page,
                                getattr(it, "category", ""),
                                getattr(it, "author", ""),
                                getattr(it, "shape", ""),
                                getattr(it, "blade_tip", ""),
                                getattr(it, "dimension", ""),
                                getattr(it, "surface_treatment", ""),
                                getattr(it, "material", ""),
                                validated_at,
                            ),
                        )
                except Exception:
                    pass
            else:
                self.refresh_items()
                self._selected = next((x for x in self.state.items_cache if int(x.id) == new_item_id), it)
                self._reload_selected_into_form()

            # Mark current form/item state as clean without forcing a full reload.
            try:
                self._capture_selected_snapshot()
            except Exception:
                pass

        self._set_status(f"✅ Đã lưu sản phẩm {it.id} ({it.code})")
        return True

    def on_add_item(self) -> None:
        if not getattr(self.state, "db", None):
            messagebox.showwarning("Thiếu CSDL", "Vui lòng tạo/tải CSDL trước (từ PDF).")
            return

        try:
            handler = getattr(self, "_handle_unsaved_before_switch", None)
            if callable(handler) and not bool(handler()):
                return
        except Exception:
            return

        pdf_path = ""
        try:
            if getattr(self.state, "catalog_pdf_path", None):
                pdf_path = str(self.state.catalog_pdf_path)
        except Exception:
            pdf_path = ""

        # Create a draft item (not saved yet) and clear all fields.
        from smartcatalog.state import CatalogItem

        draft = CatalogItem(
            id=0,
            code="",
            description="",
            description_excel="",
            description_vietnames_from_excel="",
            pdf_path=pdf_path,
            page=None,
            images=[],
            validated=False,
            validated_at="",
            category="",
            author="",
            dimension="",
            small_description="",
            shape="",
            blade_tip="",
            surface_treatment="",
            material="",
        )

        self._selected = draft
        try:
            if hasattr(self, "items_tree"):
                self.items_tree.selection_remove(self.items_tree.selection())
        except Exception:
            pass

        self._update_pdf_tools_label()
        self._reload_selected_into_form()
        self._set_status("✅ Đang thêm sản phẩm mới")

    def on_delete_item(self) -> None:
        it = getattr(self, "_selected", None)
        if not it:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn sản phẩm ở danh sách bên trái.")
            return

        if not getattr(self.state, "db", None):
            messagebox.showwarning("Thiếu CSDL", "Vui lòng tạo/tải CSDL trước (từ PDF).")
            return

        item_id = int(getattr(it, "id", 0) or 0)
        if not item_id:
            messagebox.showwarning("Không hợp lệ", "Sản phẩm đã chọn không có ID hợp lệ.")
            return

        code = str(getattr(it, "code", "") or "").strip()
        if not messagebox.askyesno("Xóa sản phẩm", f"Xóa sản phẩm {item_id} ({code})?"):
            return

        conn = self.state.db.connect()
        try:
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            conn.commit()
        finally:
            conn.close()

        self._selected = None
        try:
            if hasattr(self, "items_tree"):
                self.items_tree.selection_remove(self.items_tree.selection())
        except Exception:
            pass

        try:
            self.var_code.set("")
            self.var_page.set("")
            self.var_category.set("")
            self.var_author.set("")
            self.var_dimension.set("")
            self.var_small_description.set("")
            self.var_shape.set("")
            self.var_blade_tip.set("")
            self.var_surface_treatment.set("")
            self.var_material.set("")
            self.var_validated.set(False)
            self.description_excel_text.delete("1.0", "end")
            self.description_vietnames_from_excel_text.delete("1.0", "end")
            self._clear_thumbnails()
        except Exception:
            pass

        self.refresh_items()
        self._update_pdf_tools_label()
        self._set_status(f"✅ Đã xóa sản phẩm {item_id} ({code})")

