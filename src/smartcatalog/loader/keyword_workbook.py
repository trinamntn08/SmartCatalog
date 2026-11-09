"""Read keyword rows without modifying the source workbook."""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

from smartcatalog.domain.pdf_search import KeywordInput, KeywordRow, SearchCancelled, WorkbookInput


def file_digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def column_number(value: str) -> int:
    try:
        index = column_index_from_string(value.strip().upper())
    except (ValueError, AttributeError):
        raise ValueError("Cột Excel phải là chữ A..XFD.") from None
    if not 1 <= index <= 16384:
        raise ValueError("Cột Excel phải là chữ A..XFD.")
    return index


def workbook_sheets(path: Path) -> tuple[str, ...]:
    with Path(path).open("rb") as stream:
        book = load_workbook(stream, read_only=True)
        try:
            return tuple(book.sheetnames)
        finally:
            book.close()


def read_keyword_workbook(config: WorkbookInput, *, cancel=None) -> KeywordInput:
    if config.path.suffix.lower() != ".xlsx":
        raise ValueError("Vui lòng chọn tệp .xlsx.")
    if not 1 <= config.first_row <= 1048576:
        raise ValueError("Dòng bắt đầu không hợp lệ.")
    key_col = column_number(config.keyword_column)
    note_col = column_number(config.note_column) if config.note_column.strip() else None
    result_col = column_number(config.result_column)
    if result_col in (key_col, note_col):
        raise ValueError("Cột kết quả phải khác cột từ khóa và ghi chú.")
    before = file_digest(config.path)
    book = load_workbook(config.path, read_only=True, data_only=False)
    cached = None
    try:
        cached = load_workbook(config.path, read_only=True, data_only=True)
        if config.sheet not in book.sheetnames:
            raise ValueError("Trang tính không tồn tại.")
        sheet = book[config.sheet]
        values = cached[config.sheet]
        rows = []
        warnings = []
        skipped = 0
        max_col = max(key_col, note_col or 1, result_col)
        original_rows = sheet.iter_rows(min_row=config.first_row, max_col=max_col)
        cached_rows = values.iter_rows(min_row=config.first_row, max_col=max_col)
        for number, (cells, cache) in enumerate(zip(original_rows, cached_rows), config.first_row):
            if cancel and cancel():
                raise SearchCancelled()
            row_warnings = []
            def display(index):
                cell = cells[index - 1]
                value = cell.value
                if cell.data_type == "f":
                    value = cache[index - 1].value
                    if value is None:
                        row_warnings.append(f"Dòng {number}: công thức chưa có giá trị lưu sẵn.")
                if cell.data_type == "e":
                    row_warnings.append(f"Dòng {number}: ô lỗi Excel {cell.coordinate}.")
                    return ""
                if value is None:
                    return ""
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    row_warnings.append(f"Dòng {number}: ô số {cell.coordinate}; kiểm tra số 0 đầu và độ chính xác.")
                    if isinstance(value, float) and value.is_integer():
                        value = int(value)
                return str(value)
            keyword = display(key_col).strip()
            note = display(note_col) if note_col else ""
            if not keyword:
                skipped += 1
                warnings.extend(row_warnings)
                continue
            if cells[result_col - 1].value is not None:
                row_warnings.append(f"Dòng {number}: bản sao sẽ thay giá trị cột kết quả.")
            rows.append(KeywordRow(number, keyword, note, config.sheet, tuple(row_warnings)))
        if skipped:
            warnings.append(f"Bỏ qua {skipped} dòng không có từ khóa.")
        if not rows:
            raise ValueError("Không có từ khóa hợp lệ. Kiểm tra trang tính, cột và dòng bắt đầu.")
        if file_digest(config.path) != before:
            raise ValueError("Excel đã thay đổi khi đọc. Vui lòng đọc lại.")
        return KeywordInput(tuple(rows), tuple(warnings), config, before)
    finally:
        book.close()
        if cached is not None:
            cached.close()
