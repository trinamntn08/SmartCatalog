"""Native SmartCatalog PDF search workspace, owned by the application's Tk root."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext

from smartcatalog.ui.controllers.pdf_search_controller import PdfSearchControllerMixin
from smartcatalog.ui.widgets.pdf_document_view import PdfDocumentView


class PdfSearchWindow(tk.Toplevel, PdfSearchControllerMixin):
    def __init__(self, main_window):
        super().__init__(main_window.root)
        self.main_window = main_window
        self.title("SmartCatalog — Tìm & ghi chú PDF")
        self.geometry("1280x900")
        self.minsize(1050, 720)
        self.transient(main_window.root)
        self.init_controller()
        self._result_controls = []
        defaults = {
            "pdf_var": str(main_window.state.catalog_pdf_path or ""), "workbook_var": "",
            "source_var": "Excel", "sheet_var": "", "first_row_var": "2",
            "keyword_col_var": "A", "note_col_var": "C", "result_col_var": "B",
            "scope_var": "Sản phẩm đang chọn", "catalog_note_var": "Không ghi chú",
            "match_var": "Chứa từ khóa", "filter_var": "Tất cả", "position_var": "Trên phải",
            "offset_x_var": "5", "offset_y_var": "5", "font_var": "8", "color_var": "Đen",
            "zoom_var": "100%", "status": "Chọn PDF và nguồn từ khóa để bắt đầu.",
            "preview_status": "Chọn một kết quả sau khi tìm để xem PDF.",
        }
        for name, value in defaults.items():
            setattr(self, name, tk.StringVar(self, value=value))
        self._build_ui()
        self._update_controls()

    def _entry(self, parent, variable, width=20):
        widget = ttk.Entry(parent, textvariable=variable, width=width)
        self._input_controls.append((widget, "normal"))
        return widget

    def _combo(self, parent, variable, values, width=20):
        widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width)
        self._input_controls.append((widget, "readonly"))
        return widget

    def _button(self, parent, text, command):
        widget = ttk.Button(parent, text=text, command=command)
        self._input_controls.append((widget, "normal"))
        return widget

    def _result_button(self, parent, text, command):
        widget = ttk.Button(parent, text=text, command=command)
        self._result_controls.append(widget)
        return widget

    def _build_ui(self):
        shell = ttk.Frame(self, padding=10)
        shell.pack(fill="both", expand=True)
        inputs = ttk.LabelFrame(shell, text="Nguồn tìm kiếm", padding=8)
        inputs.pack(fill="x")
        inputs.columnconfigure(1, weight=1)
        ttk.Label(inputs, text="PDF").grid(row=0, column=0, sticky="w")
        self._entry(inputs, self.pdf_var).grid(row=0, column=1, columnspan=5, sticky="ew", padx=6)
        self._button(inputs, "Chọn PDF…", self.browse_pdf).grid(row=0, column=6)
        ttk.Label(inputs, text="Nguồn").grid(row=1, column=0, sticky="w", pady=5)
        source = self._combo(inputs, self.source_var, ("Excel", "Sản phẩm"), 15)
        source.grid(row=1, column=1, sticky="w", padx=6)
        source.bind("<<ComboboxSelected>>", self.source_changed)
        ttk.Label(inputs, text="Khớp").grid(row=1, column=2)
        self._combo(inputs, self.match_var, ("Chứa từ khóa", "Nguyên mã"), 18).grid(row=1, column=3, padx=6)
        ttk.Label(inputs, text="Không có OCR; giữ nguyên dấu gạch nối.").grid(row=1, column=4, columnspan=3, sticky="w")
        ttk.Label(inputs, text="Excel").grid(row=2, column=0, sticky="w")
        self._entry(inputs, self.workbook_var).grid(row=2, column=1, columnspan=5, sticky="ew", padx=6)
        self._button(inputs, "Chọn Excel…", self.browse_workbook).grid(row=2, column=6)
        mapping = ttk.Frame(inputs)
        mapping.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(6, 2))
        ttk.Label(mapping, text="Trang tính").pack(side="left")
        self.sheet_combo = self._combo(mapping, self.sheet_var, (), 20)
        self.sheet_combo.pack(side="left", padx=5)
        for label, var, width in (("Dòng đầu", self.first_row_var, 5), ("Cột từ khóa", self.keyword_col_var, 4),
                                  ("Cột ghi chú (tùy chọn)", self.note_col_var, 4), ("Cột kết quả", self.result_col_var, 4)):
            ttk.Label(mapping, text=label).pack(side="left", padx=(7, 2))
            self._entry(mapping, var, width).pack(side="left")
        catalog = ttk.Frame(inputs)
        catalog.grid(row=4, column=0, columnspan=7, sticky="ew", pady=(4, 0))
        ttk.Label(catalog, text="Sản phẩm").pack(side="left")
        self._combo(catalog, self.scope_var, ("Sản phẩm đang chọn", "Danh sách đang lọc", "Tất cả sản phẩm"), 24).pack(side="left", padx=5)
        self._combo(catalog, self.catalog_note_var, ("Không ghi chú", "Mô tả VI", "Mô tả EN"), 16).pack(side="left")
        ttk.Label(catalog, text="  Dùng dữ liệu đã lưu; không thay đổi CSDL.").pack(side="left")
        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=6)
        self._button(actions, "Đọc danh sách", self.read_inputs).pack(side="left")
        self._button(actions, "Tìm", self.start_search).pack(side="left", padx=6)
        self.cancel_button = ttk.Button(actions, text="Hủy", command=lambda: self._cancel.set())
        self.cancel_button.pack(side="left")
        self.progress = ttk.Progressbar(actions, length=180, mode="determinate")
        self.progress.pack(side="left", padx=10)
        self._button(actions, "Tùy chọn ghi chú ▾", self._toggle_options).pack(side="right")
        self.options_frame = ttk.LabelFrame(shell, text="Định dạng ghi chú — khoảng cách theo pt PDF", padding=6)
        for label, var, values, width in (
            ("Vị trí", self.position_var, ("Trên phải", "Trên trái", "Dưới phải", "Dưới trái"), 12),
            ("Màu", self.color_var, ("Đen", "Xanh dương", "Xanh lá", "Đỏ", "Vàng"), 12),
        ):
            ttk.Label(self.options_frame, text=label).pack(side="left", padx=(3, 4))
            self._combo(self.options_frame, var, values, width).pack(side="left")
        for label, var in (("X", self.offset_x_var), ("Y", self.offset_y_var), ("Cỡ chữ", self.font_var)):
            ttk.Label(self.options_frame, text=label).pack(side="left", padx=(10, 3))
            self._entry(self.options_frame, var, 5).pack(side="left")
        self.panes = ttk.PanedWindow(shell, orient="horizontal")
        self.panes.pack(fill="both", expand=True)
        left = ttk.Frame(self.panes)
        right = ttk.Frame(self.panes)
        self.panes.add(left, weight=2)
        self.panes.add(right, weight=3)
        filters = ttk.Frame(left)
        filters.pack(fill="x", pady=(0, 5))
        ttk.Label(filters, text="Kết quả").pack(side="left")
        filtered = self._combo(filters, self.filter_var, ("Tất cả", "Tìm thấy", "Không tìm thấy"), 18)
        filtered.pack(side="left", padx=6)
        filtered.bind("<<ComboboxSelected>>", self.filter_results)
        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.results_tree = ttk.Treeview(tree_box, columns=("keyword", "note", "pages", "count", "status"),
                                        show="headings", selectmode="browse")
        for col, label, width in (("keyword", "Từ khóa", 115), ("note", "Ghi chú", 110),
                                   ("pages", "Trang PDF", 85), ("count", "Số lần", 50), ("status", "Trạng thái", 100)):
            self.results_tree.heading(col, text=label)
            self.results_tree.column(col, width=width, minwidth=45)
        vs = ttk.Scrollbar(tree_box, orient="vertical", command=self.results_tree.yview)
        hs = ttk.Scrollbar(tree_box, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        tree_box.columnconfigure(0, weight=1)
        tree_box.rowconfigure(0, weight=1)
        self.results_tree.bind("<<TreeviewSelect>>", self.result_selected)
        navigation = ttk.Frame(right)
        navigation.pack(fill="x", pady=(0, 5))
        for label, callback in (("◀ Trang", lambda: self.move_page(-1)), ("Trang ▶", lambda: self.move_page(1)),
                                ("◀ Vị trí", lambda: self.move_hit(-1)), ("Vị trí ▶", lambda: self.move_hit(1))):
            self._result_button(navigation, label, callback).pack(side="left", padx=(0, 3))
        self._combo(navigation, self.zoom_var, ("75%", "100%", "125%", "150%", "200%"), 6).pack(side="left", padx=3)
        self._result_button(navigation, "Xem trước", self.preview).pack(side="left", padx=3)
        ttk.Label(right, textvariable=self.preview_status).pack(fill="x")
        self.viewer = PdfDocumentView(right)
        self.viewer.pack(fill="both", expand=True, pady=(5, 0))
        warnings = ttk.LabelFrame(shell, text="Cảnh báo / thông tin", padding=3)
        warnings.pack(fill="x", pady=(6, 0))
        self.warnings_text = scrolledtext.ScrolledText(warnings, height=3, wrap="word", state="disabled")
        self.warnings_text.pack(fill="x")
        outputs = ttk.Frame(shell)
        outputs.pack(fill="x", pady=(6, 0))
        for label, kind in (("Lưu PDF đánh dấu…", "pdf"), ("Lưu báo cáo Excel…", "report"), ("Lưu bản sao Excel…", "copy")):
            self._result_button(outputs, label, lambda k=kind: self.export(k)).pack(side="left", padx=(0, 6))
        ttk.Button(outputs, text="Mở thư mục kết quả", command=self.open_output_folder).pack(side="right")
        ttk.Label(shell, textvariable=self.status, anchor="w", wraplength=1150).pack(fill="x", pady=(6, 0))

    def _toggle_options(self):
        if self.options_frame.winfo_manager():
            self.options_frame.pack_forget()
        else:
            self.options_frame.pack(fill="x", pady=(0, 6), before=self.panes)
