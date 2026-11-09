"""PDF tool lifecycle. Workers communicate through a queue, never through Tk."""
from __future__ import annotations

import os
from pathlib import Path
from queue import Empty, Queue
import threading
from tkinter import filedialog, messagebox

import fitz

from smartcatalog.domain.pdf_search import (
    KeywordInput, KeywordRow, NoteOptions, SearchCancelled, WorkbookInput,
)
from smartcatalog.loader.keyword_workbook import read_keyword_workbook, workbook_sheets
from smartcatalog.services.pdf_keyword_search import search_keywords, verify_sources, check_cancel
from smartcatalog.services.pdf_annotation_export import annotate_page, export_annotated_pdf
from smartcatalog.services.keyword_results_export import export_keyword_results


class PdfSearchControllerMixin:
    def init_controller(self):
        self.result = None
        self.input_snapshot = None
        self._queue = Queue()
        self._cancel = threading.Event()
        self._job = 0
        self._working = False
        self._closed = False
        self._hits = ()
        self._hit_index = 0
        self._preview_page = 0
        self._output_paths = {}
        self._input_controls = []
        self._poll_id = self.after(60, self._poll)
        self.protocol("WM_DELETE_WINDOW", self.close_tool)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self and not self._closed:
            self._shutdown()

    def _shutdown(self):
        self._closed = True
        self._cancel.set()
        self._job += 1
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def close_tool(self):
        self._shutdown()
        self.destroy()

    def _run(self, kind, work, done):
        if self._working or self._closed:
            return
        self._job += 1
        job = self._job
        self._cancel = threading.Event()
        cancel = self._cancel
        self._working = True
        self.status.set("Đang xử lý…")
        self.progress.configure(value=0)
        self._update_controls()
        queue = self._queue
        def progress(current, total):
            queue.put((job, "progress", (current, total)))
        def worker():
            try:
                value = work(cancel.is_set, progress)
            except SearchCancelled:
                queue.put((job, "cancelled", None))
            except Exception as exc:
                queue.put((job, "error", str(exc)))
            else:
                queue.put((job, "done", value))
        self._done = done
        self._kind = kind
        threading.Thread(target=worker, daemon=True, name="pdf-search-" + kind).start()

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                job, state, value = self._queue.get_nowait()
                if job != self._job:
                    continue
                if state == "progress":
                    current, total = value
                    self.progress.configure(maximum=max(total, 1), value=current)
                    self.status.set(f"Đang xử lý trang {current}/{total}…")
                    continue
                self._working = False
                self._update_controls()
                if state == "done":
                    self.status.set("Hoàn tất.")
                    try:
                        self._done(value)
                    except Exception as exc:
                        self._error(str(exc))
                elif state == "cancelled":
                    self.status.set("Đã hủy. Không xuất tệp chưa hoàn tất.")
                else:
                    self._error(value)
        except Empty:
            pass
        if not self._closed:
            self._poll_id = self.after(60, self._poll)

    def _error(self, text):
        self.status.set("Không hoàn tất. Có thể sửa và thử lại.")
        messagebox.showerror("Tìm & ghi chú PDF", text, parent=self)

    def _update_controls(self):
        for widget, idle_state in self._input_controls:
            widget.configure(state="disabled" if self._working else idle_state)
        self.cancel_button.configure(state="normal" if self._working else "disabled")
        ready = self.result is not None and not self._working
        for widget in self._result_controls:
            widget.configure(state="normal" if ready else "disabled")

    def browse_pdf(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("PDF", "*.pdf")])
        if path:
            self.pdf_var.set(path)

    def browse_workbook(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        self.workbook_var.set(path)
        def done(sheets):
            self.sheet_combo.configure(values=sheets)
            self.sheet_var.set(sheets[0] if sheets else "")
            self.status.set("Chọn cột và dòng bắt đầu, rồi bấm Đọc danh sách.")
        self._run("sheets", lambda cancel, progress: workbook_sheets(Path(path)), done)

    def _config(self):
        return WorkbookInput(Path(self.workbook_var.get()).resolve(), self.sheet_var.get(),
                             int(self.first_row_var.get()), self.keyword_col_var.get(),
                             self.note_col_var.get(), self.result_col_var.get())

    def _catalog_source(self):
        main = self.main_window
        if main._busy.get():
            raise ValueError("SmartCatalog đang bận. Vui lòng đợi trước khi đọc sản phẩm.")
        scope = self.scope_var.get()
        if scope == "Sản phẩm đang chọn":
            ids = set(main.items_tree.selection())
        elif scope == "Danh sách đang lọc":
            ids = set(main.items_tree.get_children())
        else:
            ids = {str(item.id) for item in main.state.items_cache}
        field = {"Không ghi chú": None, "Mô tả VI": "description_vietnames_from_excel",
                 "Mô tả EN": "description_excel"}[self.catalog_note_var.get()]
        rows = tuple(KeywordRow(item.id, item.code, str(getattr(item, field, "") or "") if field else "")
                     for item in main.state.items_cache if str(item.id) in ids and item.code.strip())
        if not rows:
            raise ValueError("Không có sản phẩm trong phạm vi đã chọn.")
        return KeywordInput(rows, ("Nguồn sản phẩm dùng dữ liệu đã lưu tại lúc đọc; không gồm chỉnh sửa chưa lưu.",))

    def _source_work(self):
        if self.source_var.get() == "Excel":
            config = self._config()
            return lambda cancel, progress: self._read_excel(config, cancel)
        source = self._catalog_source()
        return lambda cancel, progress: source

    @staticmethod
    def _read_excel(config, cancel):
        check_cancel(cancel)
        source = read_keyword_workbook(config, cancel=cancel)
        check_cancel(cancel)
        return source

    def read_inputs(self):
        try:
            work = self._source_work()
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return
        def done(source):
            self.result = None
            self.input_snapshot = source
            self.viewer.clear()
            self._hits = ()
            self._show_rows(source.rows)
            self._warnings(source.warnings + tuple(w for row in source.rows for w in row.warnings))
            self.status.set(f"Đã đọc {len(source.rows)} dòng. Kiểm tra danh sách rồi bấm Tìm.")
            self._update_controls()
        self._run("input", work, done)

    def start_search(self):
        try:
            work = self._source_work()
            path = Path(self.pdf_var.get()).resolve()
            if path.suffix.lower() != ".pdf" or not path.is_file():
                raise ValueError("Vui lòng chọn PDF hợp lệ.")
            whole = self.match_var.get() == "Nguyên mã"
        except (ValueError, OSError) as exc:
            self._error(str(exc))
            return
        # Reread inputs on every run; changing a selector can never reuse old rows.
        self.result = None
        self._hits = ()
        self.viewer.clear()
        def search(cancel, progress):
            return search_keywords(path, work(cancel, progress), whole_code=whole,
                                   cancel=cancel, progress=progress)
        def done(result):
            self.result = result
            self.input_snapshot = result.source
            self.filter_var.set("Tất cả")
            self.filter_results()
            found = sum(bool(row.hits) for row in result.rows)
            self.status.set(f"{found}/{len(result.rows)} dòng tìm thấy; {len(result.rows)-found} dòng không tìm thấy.")
            self._warnings(result.warnings + tuple(w for row in result.rows for w in row.row.warnings))
            self._update_controls()
        self._run("search", search, done)

    def _show_rows(self, rows):
        self.results_tree.delete(*self.results_tree.get_children())
        for index, row in enumerate(rows):
            self.results_tree.insert("", "end", iid=str(index), values=(row.keyword, row.note, "", "", "Chưa tìm"))

    def filter_results(self, _event=None):
        if self.result is None:
            return
        self.results_tree.delete(*self.results_tree.get_children())
        for index, row in enumerate(self.result.rows):
            if self.filter_var.get() == "Tìm thấy" and not row.hits:
                continue
            if self.filter_var.get() == "Không tìm thấy" and row.hits:
                continue
            self.results_tree.insert("", "end", iid=str(index), values=(row.row.keyword, row.row.note,
                                     ", ".join(map(str, row.pages)), len(row.hits),
                                     "Tìm thấy" if row.hits else "Không tìm thấy"))

    def _warnings(self, warnings):
        self.warnings_text.configure(state="normal")
        self.warnings_text.delete("1.0", "end")
        self.warnings_text.insert("1.0", "\n".join(warnings) if warnings else "Không có cảnh báo.")
        self.warnings_text.configure(state="disabled")

    def result_selected(self, _event=None):
        if self.result is None or self._working:
            return
        selection = self.results_tree.selection()
        if not selection:
            return
        row = self.result.rows[int(selection[0])]
        self._hits = row.hits
        self._hit_index = 0
        if self._hits:
            self._preview_page = self._hits[0].page_index
            self.preview()
        else:
            self.viewer.clear()
            self.preview_status.set("Từ khóa không xuất hiện trong PDF.")

    def note_options(self):
        positions = {"Trên phải": "Top Right", "Trên trái": "Top Left",
                     "Dưới phải": "Bottom Right", "Dưới trái": "Bottom Left"}
        colors = {"Đen": "black", "Xanh dương": "blue", "Xanh lá": "green", "Đỏ": "red", "Vàng": "yellow"}
        options = NoteOptions(positions[self.position_var.get()], float(self.offset_x_var.get()),
                              float(self.offset_y_var.get()), colors[self.color_var.get()], float(self.font_var.get()))
        options.validate()
        return options

    def move_hit(self, delta):
        if not self._hits or self._working:
            return
        self._hit_index = (self._hit_index + delta) % len(self._hits)
        self._preview_page = self._hits[self._hit_index].page_index
        self.preview()

    def move_page(self, delta):
        if self.result is None or self._working:
            return
        self._preview_page = min(max(0, self._preview_page + delta), self.result.page_count - 1)
        self.preview()

    def preview(self):
        if self.result is None or self._working:
            return
        try:
            options = self.note_options()
            zoom = float(self.zoom_var.get().rstrip("%")) / 100
        except (ValueError, KeyError) as exc:
            self._error(str(exc))
            return
        result = self.result
        index = self._preview_page
        hit = self._hits[self._hit_index] if self._hits and self._hits[self._hit_index].page_index == index else None
        def render(cancel, progress):
            check_cancel(cancel)
            verify_sources(result)
            with fitz.open(result.pdf_path) as doc:
                page = doc[index]
                warnings = annotate_page(page, result, index, options, cancel)
                if hit:
                    for rect in hit.rectangles:
                        page.draw_rect(fitz.Rect(rect), color=(0.95, 0.25, 0.05), width=1.5, overlay=True)
                image = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                focus = None
                if hit:
                    point = fitz.Point(hit.rectangles[0][:2]) * page.rotation_matrix
                    focus = (point.x * zoom, point.y * zoom)
                check_cancel(cancel)
                return image.tobytes("png"), warnings, focus
        def done(value):
            png, warnings, focus = value
            self.viewer.show_png(png, focus)
            occurrence = f" | Vị trí {self._hit_index+1}/{len(self._hits)}" if hit else ""
            self.preview_status.set(f"Trang {index+1}/{result.page_count}{occurrence} | Xem trước định dạng xuất")
            self.status.set("Xem trước sẵn sàng." + (f" {len(warnings)} cảnh báo ghi chú." if warnings else ""))
            if warnings:
                self._warnings(result.warnings + warnings)
        self._run("preview", render, done)

    def export(self, kind):
        if self.result is None or self._working:
            return
        result = self.result
        try:
            options = self.note_options() if kind == "pdf" else None
            copy = kind == "copy"
            if copy and not result.source.workbook:
                raise ValueError("Bản sao Excel chỉ dùng khi nguồn là Excel.")
            if copy and not messagebox.askokcancel("Bản sao Excel", "Cột kết quả trong bản sao sẽ được thay thế. Đối tượng Excel nâng cao có thể thay đổi; hãy dùng báo cáo riêng nếu cần giữ nguyên định dạng. Tiếp tục?", parent=self):
                return
            suffix = ".pdf" if kind == "pdf" else ".xlsx"
            base = result.pdf_path if kind == "pdf" or not result.source.workbook else result.source.workbook.path
            default = base.stem + ("_highlighted" if kind == "pdf" else "_search_results") + suffix
            selected = filedialog.asksaveasfilename(parent=self, defaultextension=suffix, initialdir=str(base.parent),
                                                    initialfile=default, filetypes=[("Kết quả", "*" + suffix)])
            if not selected:
                return
            path = Path(selected).resolve()
            for previous_kind, previous in self._output_paths.items():
                if previous == path and previous_kind != kind:
                    raise ValueError("Hãy chọn tên khác để giữ kết quả xuất trước.")
            overwrite = path.exists()
            if overwrite and not messagebox.askyesno("Thay tệp kết quả?", f"Thay tệp đã tồn tại?\n{path}", parent=self):
                return
        except (ValueError, OSError, KeyError) as exc:
            self._error(str(exc))
            return
        def work(cancel, progress):
            if kind == "pdf":
                return export_annotated_pdf(result, path, options, overwrite=overwrite, cancel=cancel, progress=progress)
            return export_keyword_results(result, path, copy_workbook=copy, overwrite=overwrite, cancel=cancel)
        def done(exported):
            self._output_paths[kind] = exported.path
            self.status.set(f"Đã lưu: {exported.path}")
            self._warnings(result.warnings + exported.warnings)
            messagebox.showinfo("Đã lưu kết quả", str(exported.path) + ("\n\n" + "\n".join(exported.warnings) if exported.warnings else ""), parent=self)
        self._run("export", work, done)

    def open_output_folder(self):
        if not self._output_paths:
            messagebox.showinfo("Kết quả", "Chưa có tệp kết quả đã lưu.", parent=self)
            return
        try:
            os.startfile(str(list(self._output_paths.values())[-1].parent))
        except OSError as exc:
            self._error(str(exc))

    def source_changed(self, _event=None):
        self.match_var.set("Nguyên mã" if self.source_var.get() == "Sản phẩm" else "Chứa từ khóa")
