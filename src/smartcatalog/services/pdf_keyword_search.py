"""Search a normalized character stream and retain the same geometry for all outputs."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import re
from typing import Callable

import fitz

from smartcatalog.domain.pdf_search import (
    KeywordInput, KeywordResult, PdfHit, SearchCancelled, SearchResult,
)
from smartcatalog.loader.keyword_workbook import file_digest


def check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel and cancel():
        raise SearchCancelled()


def normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def page_character_map(page):
    text = []
    geometry = []
    line_id = 0
    for block in page.get_text("rawdict", sort=True)["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                for char in span["chars"]:
                    for folded in char["c"].casefold():
                        if folded.isspace():
                            if text and text[-1] != " ":
                                text.append(" ")
                                geometry.append(None)
                        else:
                            text.append(folded)
                            geometry.append((line_id, char["bbox"]))
            if text and text[-1] != " ":
                text.append(" ")
                geometry.append(None)
            line_id += 1
    return "".join(text), geometry


def code_character(char: str) -> bool:
    return bool(char) and (char.isalnum() or char in "-_./")


def search_keywords(pdf_path: Path, source: KeywordInput, *, whole_code: bool = False,
                    cancel: Callable[[], bool] | None = None,
                    progress: Callable[[int, int], None] | None = None) -> SearchResult:
    path = Path(pdf_path).resolve()
    check_cancel(cancel)
    if not source.rows:
        raise ValueError("Không có từ khóa để tìm.")
    digest = file_digest(path)
    needles = dict.fromkeys(normalize_query(row.keyword) for row in source.rows)
    if "" in needles:
        raise ValueError("Từ khóa trống không hợp lệ.")
    patterns = {needle: re.compile(re.escape(needle)) for needle in needles}
    found = {needle: [] for needle in needles}
    text_pages = 0
    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF được bảo vệ bằng mật khẩu; hãy dùng bản đã mở khóa.")
        total = len(doc)
        for page_index, page in enumerate(doc):
            check_cancel(cancel)
            text, geometry = page_character_map(page)
            text_pages += bool(text.strip())
            for needle, pattern in patterns.items():
                check_cancel(cancel)
                for match in pattern.finditer(text):
                    a, b = match.span()
                    if whole_code and (code_character(text[a-1:a] if a else "") or code_character(text[b:b+1])):
                        continue
                    lines = OrderedDict()
                    for entry in geometry[a:b]:
                        if entry is None:
                            continue
                        line, box = entry
                        if line in lines:
                            lines[line] |= fitz.Rect(box)
                        else:
                            lines[line] = fitz.Rect(box)
                    if lines:
                        found[needle].append(PdfHit(page_index, tuple(tuple(rect) for rect in lines.values())))
            if progress:
                progress(page_index + 1, total)
    check_cancel(cancel)
    if file_digest(path) != digest:
        raise ValueError("PDF đã thay đổi trong khi tìm. Vui lòng chạy lại.")
    warnings = list(source.warnings)
    if not text_pages:
        warnings.append("PDF không có văn bản có thể tìm; cần OCR trước khi sử dụng.")
    elif text_pages < total:
        warnings.append(f"{total - text_pages} trang không có văn bản; nội dung ảnh không được tìm bằng OCR.")
    warnings.append("Tìm không phân biệt hoa/thường; gộp khoảng trắng và xuống dòng; giữ nguyên dấu gạch nối.")
    rows = tuple(KeywordResult(row, tuple(found[normalize_query(row.keyword)])) for row in source.rows)
    return SearchResult(path, digest, source, rows, total, tuple(warnings))


def verify_sources(result: SearchResult) -> None:
    if file_digest(result.pdf_path) != result.pdf_digest:
        raise ValueError("PDF đã thay đổi. Vui lòng tìm lại trước khi xuất.")
    if result.source.workbook and file_digest(result.source.workbook.path) != result.source.workbook_digest:
        raise ValueError("Excel đã thay đổi. Vui lòng đọc và tìm lại trước khi xuất.")
