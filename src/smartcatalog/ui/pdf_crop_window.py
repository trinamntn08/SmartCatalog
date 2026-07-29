# smartcatalog/ui/pdf_crop_window.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import threading
from typing import Callable, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox


@dataclass
class PdfCropContext:
    item_id: int
    page_1based: int
    pdf_path: Path


@dataclass(frozen=True)
class PdfSearchResult:
    page_index: int
    snippet: str


@dataclass(frozen=True)
class PdfPageLayout:
    page_index: int
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def build_page_layout(
    page_sizes: list[tuple[float, float]],
    zoom: float,
    gap: int = 16,
) -> list[PdfPageLayout]:
    """Stack all PDF pages vertically and center narrower pages."""
    scaled = [
        (max(1, round(width * zoom)), max(1, round(height * zoom)))
        for width, height in page_sizes
    ]
    max_width = max((width for width, _height in scaled), default=1)
    layouts: list[PdfPageLayout] = []
    top = gap
    for page_index, (width, height) in enumerate(scaled):
        left = gap + (max_width - width) // 2
        layouts.append(PdfPageLayout(page_index, left, top, width, height))
        top += height + gap
    return layouts


def search_pdf_pages(pdf_path: Path, query: str) -> list[PdfSearchResult]:
    """Search all page text using a document local to the calling thread."""
    needle = query.strip().casefold()
    if not needle:
        return []

    results: list[PdfSearchResult] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index, page in enumerate(doc):
            text = re.sub(r"\s+", " ", page.get_text("text")).strip()
            match_at = text.casefold().find(needle)
            if match_at < 0:
                continue
            start = max(0, match_at - 55)
            end = min(len(text), match_at + len(needle) + 85)
            snippet = text[start:end]
            if start:
                snippet = f"…{snippet}"
            if end < len(text):
                snippet = f"{snippet}…"
            results.append(PdfSearchResult(page_index, snippet))
    return results


