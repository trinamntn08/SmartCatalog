from __future__ import annotations

from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from smartcatalog.services.export_preflight import (
    ExportPreflightItem,
    save_export_preflight_changes,
    validate_export_preflight_image,
)


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
        self._image_thumb_refs: list[ImageTk.PhotoImage] = []
        self._image_thumb_cells: list[tk.Frame] = []
        self._selected_image_index: Optional[int] = None
        self._drag_source_index: Optional[int] = None
        self._drag_start_xy = (0, 0)
        self._drag_active = False

        self.window = tk.Toplevel(parent)
        self.window.title("Kiểm tra dữ liệu trước khi xuất")
        self.window.transient(parent)
        self.window.geometry("980x720")
        self.window.minsize(820, 640)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value=self.FILTERS[0])
        self.summary_var = tk.StringVar()
        self.code_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.image_count_var = tk.StringVar()

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
                "Chỉnh sửa mô tả và hình ảnh tại đây, sau đó nhấn “Lưu cập nhật”. "
                "Mã không tồn tại và dữ liệu còn thiếu có thể được bỏ qua, nhưng "
                "sẽ được báo trong kết quả."
            ),
            foreground="#555555",
            wraplength=900,
        ).pack(anchor="w", pady=(2, 10))

        controls = ttk.Frame(outer)
        controls.pack(fill="x")
        ttk.Label(controls, text="Tìm mã:").pack(side="left")
        search = ttk.Entry(controls, textvariable=self.search_var, width=24)
        search.pack(side="left", padx=(6, 12))
        search.bind("<KeyRelease>", self._on_filter_change)
        ttk.Label(controls, text="Lọc:").pack(side="left")
        filter_box = ttk.Combobox(
            controls,
            textvariable=self.filter_var,
            values=self.FILTERS,
            state="readonly",
            width=27,
        )
        filter_box.pack(side="left", padx=(6, 12))
        filter_box.bind("<<ComboboxSelected>>", self._on_filter_change)
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

        ttk.Label(right, text="Ảnh sản phẩm").pack(anchor="w", pady=(10, 3))
        self.image_preview_frame = ttk.Frame(right, height=230)
        self.image_preview_frame.pack(fill="both", expand=True)
        self.image_preview_frame.pack_propagate(False)

        image_buttons = ttk.Frame(self.image_preview_frame)
        image_buttons.pack(side="bottom", fill="x", pady=(6, 0))
        self.add_image_button = ttk.Button(
            image_buttons,
            text="Thêm ảnh",
            command=self._add_images,
        )
        self.add_image_button.pack(side="left")
        self.remove_image_button = ttk.Button(
            image_buttons,
            text="Xóa ảnh",
            command=self._remove_image,
        )
        self.remove_image_button.pack(side="left", padx=(6, 0))
        ttk.Label(image_buttons, textvariable=self.image_count_var).pack(side="right")

        image_thumbs_host = ttk.Frame(self.image_preview_frame)
        image_thumbs_host.pack(fill="both", expand=True)
        self.image_thumbs_canvas = tk.Canvas(
            image_thumbs_host,
            highlightthickness=0,
        )
        image_scrollbar = ttk.Scrollbar(
            image_thumbs_host,
            orient="vertical",
            command=self.image_thumbs_canvas.yview,
        )
        self.image_thumbs_canvas.configure(yscrollcommand=image_scrollbar.set)
        self.image_thumbs_canvas.pack(side="left", fill="both", expand=True)
        image_scrollbar.pack(side="right", fill="y")
        self.image_thumbs_inner = ttk.Frame(self.image_thumbs_canvas)
        self.image_thumbs_window = self.image_thumbs_canvas.create_window(
            (0, 0),
            window=self.image_thumbs_inner,
            anchor="nw",
        )
        self.image_thumbs_inner.bind(
            "<Configure>",
            lambda _event: self.image_thumbs_canvas.configure(
                scrollregion=self.image_thumbs_canvas.bbox("all")
            ),
        )
        self.image_thumbs_canvas.bind(
            "<Configure>",
            lambda event: self.image_thumbs_canvas.itemconfigure(
                self.image_thumbs_window,
                width=event.width,
            ),
        )

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

    def _on_filter_change(self, _event=None) -> None:
        if not self._dirty:
            self._refresh_tree()

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
                    f"Bạn đã thay đổi nội dung của mã {current.code}.\n\n"
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
            if not save_before_switch:
                self._discard_current_changes()

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
        self._set_text(self.en_text, issue.effective_description_en)
        self._refresh_image_panel(issue.image_paths)
        self.add_image_button.configure(state="normal")
        self.vi_text.configure(state="normal")
        self.en_text.configure(state="normal")
        self.save_button.configure(state="normal")
        self._dirty = False

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")
        widget.edit_modified(False)

    def _refresh_image_panel(
        self,
        image_paths: list[str],
        *,
        selected_index: int = 0,
    ) -> None:
        for child in self.image_thumbs_inner.winfo_children():
            child.destroy()
        self._image_thumb_refs.clear()
        self._image_thumb_cells.clear()
        self._selected_image_index = None
        self.image_count_var.set(f"{len(image_paths)} ảnh")
        if not image_paths:
            placeholder = ttk.Label(
                self.image_thumbs_inner,
                text="Không có ảnh hiện có",
                anchor="center",
            )
            placeholder.pack(fill="both", expand=True, pady=50)
            self._update_image_action_states(0)
            return

        columns = 4
        for column in range(columns):
            self.image_thumbs_inner.columnconfigure(column, weight=1)
        for index, path in enumerate(image_paths):
            cell = tk.Frame(self.image_thumbs_inner, borderwidth=0, relief="flat")
            cell.grid(
                row=index // columns,
                column=index % columns,
                padx=4,
                pady=4,
                sticky="nsew",
            )
            self._image_thumb_cells.append(cell)
            setattr(cell, "_image_index", index)
            try:
                with Image.open(path) as source:
                    thumbnail = source.convert("RGBA")
                    thumbnail.thumbnail((96, 96))
                    tk_thumbnail = ImageTk.PhotoImage(thumbnail)
                self._image_thumb_refs.append(tk_thumbnail)
                image_widget = ttk.Label(cell, image=tk_thumbnail)
            except (
                OSError,
                ValueError,
                tk.TclError,
                Image.DecompressionBombError,
            ):
                image_widget = ttk.Label(cell, text="[Không đọc được]", width=11)
            image_widget.pack(fill="both", expand=True)
            setattr(image_widget, "_image_index", index)
            for widget in (cell, image_widget):
                widget.bind(
                    "<ButtonPress-1>",
                    lambda event, target=index: self._on_image_drag_start(
                        event,
                        target,
                    ),
                )
                widget.bind(
                    "<B1-Motion>",
                    self._on_image_drag_motion,
                )
                widget.bind(
                    "<ButtonRelease-1>",
                    self._on_image_drag_release,
                )

        selected_index = min(max(0, selected_index), len(image_paths) - 1)
        self._select_image(selected_index)

    def _select_image(self, index: int) -> None:
        issue = self._selected
        if issue is None or index < 0 or index >= len(issue.image_paths):
            return
        self._selected_image_index = index
        for cell_index, cell in enumerate(self._image_thumb_cells):
            selected = cell_index == index
            cell.configure(
                borderwidth=(2 if selected else 0),
                relief=("solid" if selected else "flat"),
            )
        self._update_image_action_states(len(issue.image_paths))

    def _update_image_action_states(self, image_count: int) -> None:
        index = self._selected_image_index
        has_selection = index is not None and 0 <= index < image_count
        self.remove_image_button.configure(
            state=("normal" if has_selection else "disabled")
        )

    def _add_images(self) -> None:
        issue = self._selected
        if issue is None:
            return
        selected_paths = filedialog.askopenfilenames(
            parent=self.window,
            title="Chọn một hoặc nhiều ảnh",
            filetypes=[
                ("Tệp ảnh", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Tất cả tệp", "*.*"),
            ],
        )
        if not selected_paths:
            return
        try:
            validated_paths = [
                validate_export_preflight_image(path)
                for path in selected_paths
            ]
        except Exception as exc:
            messagebox.showerror(
                "Không thể thêm ảnh",
                str(exc),
                parent=self.window,
            )
            return

        first_new_index = len(issue.image_paths)
        for path in validated_paths:
            if path not in issue.image_paths:
                issue.image_paths.append(path)
        if len(issue.image_paths) == first_new_index:
            return
        self._dirty = True
        self.status_var.set(f"{issue.status_text()} (chưa lưu)")
        self._refresh_image_panel(
            issue.image_paths,
            selected_index=min(first_new_index, len(issue.image_paths) - 1),
        )

    def _remove_image(self) -> None:
        issue = self._selected
        index = self._selected_image_index
        if issue is None or index is None:
            return
        if index >= len(issue.image_paths):
            return
        del issue.image_paths[index]
        self._dirty = True
        self.status_var.set(f"{issue.status_text()} (chưa lưu)")
        self._refresh_image_panel(
            issue.image_paths,
            selected_index=max(0, index - 1),
        )

    def _on_image_drag_start(self, event, index: int) -> None:
        self._drag_source_index = index
        self._drag_start_xy = (
            int(getattr(event, "x_root", 0)),
            int(getattr(event, "y_root", 0)),
        )
        self._drag_active = False
        self._select_image(index)

    def _on_image_drag_motion(self, event) -> None:
        if self._drag_source_index is None:
            return
        x_root = int(getattr(event, "x_root", 0))
        y_root = int(getattr(event, "y_root", 0))
        start_x, start_y = self._drag_start_xy
        if abs(x_root - start_x) + abs(y_root - start_y) >= 8:
            self._drag_active = True
            self.image_thumbs_canvas.configure(cursor="fleur")
            target_index = self._image_index_at(x_root, y_root)
            for index, cell in enumerate(self._image_thumb_cells):
                if index == target_index:
                    cell.configure(borderwidth=3, relief="ridge")
                elif index == self._drag_source_index:
                    cell.configure(borderwidth=2, relief="solid")
                else:
                    cell.configure(borderwidth=0, relief="flat")

    def _on_image_drag_release(self, event) -> None:
        source_index = self._drag_source_index
        drag_active = self._drag_active
        self._drag_source_index = None
        self._drag_active = False
        self.image_thumbs_canvas.configure(cursor="")
        if source_index is None or not drag_active:
            return
        target_index = self._image_index_at(
            int(getattr(event, "x_root", 0)),
            int(getattr(event, "y_root", 0)),
        )
        if target_index is not None:
            self._reorder_image(source_index, target_index)
        else:
            self._select_image(source_index)

    def _image_index_at(self, x_root: int, y_root: int) -> Optional[int]:
        try:
            canvas_x = int(self.image_thumbs_canvas.winfo_rootx())
            canvas_y = int(self.image_thumbs_canvas.winfo_rooty())
            canvas_right = canvas_x + int(self.image_thumbs_canvas.winfo_width())
            canvas_bottom = canvas_y + int(self.image_thumbs_canvas.winfo_height())
            if not (
                canvas_x <= x_root <= canvas_right
                and canvas_y <= y_root <= canvas_bottom
            ):
                return None
            widget = self.window.winfo_containing(x_root, y_root)
        except tk.TclError:
            return None

        current = widget
        while current is not None:
            index = getattr(current, "_image_index", None)
            if index is not None:
                return int(index)
            current = getattr(current, "master", None)

        nearest: tuple[int, int] | None = None
        for index, cell in enumerate(self._image_thumb_cells):
            try:
                center_x = int(cell.winfo_rootx()) + int(cell.winfo_width()) // 2
                center_y = int(cell.winfo_rooty()) + int(cell.winfo_height()) // 2
            except tk.TclError:
                continue
            distance = abs(x_root - center_x) + abs(y_root - center_y)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, index)
        return nearest[1] if nearest is not None else None

    def _reorder_image(self, source_index: int, target_index: int) -> None:
        issue = self._selected
        if issue is None:
            return
        if not (
            0 <= source_index < len(issue.image_paths)
            and 0 <= target_index < len(issue.image_paths)
        ):
            return
        moved = issue.image_paths.pop(source_index)
        issue.image_paths.insert(target_index, moved)
        if source_index == target_index:
            return
        self._dirty = True
        self.status_var.set(f"{issue.status_text()} (chưa lưu)")
        self._refresh_image_panel(issue.image_paths, selected_index=target_index)

    def _discard_current_changes(self) -> None:
        issue = self._selected
        if issue is None:
            return
        issue.image_paths = list(issue.persisted_image_paths)
        issue.missing_images = not bool(issue.image_paths)
        self._dirty = False

    def _on_modified(self, event) -> None:
        if event.widget.edit_modified():
            self._dirty = True
            event.widget.edit_modified(False)

    def _save_current(self, *, show_errors: bool = True) -> bool:
        issue = self._selected
        if issue is None or not self._dirty:
            return True
        description_vi = self.vi_text.get("1.0", "end-1c").strip()
        description_en = self.en_text.get("1.0", "end-1c").strip()
        try:
            save_export_preflight_changes(
                issue,
                db=self.db,
                description_vi=description_vi,
                description_en=description_en,
                image_paths=list(issue.image_paths),
            )
        except Exception as exc:
            if show_errors:
                messagebox.showerror("Không thể lưu", str(exc), parent=self.window)
            return False

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
            self._discard_current_changes()
        self.result = "continue"
        self.window.destroy()

    def _cancel(self) -> None:
        if self._dirty and not messagebox.askyesno(
            "Hủy xuất",
            "Bỏ các thay đổi chưa lưu và hủy xuất?",
            parent=self.window,
        ):
            return
        self._discard_current_changes()
        self.result = "cancel"
        self.window.destroy()

    def _clear_editor(self) -> None:
        self._selected = None
        self.code_var.set("")
        self.status_var.set("")
        self._set_text(self.vi_text, "")
        self._set_text(self.en_text, "")
        self._refresh_image_panel([])
        self.vi_text.configure(state="disabled")
        self.en_text.configure(state="disabled")
        self.add_image_button.configure(state="disabled")
        self.remove_image_button.configure(state="disabled")
        self.save_button.configure(state="disabled")
