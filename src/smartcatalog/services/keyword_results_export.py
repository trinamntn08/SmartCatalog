"""Independent workbook report/copy export with literal user text."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from smartcatalog.domain.pdf_search import ExportResult, SearchResult
from smartcatalog.loader.keyword_workbook import column_number
from smartcatalog.services.pdf_annotation_export import staged_output, validate_output
from smartcatalog.services.pdf_keyword_search import check_cancel, verify_sources


def literal_cell(cell, value) -> None:
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"


def export_keyword_results(result: SearchResult, path: Path, *, copy_workbook: bool = False,
                           overwrite: bool = False, cancel=None) -> ExportResult:
    path = validate_output(result, path, ".xlsx", overwrite)
    verify_sources(result)
    check_cancel(cancel)
    warnings = []
    if copy_workbook:
        config = result.source.workbook
        if config is None:
            raise ValueError("Chế độ bản sao cần nguồn Excel.")
        book = load_workbook(config.path)
    else:
        book = Workbook()
    try:
        if copy_workbook:
            sheet = book[config.sheet]
            for row in result.rows:
                check_cancel(cancel)
                cell = sheet.cell(row.row.source_row, column_number(config.result_column))
                literal_cell(cell, ", ".join(map(str, row.pages)))
            warnings.append("Đã lưu bản sao bằng openpyxl; kiểm tra đối tượng Excel nâng cao. Tệp nguồn được giữ nguyên.")
        else:
            sheet = book.active
            sheet.title = "PDF Search"
            sheet.append(["Dòng / ID", "Trang tính", "Từ khóa", "Ghi chú", "Trang PDF", "Số lần", "Trạng thái", "Cảnh báo"])
            for row in result.rows:
                check_cancel(cancel)
                values = (row.row.source_row, row.row.sheet, row.row.keyword, row.row.note,
                          ", ".join(map(str, row.pages)), len(row.hits),
                          "Tìm thấy" if row.hits else "Không tìm thấy", "\n".join(row.row.warnings))
                for col, value in enumerate(values, 1):
                    literal_cell(sheet.cell(sheet.max_row + 1 if col == 1 else sheet.max_row, col), value)
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="245C75")
            for col, width in {"A": 14, "B": 18, "C": 25, "D": 45, "E": 24, "F": 12, "G": 20, "H": 60}.items():
                sheet.column_dimensions[col].width = width
            info = book.create_sheet("Thông tin")
            info.append(["PDF", str(result.pdf_path)])
            for warning in result.warnings:
                info.append(["Cảnh báo", warning])
        with staged_output(path, overwrite) as temporary:
            check_cancel(cancel)
            book.save(temporary)
            with temporary.open("rb") as stream:
                check = load_workbook(stream, read_only=True)
                check.close()
            verify_sources(result)
            check_cancel(cancel)
    finally:
        book.close()
    return ExportResult(path, tuple(warnings))
