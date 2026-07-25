# smartcatalog/ui/controllers/images_controller.py
from __future__ import annotations

from pathlib import Path
import os
import shutil
import time
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk
from smartcatalog.utils.hashing import sha256_text


class ImagesControllerMixin:
    """
    Images panel behavior:
    - Render thumbnails for selected item (self._render_thumbnails)
    - Click thumbnail -> select + preview + store self._selected_image_path
    - Add image -> saves to assets + links to selected item
    - Remove selected -> unlink asset
    - Reorder image -> move selected image up/down

    Assumes MainWindow provides:
      - self.state (db, catalog_pdf_path, items_cache, selected_item_id)
      - self._selected (CatalogItem | None)
      - self.thumb_inner (Frame)
      - self.image_preview_label (Label)
      - self._thumb_refs: list[PhotoImage]
      - self._full_img_ref: PhotoImage | None
      - self._selected_image_path: str | None
      - self.refresh_items(), self._reload_selected_into_form(), self._set_status()
    """

    # ----------------------------
    # Thumbnails rendering
    # ----------------------------
    def _clear_thumbnails(self) -> None:
        self._hide_thumb_drag_ghost()
        self._hide_thumb_drop_indicator()
        for w in self.thumb_inner.winfo_children():
            w.destroy()
        self._thumb_refs.clear()
        self._full_img_ref = None
        self._selected_image_path = None
        if hasattr(self, "image_preview_label"):
            self.image_preview_label.configure(image="")

    def _render_thumbnails(self, image_paths: list[str], source_map: Optional[dict[str, str]] = None) -> None:
        prev_selected = self._selected_image_path
        self._clear_thumbnails()
        self._thumb_cells: list[tuple[str, tk.Misc]] = []
        if prev_selected and prev_selected in image_paths:
            self._selected_image_path = prev_selected

        # Cache last render inputs for refresh on selection change.
        self._last_rendered_image_paths = list(image_paths or [])
        self._last_rendered_source_map = dict(source_map or {})

        if not image_paths:
            return
        selected_path = self._selected_image_path
        thumb_w = 90
        thumb_h = 90
        pad = 6
        canvas_w = int(getattr(self, "thumb_canvas", None).winfo_width() or 400)
        cell_w = thumb_w + pad * 2
        cols = max(1, int(canvas_w // max(1, cell_w)))

        grid = ttk.Frame(self.thumb_inner)
        grid.pack(fill="both", expand=True)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

        for i, p in enumerate(image_paths):
            r = i // cols
            c = i % cols
            self._render_one_thumbnail(
                grid,
                p,
                r,
                c,
                pad,
                (thumb_w, thumb_h),
                selected_path,
                source_map or {},
            )

        if selected_path:
            self._set_preview_image(selected_path)

    def _render_one_thumbnail(
        self,
        parent: ttk.Frame,
        image_path: str,
        row: int,
        col: int,
        pad: int,
        size: tuple[int, int],
        selected_path: Optional[str],
        source_map: dict[str, str],
    ) -> None:
        is_selected = bool(selected_path) and image_path == selected_path
        cell = ttk.Frame(parent, relief=("solid" if is_selected else "flat"), borderwidth=(2 if is_selected else 0))
        cell.grid(row=row, column=col, padx=pad, pady=pad, sticky="nsew")
        setattr(cell, "_image_path", image_path)
        self._thumb_cells.append((image_path, cell))

        def _badge_text(source: str) -> str:
            s = (source or "").strip().lower()
            if s == "excel":
                return "Excel"
            if s == "manual_crop":
                return "Cắt tay"
            if s in ("extract", "page_extract"):
                return "Từ pdf"
            if s == "add":
                return "Thêm"
            return s.upper() if s else ""

        key = os.path.normcase(os.path.normpath(image_path))
        badge = _badge_text(source_map.get(key, ""))

        # Load thumb
        tk_img = None
        try:
            with Image.open(image_path) as pil:
                pil = pil.convert("RGBA")
                pil.thumbnail(size)
                tk_img = ImageTk.PhotoImage(pil)
        except Exception:
            tk_img = None

        if tk_img is not None:
            self._thumb_refs.append(tk_img)
            img_widget = ttk.Label(cell, image=tk_img, text="")
            img_widget.pack()
        else:
            img_widget = ttk.Label(cell, text="[Không xem được]", width=14)
            img_widget.pack()
        setattr(img_widget, "_image_path", image_path)

        drag_widgets = [cell, img_widget]
        if badge:
            b = ttk.Label(
                cell,
                text=badge,
                font=("Segoe UI", 7),
                foreground="#555555",
            )
            b.pack(pady=(2, 0))
            setattr(b, "_image_path", image_path)
            drag_widgets.append(b)

        # Drag reorder bindings (press-hold-move-release).
        for w in drag_widgets:
            w.bind("<ButtonPress-1>", lambda e, p=image_path: self._on_thumb_drag_start(e, p), add="+")
            w.bind("<B1-Motion>", self._on_thumb_drag_motion, add="+")
            w.bind("<ButtonRelease-1>", lambda e, p=image_path: self._on_thumb_drag_release(e, p), add="+")


    def _on_select_thumbnail(self, image_path: str) -> None:
        self._selected_image_path = image_path
        refreshed = False
        if getattr(self, "_last_rendered_image_paths", None):
            self._render_thumbnails(
                self._last_rendered_image_paths,
                source_map=getattr(self, "_last_rendered_source_map", None),
            )
            refreshed = True
        if not refreshed:
            self._set_preview_image(image_path)

    def _set_preview_image(self, image_path: Optional[str]) -> None:
        if not getattr(self, "image_preview_label", None):
            return

        if not image_path:
            self.image_preview_label.configure(image="")
            self._full_img_ref = None
            return

        try:
            # Use current label size when available; fallback to a reasonable default.
            self.image_preview_label.update_idletasks()
            preview_host = getattr(self, "image_preview_frame", None) or self.image_preview_label
            max_w = int(preview_host.winfo_width() or 240)
            max_h = int(preview_host.winfo_height() or 180)
            max_w = max(80, max_w)
            max_h = max(80, max_h)

            with Image.open(image_path) as pil:
                pil = pil.convert("RGBA")
                pil.thumbnail((max_w, max_h))
                self._full_img_ref = ImageTk.PhotoImage(pil)
            self.image_preview_label.configure(image=self._full_img_ref)
        except Exception:
            self.image_preview_label.configure(image="")
            self._full_img_ref = None

    # ----------------------------
    # Add / Remove
    # ----------------------------
    def on_add_image(self) -> None:
        """
        Add an external image file path to the selected item via assets + links.
        """
        if not self._selected:
            code = ""
            try:
                code = (self.var_code.get() or "").strip()
            except Exception:
                code = ""

            if code and getattr(self.state, "db", None):
                if not getattr(self.state, "items_cache", None):
                    try:
                        self.refresh_items()
                    except Exception:
                        pass

                match = next((x for x in self.state.items_cache if str(x.code) == code), None)
                if match is None:
                    try:
                        match = self.state.db.get_item_by_code(code)
                    except Exception:
                        match = None

                if match is None:
                    # Create a new item from form inputs, then continue.
                    try:
                        self.on_add_item()
                    except Exception:
                        pass
                else:
                    self._selected = match
                    try:
                        if hasattr(self, "items_tree"):
                            self.items_tree.selection_set(str(match.id))
                            self.items_tree.focus(str(match.id))
                    except Exception:
                        pass
                    try:
                        self._update_pdf_tools_label()
                    except Exception:
                        pass
                    try:
                        self._reload_selected_into_form()
                    except Exception:
                        pass

            if not self._selected:
                messagebox.showwarning("Chưa chọn", "Vui lòng thêm hoặc chọn sản phẩm trước.")
                return

        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            filetypes=[("Tệp ảnh", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tất cả tệp", "*.*")],
        )
        if not path:
            return

        # Copy into assets folder (new scheme) for portability and collision avoidance
        pdf_path = ""
        page = int(getattr(self._selected, "page", 0) or 0)
        try:
            data_dir = getattr(self.state, "data_dir", None)
            if data_dir:
                assets_dir = Path(data_dir) / "assets" / "manual_import"
                assets_dir.mkdir(parents=True, exist_ok=True)

                src = Path(path)
                ext = src.suffix or ".png"

                pdf_path = str(getattr(self._selected, "pdf_path", "") or "")
                if not pdf_path and getattr(self.state, "catalog_pdf_path", None):
                    pdf_path = str(self.state.catalog_pdf_path)

                pdf_stem = Path(pdf_path).stem if pdf_path else "pdf"
                safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in pdf_stem)
                pdf_key_src = pdf_path or "nopdf"
                pdf_key = sha256_text(pdf_key_src)[:8]
                xref = int(time.time() * 1000)

                base = f"{safe_stem}_{pdf_key}_page{page:04d}_xref{xref}"
                dest = assets_dir / f"{base}{ext.lower()}"
                i = 1
                while dest.exists():
                    dest = assets_dir / f"{base}_{i}{ext.lower()}"
                    i += 1

                shutil.copy2(str(src), str(dest))
                path = str(dest)
        except Exception:
            # Fallback: keep original path
            pass

        # Draft-only: keep changes in memory, persist when user clicks "Lưu".
        self._selected.images = list(self._selected.images or [])
        self._selected.images.append(path)
        self._render_thumbnails(
            self._selected.images or [],
            source_map=getattr(self, "_last_rendered_source_map", None),
        )
        self._selected_image_path = path
        self._on_select_thumbnail(path)
        self._set_status("✅ Đã thêm ảnh (chưa lưu)")

    def on_remove_selected_thumbnail(self) -> None:
        """
        Remove currently selected thumbnail from selected item:
        - Unlink from item_asset_links
        Also remove from in-memory selected.images and refresh UI.
        """
        if not self._selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn sản phẩm trước.")
            return

        img_path = (self._selected_image_path or "").strip()
        if not img_path:
            messagebox.showwarning("Chưa chọn ảnh", "Vui lòng chọn ảnh thu nhỏ trước (để xóa).")
            return

        # Draft-only: remove in memory; persist when user clicks "Lưu".
        self._selected.images = [p for p in (self._selected.images or []) if p != img_path]
        if self._selected_image_path == img_path:
            self._selected_image_path = (self._selected.images[0] if self._selected.images else None)
        self._render_thumbnails(
            self._selected.images or [],
            source_map=getattr(self, "_last_rendered_source_map", None),
        )
        if self._selected_image_path:
            self._on_select_thumbnail(self._selected_image_path)
        self._set_status("✅ Đã xóa ảnh (chưa lưu)")
    def on_rotate_selected_image(self, degrees: int) -> None:
        """
        Rotate selected image on disk and refresh UI.
        """
        if not self._selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn sản phẩm trước.")
            return

        img_path = (self._selected_image_path or "").strip()
        if not img_path:
            messagebox.showwarning("Chưa chọn ảnh", "Vui lòng chọn ảnh thu nhỏ trước (để xoay).")
            return

        try:
            with Image.open(img_path) as pil:
                # Preserve mode; expand keeps full image
                rotated = pil.rotate(degrees, expand=True)
                rotated.save(img_path)
        except Exception as e:
            messagebox.showerror("Xoay ảnh thất bại", f"Không thể xoay ảnh:\n{e}")
            return

        # Refresh thumbnails + preview without losing selection
        try:
            if hasattr(self, "items_tree") and getattr(self._selected, "id", None):
                self.items_tree.selection_set(str(self._selected.id))
                self.items_tree.focus(str(self._selected.id))
        except Exception:
            pass

        self._reload_selected_into_form()
        # reselect the rotated image
        self._selected_image_path = img_path
        self._on_select_thumbnail(img_path)
        self._set_status("✅ Đã xoay ảnh")

    @staticmethod
    def _extract_thumb_image_path(widget) -> Optional[str]:
        cur = widget
        while cur is not None:
            p = getattr(cur, "_image_path", None)
            if p:
                return str(p)
            cur = getattr(cur, "master", None)
        return None

    def _on_thumb_drag_start(self, event, image_path: str) -> None:
        self._hide_thumb_drag_ghost()
        self._hide_thumb_drop_indicator()
        self._drag_source_path = str(image_path or "")
        self._drag_start_xy = (int(getattr(event, "x_root", 0)), int(getattr(event, "y_root", 0)))
        self._drag_active = False
        if self._drag_source_path:
            # Do not re-render thumbnails here; destroying the source widget
            # during a drag can break subsequent motion/release events.
            self._selected_image_path = self._drag_source_path
            self._set_preview_image(self._drag_source_path)

    def _on_thumb_drag_motion(self, event) -> None:
        src = getattr(self, "_drag_source_path", "")
        if not src:
            return
        x0, y0 = getattr(self, "_drag_start_xy", (0, 0))
        dx = abs(int(getattr(event, "x_root", 0)) - x0)
        dy = abs(int(getattr(event, "y_root", 0)) - y0)
        if dx + dy >= 8:
            self._drag_active = True
            if not getattr(self, "_drag_ghost", None):
                self._show_thumb_drag_ghost(src, int(getattr(event, "x_root", 0)), int(getattr(event, "y_root", 0)))
            else:
                self._move_thumb_drag_ghost(int(getattr(event, "x_root", 0)), int(getattr(event, "y_root", 0)))
            xr = int(getattr(event, "x_root", 0))
            yr = int(getattr(event, "y_root", 0))
            if self._is_over_images_panel(xr, yr):
                info = self._compute_drop_insert_info(xr, yr, list(getattr(self._selected, "images", []) or []))
                if info:
                    _idx, x_line, y_top, y_bottom = info
                    self._show_thumb_drop_indicator(x_line, y_top, max(8, y_bottom - y_top))
                else:
                    self._hide_thumb_drop_indicator()
            else:
                self._hide_thumb_drop_indicator()

    def _on_thumb_drag_release(self, event, image_path: str) -> None:
        src = str(getattr(self, "_drag_source_path", "") or "")
        active = bool(getattr(self, "_drag_active", False))
        self._drag_source_path = ""
        self._drag_active = False
        self._hide_thumb_drag_ghost()
        self._hide_thumb_drop_indicator()
        if not src:
            return
        if not active:
            # Normal click: refresh thumbnail selection highlight.
            self._on_select_thumbnail(src)
            return
        if not self._selected:
            return
        if not self._is_over_images_panel(int(getattr(event, "x_root", 0)), int(getattr(event, "y_root", 0))):
            return

        imgs = list(self._selected.images or [])
        if src not in imgs:
            return
        src_idx = imgs.index(src)

        drop_idx = self._compute_drop_insert_index(
            int(getattr(event, "x_root", 0)),
            int(getattr(event, "y_root", 0)),
            imgs,
        )
        if drop_idx is None:
            target_widget = self.winfo_containing(int(getattr(event, "x_root", 0)), int(getattr(event, "y_root", 0)))
            dst = self._extract_thumb_image_path(target_widget) or str(image_path or "")
            if not dst or dst not in imgs:
                return
            drop_idx = imgs.index(dst)

        moved = imgs.pop(src_idx)
        if src_idx < drop_idx:
            drop_idx -= 1
        if drop_idx < 0:
            drop_idx = 0
        if drop_idx > len(imgs):
            drop_idx = len(imgs)
        imgs.insert(drop_idx, moved)
        if imgs == list(self._selected.images or []):
            return
        self._selected.images = imgs

        self._render_thumbnails(
            self._selected.images or [],
            source_map=getattr(self, "_last_rendered_source_map", None),
        )
        self._selected_image_path = src
        self._on_select_thumbnail(src)
        self._set_status("✅ Đã cập nhật thứ tự ảnh (chưa lưu)")

    def _compute_drop_insert_index(self, x_root: int, y_root: int, imgs: list[str]) -> Optional[int]:
        info = self._compute_drop_insert_info(x_root, y_root, imgs)
        return int(info[0]) if info else None

    def _compute_drop_insert_info(self, x_root: int, y_root: int, imgs: list[str]) -> Optional[tuple[int, int, int, int]]:
        """
        Compute insertion index + indicator position based on pointer position in thumbnail panel.
        Allows dropping on blank left/right space, not just on a thumbnail.
        Returns (insert_index, x_line_root, y_top_root, y_bottom_root).
        """
        cells = list(getattr(self, "_thumb_cells", []) or [])
        if not cells:
            return None

        entries: list[dict[str, int | str]] = []
        for p, w in cells:
            try:
                x0 = int(w.winfo_rootx())
                y0 = int(w.winfo_rooty())
                ww = int(w.winfo_width())
                hh = int(w.winfo_height())
                entries.append({"path": p, "x0": x0, "y0": y0, "x1": x0 + ww, "y1": y0 + hh, "xc": x0 + ww // 2, "yc": y0 + hh // 2})
            except Exception:
                continue
        if not entries:
            return None

        entries.sort(key=lambda e: (int(e["y0"]), int(e["x0"])))

        # Build visual rows from y-centers.
        rows: list[list[dict[str, int | str]]] = []
        row_tolerance = 42
        for e in entries:
            if not rows:
                rows.append([e])
                continue
            last_row = rows[-1]
            last_avg_y = sum(int(x["yc"]) for x in last_row) / max(1, len(last_row))
            if abs(int(e["yc"]) - int(last_avg_y)) <= row_tolerance:
                last_row.append(e)
            else:
                rows.append([e])

        # Pick nearest row by y.
        chosen_row = min(
            rows,
            key=lambda r: abs(y_root - int(sum(int(x["yc"]) for x in r) / max(1, len(r)))),
        )
        chosen_row = sorted(chosen_row, key=lambda e: int(e["xc"]))

        # Global path order by visual layout.
        visual_paths: list[str] = []
        for r in rows:
            for e in sorted(r, key=lambda t: int(t["xc"])):
                visual_paths.append(str(e["path"]))
        # Normalize to actual image list order membership.
        visual_paths = [p for p in visual_paths if p in imgs]
        if not visual_paths:
            return None

        y_top = min(int(e["y0"]) for e in chosen_row)
        y_bottom = max(int(e["y1"]) for e in chosen_row)

        # Insert before first thumbnail whose center is to the right of cursor.
        for e in chosen_row:
            if x_root < int(e["xc"]):
                p = str(e["path"])
                idx = visual_paths.index(p)
                x_line = int(e["x0"]) - 3
                return idx, x_line, y_top, y_bottom

        # Cursor is right of row: insert after last item in chosen row.
        last_p = str(chosen_row[-1]["path"])
        if last_p in visual_paths:
            idx = visual_paths.index(last_p) + 1
            x_line = int(chosen_row[-1]["x1"]) + 3
            return idx, x_line, y_top, y_bottom
        return len(visual_paths), int(chosen_row[-1]["x1"]) + 3, y_top, y_bottom

    def _is_over_images_panel(self, x_root: int, y_root: int) -> bool:
        target = getattr(self, "thumb_canvas", None)
        if target is None:
            return False
        try:
            x0 = target.winfo_rootx()
            y0 = target.winfo_rooty()
            x1 = x0 + target.winfo_width()
            y1 = y0 + target.winfo_height()
            return x0 <= x_root <= x1 and y0 <= y_root <= y1
        except Exception:
            return False

    def _show_thumb_drag_ghost(self, image_path: str, x_root: int, y_root: int) -> None:
        try:
            with Image.open(image_path) as pil:
                pil = pil.convert("RGBA")
                pil.thumbnail((72, 72))
                ghost_img = ImageTk.PhotoImage(pil)
        except Exception:
            return
        try:
            ghost = tk.Toplevel(self.root)
            ghost.overrideredirect(True)
            ghost.attributes("-topmost", True)
            try:
                ghost.attributes("-alpha", 0.85)
            except Exception:
                pass
            lbl = tk.Label(
                ghost,
                image=ghost_img,
                bd=1,
                relief="solid",
                background="#111111",
            )
            lbl.pack()
            self._drag_ghost_ref = ghost_img
            self._drag_ghost = ghost
            self._move_thumb_drag_ghost(x_root, y_root)
        except Exception:
            self._drag_ghost = None
            self._drag_ghost_ref = None

    def _move_thumb_drag_ghost(self, x_root: int, y_root: int) -> None:
        ghost = getattr(self, "_drag_ghost", None)
        if not ghost or not ghost.winfo_exists():
            return
        ghost.geometry(f"+{x_root + 14}+{y_root + 14}")

    def _hide_thumb_drag_ghost(self) -> None:
        ghost = getattr(self, "_drag_ghost", None)
        if ghost and ghost.winfo_exists():
            try:
                ghost.destroy()
            except Exception:
                pass
        self._drag_ghost = None
        self._drag_ghost_ref = None

    def _show_thumb_drop_indicator(self, x_root: int, y_root: int, height: int) -> None:
        ind = getattr(self, "_thumb_drop_indicator", None)
        if not ind or not ind.winfo_exists():
            try:
                ind = tk.Toplevel(self.root)
                ind.overrideredirect(True)
                ind.attributes("-topmost", True)
                frm = tk.Frame(ind, bg="#22C55E", width=3, height=max(8, int(height)))
                frm.pack(fill="both", expand=True)
                self._thumb_drop_indicator = ind
            except Exception:
                self._thumb_drop_indicator = None
                return
        try:
            # Update size and position in root coordinates.
            for child in ind.winfo_children():
                child.configure(height=max(8, int(height)))
            ind.geometry(f"3x{max(8, int(height))}+{int(x_root)}+{int(y_root)}")
        except Exception:
            pass

    def _hide_thumb_drop_indicator(self) -> None:
        ind = getattr(self, "_thumb_drop_indicator", None)
        if ind and ind.winfo_exists():
            try:
                ind.destroy()
            except Exception:
                pass
        self._thumb_drop_indicator = None

    # Image DB persistence is handled in item save flow.