class PdfCropWindow(tk.Toplevel):
    """
    Popup window for viewing a PDF page and cropping an area to create an asset + link to item.

    UX:
      - Drag to select
      - Enter = Save crop
      - Esc = Clear selection
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        state,
        item_id: int,
        page_1based: int,
        on_after_save: Optional[Callable[[], None]] = None,
        title: str = "Trình xem cắt PDF",
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.ctx = PdfCropContext(
            item_id=int(item_id),
            page_1based=int(page_1based),
            pdf_path=Path(self.state.catalog_pdf_path) if self.state.catalog_pdf_path else Path(),
        )
        self.on_after_save = on_after_save

        self.title(title)
        self.geometry("1100x800")
        self.minsize(900, 650)
        self.transient(parent)
        self.grab_set()  # modal-ish, better UX

        # PDF state
        self._doc: Optional[fitz.Document] = None
        self._page_index: int = max(0, self.ctx.page_1based - 1)
        self._zoom: float = 2.0
        self._page_layouts: list[PdfPageLayout] = []
        self._page_pil_images: dict[int, Image.Image] = {}
        self._page_tk_images: dict[int, ImageTk.PhotoImage] = {}
        self._page_canvas_ids: dict[int, int] = {}
        self._search_generation = 0

        # selection state (canvas coords)
        self._sel_start: Optional[tuple[int, int]] = None
        self._sel_rect_id: Optional[int] = None
        self._sel_rect_canvas: Optional[tuple[int, int, int, int]] = None
        self._selection_page_index: Optional[int] = None

        self._build_ui()
        self._bind_shortcuts()

        if not self._ensure_doc_open():
            messagebox.showerror("Thiếu PDF", "Chưa chọn PDF hoặc không thể mở PDF.")
            self.destroy()
            return

        self._populate_page_list()
        self._build_document_layout()
        self.update_idletasks()
        self._go_to_page(self._page_index)

    # -------------------------
    # UI
    # -------------------------

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        # Top controls
        top = ttk.Frame(root)
        top.pack(fill="x")

        self.lbl_info = ttk.Label(top, text="—")
        self.lbl_info.pack(side="left")

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="◀ Trang trước", command=self._prev_page).pack(side="left")
        ttk.Button(top, text="Trang sau ▶", command=self._next_page).pack(side="left", padx=(6, 0))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="🔍 Phóng to +", command=lambda: self._set_zoom(self._zoom * 1.25)).pack(side="left")
        ttk.Button(top, text="🔎 Thu nhỏ -", command=lambda: self._set_zoom(max(0.6, self._zoom / 1.25))).pack(side="left", padx=(6, 0))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="🧹 Xóa chọn (Esc)", command=self._clear_selection).pack(side="right")
        ttk.Button(top, text="💾 Lưu ảnh cắt (Enter)", command=self._save_crop).pack(side="right", padx=(0, 8))

        # Whole-document navigator and canvas area
        mid = ttk.Frame(root)
        mid.pack(fill="both", expand=True, pady=(8, 0))

        navigator = ttk.LabelFrame(mid, text="Toàn bộ PDF", padding=6)
        navigator.pack(side="left", fill="y", padx=(0, 8))

        search_row = ttk.Frame(navigator)
        search_row.pack(fill="x")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=25)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<Return>", self._start_search)
        ttk.Button(search_row, text="Tìm", command=self._start_search).pack(side="left", padx=(4, 0))

        self.search_status = ttk.Label(navigator, text="Chọn một trang để xem.", anchor="w")
        self.search_status.pack(fill="x", pady=(5, 3))

        list_frame = ttk.Frame(navigator)
        list_frame.pack(fill="both", expand=True)
        self.page_list = tk.Listbox(list_frame, width=36, exportselection=False)
        self.page_list.pack(side="left", fill="both", expand=True)
        page_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.page_list.yview)
        page_scroll.pack(side="right", fill="y")
        self.page_list.configure(yscrollcommand=page_scroll.set)
        self.page_list.bind("<<ListboxSelect>>", self._on_page_list_select)

        self.canvas = tk.Canvas(mid, highlightthickness=1)
        self.canvas.pack(side="left", fill="both", expand=True)

        vscroll = ttk.Scrollbar(mid, orient="vertical", command=self._on_vertical_scroll)
        vscroll.pack(side="right", fill="y")

        hscroll = ttk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        hscroll.pack(fill="x")

        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", lambda _event: self.after_idle(self._render_visible_pages))

        # Bottom hint
        hint = ttk.Label(
            root,
            text="Mẹo: Kéo để chọn. Enter = lưu ảnh cắt vào sản phẩm. Esc = xóa chọn.",
            anchor="w",
        )
        hint.pack(fill="x", pady=(8, 0))

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _e: self._clear_selection())
        self.bind("<Return>", lambda _e: self._save_crop())
        self.bind("<KP_Enter>", lambda _e: self._save_crop())

    # -------------------------
    # PDF lifecycle / rendering
    # -------------------------

    def _ensure_doc_open(self) -> bool:
        if self._doc is not None:
            return True

        if not self.ctx.pdf_path or not self.ctx.pdf_path.exists():
            return False

        try:
            self._doc = fitz.open(str(self.ctx.pdf_path))
            return True
        except Exception:
            self._doc = None
            return False

    def destroy(self) -> None:
        for image in self._page_pil_images.values():
            image.close()
        self._page_pil_images.clear()
        self._page_tk_images.clear()
        try:
            if self._doc is not None:
                self._doc.close()
        except Exception:
            pass
        self._doc = None
        super().destroy()

    def _set_zoom(self, z: float) -> None:
        self._zoom = float(z)
        self._clear_selection()
        self._build_document_layout()
        self._go_to_page(self._page_index)

    def _prev_page(self) -> None:
        if not self._doc:
            return
        self._go_to_page(self._page_index - 1)

    def _next_page(self) -> None:
        if not self._doc:
            return
        self._go_to_page(self._page_index + 1)

    def _go_to_page(self, page_index: int) -> None:
        if not self._doc or not self._page_layouts:
            return
        self._page_index = max(0, min(len(self._doc) - 1, int(page_index)))
        layout = self._page_layouts[self._page_index]
        scrollregion = self.canvas.cget("scrollregion").split()
        total_height = float(scrollregion[3]) if len(scrollregion) == 4 else layout.bottom
        self.canvas.yview_moveto(max(0.0, layout.top / max(1.0, total_height)))
        self._update_current_page_ui()
        self._render_visible_pages()

    def _populate_page_list(self) -> None:
        if not self._doc:
            return
        self.page_list.delete(0, "end")
        for page_index in range(len(self._doc)):
            self.page_list.insert("end", f"Trang {page_index + 1}")
        self.search_status.configure(text=f"{len(self._doc)} trang trong tài liệu.")
        self._select_current_page_in_list()

    def _select_current_page_in_list(self) -> None:
        if self.page_list.size() != len(self._doc or ()):
            return
        self.page_list.selection_clear(0, "end")
        self.page_list.selection_set(self._page_index)
        self.page_list.see(self._page_index)

    def _on_page_list_select(self, _event=None) -> None:
        selection = self.page_list.curselection()
        if not selection:
            return
        match = re.match(r"Trang (\d+)", self.page_list.get(selection[0]))
        if match:
            self._go_to_page(int(match.group(1)) - 1)

    def _start_search(self, _event=None) -> None:
        query = self.search_var.get().strip()
        self._search_generation += 1
        generation = self._search_generation
        if not query:
            self._populate_page_list()
            return "break"

        self.search_status.configure(text="Đang tìm trong toàn bộ PDF…")
        self.page_list.delete(0, "end")

        def worker() -> None:
            try:
                results = search_pdf_pages(self.ctx.pdf_path, query)
                error = None
            except Exception as exc:
                results = []
                error = str(exc)
            try:
                self.after(0, lambda: self._show_search_results(generation, results, error))
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return "break"

    def _show_search_results(
        self,
        generation: int,
        results: list[PdfSearchResult],
        error: Optional[str],
    ) -> None:
        if generation != self._search_generation or not self.winfo_exists():
            return
        self.page_list.delete(0, "end")
        if error:
            self.search_status.configure(text="Không thể tìm kiếm trong PDF.")
            return
        for result in results:
            preview = result.snippet or "(không có đoạn xem trước)"
            self.page_list.insert("end", f"Trang {result.page_index + 1}: {preview}")
        self.search_status.configure(text=f"Tìm thấy {len(results)} trang.")

    def _build_document_layout(self) -> None:
        if not self._doc:
            return
        self.canvas.delete("all")
        for image in self._page_pil_images.values():
            image.close()
        self._page_pil_images.clear()
        self._page_tk_images.clear()
        self._page_canvas_ids.clear()

        page_sizes = [(page.rect.width, page.rect.height) for page in self._doc]
        self._page_layouts = build_page_layout(page_sizes, self._zoom)
        max_right = max((layout.right for layout in self._page_layouts), default=1)
        max_bottom = max((layout.bottom for layout in self._page_layouts), default=1)
        for layout in self._page_layouts:
            self.canvas.create_rectangle(
                layout.left,
                layout.top,
                layout.right,
                layout.bottom,
                fill="#eeeeee",
                outline="#999999",
            )
            self.canvas.create_text(
                layout.left + 8,
                layout.top + 8,
                text=f"Trang {layout.page_index + 1} — đang tải…",
                anchor="nw",
                fill="#666666",
            )
        self.canvas.configure(scrollregion=(0, 0, max_right + 16, max_bottom + 16))

    def _render_page_image(self, page_index: int) -> None:
        if not self._doc or page_index in self._page_tk_images:
            return
        page = self._doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(self._zoom, self._zoom), alpha=False)
        pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        tk_image = ImageTk.PhotoImage(pil)
        layout = self._page_layouts[page_index]
        canvas_id = self.canvas.create_image(
            layout.left,
            layout.top,
            image=tk_image,
            anchor="nw",
        )
        self._page_pil_images[page_index] = pil
        self._page_tk_images[page_index] = tk_image
        self._page_canvas_ids[page_index] = canvas_id

    def _render_visible_pages(self) -> None:
        if not self._doc or not self._page_layouts:
            return
        viewport_top = float(self.canvas.canvasy(0))
        viewport_height = max(1, self.canvas.winfo_height())
        viewport_bottom = viewport_top + viewport_height
        buffer = viewport_height
        nearby = {
            layout.page_index
            for layout in self._page_layouts
            if layout.bottom >= viewport_top - buffer
            and layout.top <= viewport_bottom + buffer
        }
        nearby.add(self._page_index)
        if self._selection_page_index is not None:
            nearby.add(self._selection_page_index)

        for page_index in sorted(nearby):
            self._render_page_image(page_index)

        for page_index in set(self._page_tk_images) - nearby:
            self.canvas.delete(self._page_canvas_ids.pop(page_index))
            self._page_tk_images.pop(page_index)
            self._page_pil_images.pop(page_index).close()

    def _on_vertical_scroll(self, *args) -> None:
        self.canvas.yview(*args)
        self.after_idle(self._after_document_scroll)

    def _on_mousewheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta * 3, "units")
        self.after_idle(self._after_document_scroll)
        return "break"

    def _after_document_scroll(self) -> None:
        self._update_page_from_viewport()
        self._render_visible_pages()

    def _update_page_from_viewport(self) -> None:
        if not self._page_layouts:
            return
        center = float(self.canvas.canvasy(0)) + max(1, self.canvas.winfo_height()) / 2
        self._page_index = min(
            range(len(self._page_layouts)),
            key=lambda index: abs(
                (self._page_layouts[index].top + self._page_layouts[index].bottom) / 2
                - center
            ),
        )
        self._update_current_page_ui()

    def _update_current_page_ui(self) -> None:
        if not self._doc:
            return
        if not self.search_var.get().strip():
            self._select_current_page_in_list()
        self.lbl_info.configure(
            text=(
                f"PDF: {self.ctx.pdf_path.name} | Trang {self._page_index + 1}/"
                f"{len(self._doc)} | Phóng to {self._zoom:.2f} | "
                f"Sản phẩm {self.ctx.item_id}"
            )
        )

    # -------------------------
    # Selection rectangle
    # -------------------------

    def _canvas_to_image_xy(self, x: int, y: int) -> tuple[int, int]:
        return int(self.canvas.canvasx(x)), int(self.canvas.canvasy(y))

    def _page_at_canvas_point(self, x: int, y: int) -> Optional[PdfPageLayout]:
        return next(
            (
                layout
                for layout in self._page_layouts
                if layout.left <= x <= layout.right and layout.top <= y <= layout.bottom
            ),
            None,
        )

    def _clear_selection(self) -> None:
        self._sel_rect_canvas = None
        self._sel_start = None
        self._selection_page_index = None
        if self._sel_rect_id is not None:
            try:
                self.canvas.delete(self._sel_rect_id)
            except Exception:
                pass
        self._sel_rect_id = None

    def _on_mouse_down(self, e) -> None:
        self._clear_selection()

        x, y = self._canvas_to_image_xy(e.x, e.y)
        layout = self._page_at_canvas_point(x, y)
        if layout is None:
            return
        self._selection_page_index = layout.page_index
        self._page_index = layout.page_index
        self._render_page_image(layout.page_index)
        self._update_current_page_ui()
        self._sel_start = (x, y)
        self._sel_rect_id = self.canvas.create_rectangle(x, y, x, y, outline="red", width=2)

    def _on_mouse_drag(self, e) -> None:
        if not self._sel_start or self._sel_rect_id is None:
            return
        x0, y0 = self._sel_start
        x1, y1 = self._canvas_to_image_xy(e.x, e.y)
        self.canvas.coords(self._sel_rect_id, x0, y0, x1, y1)

    def _on_mouse_up(self, e) -> None:
        if (
            not self._sel_start
            or self._sel_rect_id is None
            or self._selection_page_index is None
        ):
            return

        x0, y0 = self._sel_start
        x1, y1 = self._canvas_to_image_xy(e.x, e.y)

        x0, x1 = sorted([int(x0), int(x1)])
        y0, y1 = sorted([int(y0), int(y1)])

        layout = self._page_layouts[self._selection_page_index]
        x0 = max(layout.left, min(layout.right - 1, x0))
        x1 = max(layout.left, min(layout.right, x1))
        y0 = max(layout.top, min(layout.bottom - 1, y0))
        y1 = max(layout.top, min(layout.bottom, y1))

        if (x1 - x0) < 10 or (y1 - y0) < 10:
            self._clear_selection()
            return

        self._sel_rect_canvas = (x0, y0, x1, y1)
        self._sel_start = None

    # -------------------------
    # Save crop -> asset -> link
    # -------------------------

    def _next_crop_filename(self, out_dir: Path, base: str) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        # item12_p0012_crop001.png
        for i in range(1, 10000):
            p = out_dir / f"{base}_crop{i:03d}.png"
            if not p.exists():
                return p
        return out_dir / f"{base}_crop9999.png"

    def _save_crop(self) -> None:
        if not self.state.db:
            messagebox.showwarning("Thiếu CSDL", "CSDL chưa được tải.")
            return
        if self._selection_page_index is None or not self._sel_rect_canvas:
            messagebox.showwarning("Chưa chọn vùng", "Vui lòng kéo trên PDF để chọn vùng cắt trước.")
            return

        upsert_asset = getattr(self.state.db, "upsert_asset", None)
        link_asset = getattr(self.state.db, "link_asset_to_item", None)
        if not callable(upsert_asset) or not callable(link_asset):
            messagebox.showerror("Thiếu tính năng CSDL", "CSDL chưa hỗ trợ assets/link.")
            return

        page_index = self._selection_page_index
        layout = self._page_layouts[page_index]
        page_image = self._page_pil_images.get(page_index)
        if page_image is None:
            self._render_page_image(page_index)
            page_image = self._page_pil_images[page_index]
        x0, y0, x1, y1 = self._sel_rect_canvas
        local_bbox = (
            x0 - layout.left,
            y0 - layout.top,
            x1 - layout.left,
            y1 - layout.top,
        )
        crop = page_image.crop(local_bbox)

        # Save into: config/database/assets/manual_crop/pXXXX/
        out_dir = self.state.assets_dir / "pdf_import" / "manual_crop" / f"p{(page_index + 1):04d}"
        base = f"item{self.ctx.item_id}_p{(page_index + 1):04d}"
        out_path = self._next_crop_filename(out_dir, base)
        crop.save(out_path, format="PNG")

        # bbox in PDF points (pixels / zoom)
        z = float(self._zoom)
        bbox_pdf = tuple(value / z for value in local_bbox)

        asset_id = upsert_asset(
            pdf_path=str(self.ctx.pdf_path),
            page=int(page_index + 1),
            asset_path=str(out_path),
            bbox=bbox_pdf,
            source="manual_crop",
            sha256="",
        )

        link_asset(
            item_id=int(self.ctx.item_id),
            asset_id=int(asset_id),
            match_method="manual_crop",
            score=None,
            verified=True,
            is_primary=False,
        )

        # Refresh parent UI + close
        if callable(self.on_after_save):
            try:
                self.on_after_save()
            except Exception:
                pass

        self.destroy()
