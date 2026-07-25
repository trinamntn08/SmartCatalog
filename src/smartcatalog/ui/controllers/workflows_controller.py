from __future__ import annotations

import datetime
import threading
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from smartcatalog.loader.pdf_loader import build_or_update_db_from_pdf
from smartcatalog.services.backup_service import backup_catalog
from smartcatalog.services.catalog_export import CatalogExportOptions, export_catalog
from smartcatalog.services.excel_catalog_import import import_excel_catalog
from smartcatalog.services.export_preflight import prepare_export_preflight
from smartcatalog.services.workbook_product_reader import read_workbook_products
from smartcatalog.ui.export_review_dialog import ExportReviewDialog
from smartcatalog.utils.description_dictionary import import_dictionary_into_db
from smartcatalog.utils.post_processing import (
    DEFAULT_SHEET_NAME as POST_PROCESSING_SHEET_NAME,
)
from smartcatalog.utils.ui_dispatch import dispatch_to_tk


def _safe_ui(root: tk.Misc, fn) -> None:
    dispatch_to_tk(root, fn)


class WorkflowsControllerMixin:
    def on_import_pdf_catalog(self) -> None:
        """
        Show existing catalog PDFs, ask whether to load a new one, then build/update DB.
        """
        # show existing catalog PDFs
        pdf_dir = self.state.data_dir / "catalog_pdfs"
        existing = []
        try:
            if pdf_dir.exists():
                existing = sorted([p.name for p in pdf_dir.glob("*.pdf")])
            if existing:
                messagebox.showinfo(
                    "PDF danh mục đã có",
                    "Đã có trong CSDL:\n" + "\n".join(existing),
                )
        except Exception:
            pass

        use_new = messagebox.askyesno(
            "Tải PDF mới?",
            "Bạn có muốn tải một file PDF mới không?",
        )

        if use_new or not self.state.catalog_pdf_path:
            path = filedialog.askopenfilename(
                title="Chọn PDF danh mục",
                initialdir=str(pdf_dir) if pdf_dir.exists() else None,
                filetypes=[("Tệp PDF", "*.pdf"), ("Tất cả tệp", "*.*")],
            )
            if not path:
                return
            self.state.set_catalog_pdf(path)
            _safe_ui(self.root, self._update_pdf_tools_label)
            self._set_status(f"Đã chọn PDF: {path}")
        else:
            path = str(self.state.catalog_pdf_path)
            if not path:
                return
            run_again = messagebox.askyesno(
                "Cập nhật lại CSDL?",
                "Dùng PDF hiện tại và cập nhật lại?",
            )
            if not run_again:
                self._set_status("Đã hủy cập nhật PDF.")
                return
            self._set_status(f"Đang dùng PDF hiện tại: {path}")

        # From here: we have a PDF path
        def work():
            apply_all_choice: Optional[bool] = None

            def on_existing_item_decision(code: str) -> bool:
                nonlocal apply_all_choice
                if apply_all_choice is not None:
                    return bool(apply_all_choice)

                done = threading.Event()
                result: dict[str, bool] = {
                    "update": False,
                    "apply_all": False,
                }

                def ask_on_ui_thread():
                    update, apply_all = self._ask_update_existing_item_dialog(code)
                    result["update"] = bool(update)
                    result["apply_all"] = bool(apply_all)
                    done.set()

                _safe_ui(self.root, ask_on_ui_thread)
                done.wait()
                if result["apply_all"]:
                    apply_all_choice = result["update"]
                return result["update"]

            build_or_update_db_from_pdf(
                self.state,
                None,
                self.status_message,
                on_existing_item_decision=on_existing_item_decision,
            )
            _safe_ui(self.root, self.refresh_items)
            _safe_ui(self.root, lambda: self._set_status("✅ Cập nhật CSDL từ PDF xong"))

        self._run_bg("⏳ Đang tạo/cập nhật CSDL từ PDF...", work)

    def _ask_update_existing_item_dialog(self, code: str) -> tuple[bool, bool]:
        """
        Ask what to do when an item code already exists.
        Returns: (update_existing, apply_for_all_existing)
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Mã đã tồn tại")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"Mã sản phẩm '{code}' đã có trong CSDL.\nBạn muốn cập nhật/ghi đè dữ liệu hiện tại không?",
            justify="left",
        ).pack(anchor="w")

        apply_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Áp dụng cho tất cả mã đã tồn tại",
            variable=apply_all_var,
        ).pack(anchor="w", pady=(10, 0))

        result = {"update": False}

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(12, 0))

        def choose_update():
            result["update"] = True
            dlg.destroy()

        def choose_skip():
            result["update"] = False
            dlg.destroy()

        ttk.Button(btns, text="Cập nhật/Ghi đè", command=choose_update).pack(side="left")
        ttk.Button(btns, text="Giữ nguyên (bỏ qua)", command=choose_skip).pack(side="left", padx=(8, 0))

        dlg.protocol("WM_DELETE_WINDOW", choose_skip)
        dlg.wait_window()
        return bool(result["update"]), bool(apply_all_var.get())

    def on_backup_data(self) -> None:
        """
        Backup SQLite DB and assets folder to a user-chosen directory.
        """
        if not self.state or not self.state.db_path:
            messagebox.showwarning("Thiếu CSDL", "Không tìm thấy đường dẫn CSDL để backup.")
            return

        db_path = Path(self.state.db_path)
        if not db_path.exists():
            messagebox.showwarning("Thiếu CSDL", f"Không tìm thấy file DB: {db_path}")
            return

        dest_root = filedialog.askdirectory(
            title="Chọn thư mục lưu backup",
            mustexist=True,
        )
        if not dest_root:
            return

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        backup_dir = Path(dest_root) / f"smartcatalog_backup_{ts}"

        def work():
            try:
                manifest = backup_catalog(
                    database_path=db_path,
                    assets_dir=self.state.assets_dir,
                    catalog_pdfs_dir=self.state.data_dir / "catalog_pdfs",
                    settings_path=self.state.settings_path,
                    backup_dir=backup_dir,
                )

                _safe_ui(
                    self.root,
                    lambda: messagebox.showinfo(
                        "Backup xong",
                        f"Đã backup CSDL và assets vào:\n{manifest.backup_dir}",
                    ),
                )
            except Exception as exc:
                _safe_ui(
                    self.root,
                    lambda exc=exc: messagebox.showerror(
                        "Backup lỗi",
                        f"Không thể backup: {exc}",
                    ),
                )

        self._run_bg("⏳ Đang backup CSDL...", work)

    def on_import_excel_catalog(self) -> None:
        if not self.state.db:
            messagebox.showwarning("Thiếu CSDL", "Vui lòng tạo/tải CSDL trước (từ PDF).")
            return

        xlsx_path = filedialog.askopenfilename(
            title="Chọn file Excel",
            filetypes=[("Tệp Excel", "*.xlsx *.xls"), ("Tất cả tệp", "*.*")],
        )
        if not xlsx_path:
            return

        def work():
            apply_all_choice: Optional[bool] = None
            decision_by_code: dict[str, bool] = {}

            def should_update_existing(code: str) -> bool:
                nonlocal apply_all_choice
                code_key = str(code or "").strip()
                if not code_key:
                    return False
                if code_key in decision_by_code:
                    return bool(decision_by_code[code_key])
                if apply_all_choice is not None:
                    decision_by_code[code_key] = bool(apply_all_choice)
                    return bool(apply_all_choice)

                done = threading.Event()
                result: dict[str, bool] = {"update": False, "apply_all": False}

                def ask_on_ui_thread():
                    update, apply_all = self._ask_update_existing_item_dialog(code_key)
                    result["update"] = bool(update)
                    result["apply_all"] = bool(apply_all)
                    done.set()

                _safe_ui(self.root, ask_on_ui_thread)
                done.wait()
                if result["apply_all"]:
                    apply_all_choice = result["update"]
                decision_by_code[code_key] = result["update"]
                return bool(result["update"])

            def report_progress(i: int, total: int, updated: int, missing: int):
                _safe_ui(
                    self.root,
                    lambda: self._set_status(
                        f"⏳ Cập nhật Excel {i}/{total} | đã cập nhật={updated} | thiếu={missing}"
                    ),
                )

            result = import_excel_catalog(
                xlsx_path,
                db=self.state.db,
                assets_dir=self.state.assets_dir,
                should_update_existing=should_update_existing,
                progress_callback=report_progress,
            )
            _safe_ui(self.root, self.refresh_items)
            _safe_ui(
                self.root,
                lambda: self._set_status(
                    f"✅ Nhập Excel xong | tạo mới={result.created_new} | đã cập nhật={result.updated} | bỏ qua={result.skipped_existing} | thiếu={result.missing} | ảnh={result.images_updated}"
                ),
            )
            _safe_ui(
                self.root,
                lambda: messagebox.showinfo(
                    "Nhập Excel xong",
                    "Số dòng đọc: {total}\nTạo mới: {created_new}\nĐã cập nhật: {updated}\nBỏ qua mã đã tồn tại: {skipped_existing}\nMã thiếu: {missing}\n"
                    "Ảnh đã gắn: {images_updated}\nẢnh thiếu: {images_missing}\n"
                    "Ảnh tìm thấy trong file: {image_rows_total}".format(
                        total=result.total,
                        created_new=result.created_new,
                        updated=result.updated,
                        skipped_existing=result.skipped_existing,
                        missing=result.missing,
                        images_updated=result.images_updated,
                        images_missing=result.images_missing,
                        image_rows_total=result.image_rows_total,
                    ),
                ),
            )
            if result.missing_codes:
                _safe_ui(
                    self.root,
                    lambda: self._show_missing_codes(list(result.missing_codes)),
                )

        self._run_bg("⏳ Đang cập nhật mô tả và ảnh từ Excel...", work)

    def on_export_catalog(self) -> None:
        if not self.state.db:
            messagebox.showwarning(
                "Thiếu CSDL",
                "Vui lòng tạo/tải CSDL trước (từ PDF).",
            )
            return
        xlsx_path = filedialog.askopenfilename(
            title="Chọn file Excel",
            filetypes=[("Tệp Excel", "*.xlsx *.xls"), ("Tất cả tệp", "*.*")],
        )
        if not xlsx_path:
            return
        xlsx_path = str(xlsx_path)
        if self._open_search_options_popup() is False:
            return

        options = CatalogExportOptions(
            include_description_en=bool(self.var_export_desc_en.get()),
            include_description_vi=bool(self.var_export_desc_vi.get()),
            preserve_image_order=bool(
                self.var_export_images_in_ui_order.get()
            ),
        )

        def work():
            import_dictionary_into_db(
                self.state.db,
                self.state.project_dir,
            )
            rows = read_workbook_products(xlsx_path)
            preflight = prepare_export_preflight(
                rows,
                db=self.state.db,
                include_description_vi=options.include_description_vi,
                include_description_en=options.include_description_en,
            )
            issues = [item for item in preflight.issues if item.has_issue]
            if issues:
                review_done = threading.Event()
                review_result = {"action": "cancel"}

                def show_preflight_review() -> None:
                    try:
                        review_result["action"] = ExportReviewDialog(
                            self.root,
                            self.state.db,
                            issues,
                        ).show()
                    finally:
                        review_done.set()

                _safe_ui(self.root, show_preflight_review)
                review_done.wait()
                if review_result["action"] != "continue":
                    _safe_ui(
                        self.root,
                        lambda: self._set_status("Đã hủy xuất catalog."),
                    )
                    return

            result = export_catalog(
                xlsx_path,
                preflight.rows,
                db=self.state.db,
                project_dir=self.state.project_dir,
                options=options,
            )
            _safe_ui(
                self.root,
                lambda: self._show_export_result(
                    xlsx_path=result.xlsx_path,
                    matched=result.matched,
                    total=result.total,
                    images_found=result.images_found,
                    missing_vi=result.missing_vi,
                    missing_en=result.missing_en,
                    missing_images=result.missing_images,
                    missing_codes=list(result.missing_codes),
                ),
            )
            _safe_ui(
                self.root,
                lambda: self._set_status(
                    f"✅ Xuất Excel: khớp {result.matched}/{result.total} | "
                    f"thiếu VI={result.missing_vi}, EN={result.missing_en}, "
                    f"ảnh={result.missing_images}, mã={len(result.missing_codes)} | "
                    f"tạo {POST_PROCESSING_SHEET_NAME}"
                ),
            )

        self._run_bg("⏳ Extracting images by code...", work)
