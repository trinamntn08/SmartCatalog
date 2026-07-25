from __future__ import annotations

from typing import Optional

import tkinter as tk
from tkinter import messagebox, ttk

from smartcatalog.services.export_preflight import ExportPreflightItem


class ExportReviewDialog:
    """Modal editor for resolving export problems before creating the workbook."""

    FILTERS = (
        "Tất cả mục chưa hoàn chỉnh",
        "Thiếu mô tả VI",
        "Thiếu mô tả EN",
        "Thiếu ảnh",
        "Mã không tồn tại",
    )

    def __init__(self, parent: tk.Misc, db, issues: list[ExportPreflightItem]):
        self.parent = parent
        self.db = db
        self.issues = issues
        self.result = "cancel"
        self._visible: list[ExportPreflightItem] = []
        self._selected: Optional[ExportPreflightItem] = None
        self._dirty = False
        self._ignore_selection_event = False

        self.window = tk.Toplevel(parent)
        self.window.title("Kiểm tra dữ liệu trước khi xuất")
        self.window.transient(parent)
        self.window.geometry("980x520")
        self.window.minsize(820, 460)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value=self.FILTERS[0])
        self.summary_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self._build()
        self._refresh_tree()
        self.window.grab_set()
        self.window.focus_force()

    def show(self) -> str:
        self.parent.wait_window(self.window)
        return self.result

    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Kiểm tra dữ liệu trước khi xuất catalog",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Sửa mô tả trực tiếp tại đây. Mã không tồn tại và ảnh còn thiếu "
                "có thể được bỏ qua, nhưng sẽ được báo trong kết quả."
            ),
            foreground="#555555",
            wraplength=900,
        ).pack(anchor="w", pady=(2, 10))

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Label(controls, text="Tìm mã:").pack(side="left")
        search = ttk.Entry(controls, textvariable=self.search_var, width=24)
        search.pack(side="left", padx=(6, 12))
        search.bind("<KeyRelease>", lambda _event: self._refresh_tree())
        ttk.Label(controls, text="Lọc:").pack(side="left")
        filter_box = ttk.Combobox(
            controls,
            textvariable=self.filter_var,
            values=self.FILTERS,
            state="readonly",
            width=27,
        )
        filter_box.pack(side="left", padx=(6, 12))
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_tree())
        ttk.Label(controls, textvariable=self.summary_var).pack(side="right")

        # Keep the action bar outside the resizable content area so the buttons
        # remain visible regardless of image size or pane resizing.
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Separator(footer, orient="horizontal").pack(fill="x", pady=(0, 10))

        footer_buttons = ttk.Frame(footer)
        footer_buttons.pack(fill="x")
        ttk.Button(
            footer_buttons,
            text="Hủy xuất",
            command=self._cancel,
        ).pack(side="left")
        ttk.Button(
            footer_buttons,
            text="Xuất file Excel",
            command=self._continue_incomplete,
        ).pack(side="right")
        self.save_button = ttk.Button(
            footer_buttons,
            text="Lưu cập nhật",
            command=self._save_and_next,
        )
        self.save_button.pack(side="right", padx=(0, 8))

        panes = ttk.PanedWindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(10, 10))

        left = ttk.Frame(panes)
        right = ttk.Frame(panes, padding=(12, 0, 0, 0))
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        self.tree = ttk.Treeview(
            left,
            columns=("code", "status"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("code", text="Mã sản phẩm")
        self.tree.heading("status", text="Trạng thái")
        self.tree.column("code", width=145, stretch=False)
        self.tree.column("status", width=230)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        header = ttk.Frame(right)
        header.pack(fill="x")
        ttk.Label(header, text="Mã:", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(header, textvariable=self.code_var).pack(side="left", padx=(5, 16))
        ttk.Label(header, textvariable=self.status_var, foreground="#9A6700").pack(side="left")

        ttk.Label(right, text="Mô tả tiếng Việt").pack(anchor="w", pady=(12, 3))
        self.vi_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.vi_text.pack(fill="x")
        ttk.Label(right, text="Mô tả tiếng Anh").pack(anchor="w", pady=(10, 3))
        self.en_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.en_text.pack(fill="x")
        for widget in (self.vi_text, self.en_text):
            widget.bind("<<Modified>>", self._on_modified)

        self.window.bind("<Control-Return>", lambda _event: self._save_and_next())

    def _matches_filter(self, issue: ExportPreflightItem) -> bool:
        selected = self.filter_var.get()
        if selected == "Thiếu mô tả VI":
            return issue.missing_vi
        if selected == "Thiếu mô tả EN":
            return issue.missing_en
        if selected == "Thiếu ảnh":
            return issue.missing_images
        if selected == "Mã không tồn tại":
            return issue.unknown_code
        return issue.has_issue

    def _refresh_tree(self, select_code: str = "") -> None:
        query = self.search_var.get().strip().casefold()
        self._visible = [
            issue
            for issue in self.issues
            if self._matches_filter(issue) and (not query or query in issue.code.casefold())
        ]
        self.tree.delete(*self.tree.get_children())
        selected_iid = ""
        for index, issue in enumerate(self._visible):
            iid = str(index)
            self.tree.insert("", "end", iid=iid, values=(issue.code, issue.status_text()))
            if select_code and issue.code == select_code:
                selected_iid = iid

        remaining = sum(1 for issue in self.issues if issue.has_issue)
        self.summary_var.set(f"{remaining} mục chưa hoàn chỉnh")
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            selected_index = int(selected_iid)
            self._load_issue(self._visible[selected_index])
        elif self._visible:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self._load_issue(self._visible[0])
        else:
            self._clear_editor()

    def _on_select(self, _event=None) -> None:
        if self._ignore_selection_event:
            self._ignore_selection_event = False
            return
        selection = self.tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if index >= len(self._visible):
            return
        target = self._visible[index]
        current = self._selected
        if target is current:
            return

        if self._dirty and current is not None:
            save_before_switch = messagebox.askyesnocancel(
                "Nội dung chưa được lưu",
                (
                    f"Bạn đã thay đổi mô tả của mã {current.code}.\n\n"
                    "Bạn có muốn lưu cập nhật trước khi chuyển sang mã khác không?"
                ),
                parent=self.window,
            )
            if save_before_switch is None:
                self._restore_tree_selection(current)
                return
            if save_before_switch and not self._save_current():
                self._restore_tree_selection(current)
                return

        self._load_issue(target)

    def _restore_tree_selection(self, issue: ExportPreflightItem) -> None:
        for index, visible_issue in enumerate(self._visible):
            if visible_issue is issue:
                iid = str(index)
                self._ignore_selection_event = True
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                return

    def _load_issue(self, issue: ExportPreflightItem) -> None:
        self._selected = issue
        self.code_var.set(issue.code)
        self.status_var.set(issue.status_text())
        self._set_text(self.vi_text, issue.description_vi)
        self._set_text(self.en_text, issue.description_en)
        editable = "disabled" if issue.unknown_code else "normal"
        self.vi_text.configure(state=editable)
        self.en_text.configure(state=editable)
        self.save_button.configure(state=editable)
        self._dirty = False

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")
        widget.edit_modified(False)

    def _on_modified(self, event) -> None:
        if event.widget.edit_modified():
            self._dirty = True
            event.widget.edit_modified(False)

    def _save_current(self, *, show_errors: bool = True) -> bool:
        issue = self._selected
        if issue is None or issue.unknown_code or not self._dirty:
            return True
        description_vi = self.vi_text.get("1.0", "end-1c").strip()
        description_en = self.en_text.get("1.0", "end-1c").strip()
        try:
            self.db.update_excel_descriptions_by_code(
                code=issue.code,
                description_vi=description_vi,
                description_en=description_en,
            )
        except Exception as exc:
            if show_errors:
                messagebox.showerror("Không thể lưu", str(exc), parent=self.window)
            return False

        issue.description_vi = description_vi
        issue.description_en = description_en
        issue.missing_vi = not bool(description_vi)
        issue.missing_en = not bool(description_en)
        self.status_var.set(issue.status_text())
        self._dirty = False
        return True

    def _save_and_next(self) -> None:
        if not self._save_current():
            return
        self._refresh_tree()

    def _select_next(self) -> None:
        children = list(self.tree.get_children())
        if not children:
            return
        selection = self.tree.selection()
        current = children.index(selection[0]) if selection and selection[0] in children else -1
        next_iid = children[min(current + 1, len(children) - 1)]
        self.tree.selection_set(next_iid)
        self.tree.focus(next_iid)
        self.tree.see(next_iid)

    def _continue_incomplete(self) -> None:
        if self._dirty:
            discard = messagebox.askyesno(
                "Nội dung chưa được lưu",
                (
                    "Nội dung bạn vừa nhập chưa được lưu và sẽ không được đưa vào file xuất.\n\n"
                    "Chọn “Có” để bỏ nội dung chưa lưu và tiếp tục xuất.\n"
                    "Chọn “Không” để quay lại và nhấn “Lưu cập nhật”."
                ),
                parent=self.window,
            )
            if not discard:
                return
        self.result = "continue"
        self.window.destroy()

    def _cancel(self) -> None:
        if self._dirty and not messagebox.askyesno(
            "Hủy xuất",
            "Bỏ các thay đổi chưa lưu và hủy xuất?",
            parent=self.window,
        ):
            return
        self.result = "cancel"
        self.window.destroy()

    def _clear_editor(self) -> None:
        self._selected = None
        self.code_var.set("")
        self.status_var.set("")
        self._set_text(self.vi_text, "")
        self._set_text(self.en_text, "")
        self.vi_text.configure(state="disabled")
        self.en_text.configure(state="disabled")
        self.save_button.configure(state="disabled")
