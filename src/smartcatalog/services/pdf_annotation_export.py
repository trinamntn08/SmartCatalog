"""Staged annotated PDF output and shared annotation placement for preview."""
from __future__ import annotations

from contextlib import contextmanager
from html import escape
import os
from pathlib import Path
import tempfile

import fitz

from smartcatalog.domain.pdf_search import ExportResult, NoteOptions, SearchResult
from smartcatalog.services.pdf_keyword_search import check_cancel, verify_sources


def validate_output(result: SearchResult, path: Path, suffix: str, overwrite: bool) -> Path:
    path = Path(path).resolve()
    sources = [result.pdf_path]
    if result.source.workbook:
        sources.append(result.source.workbook.path.resolve())
    for source in sources:
        if path == source or (path.exists() and os.path.samefile(path, source)):
            raise ValueError("Không được ghi đè tệp nguồn. Hãy chọn tên tệp mới.")
    if path.suffix.lower() != suffix:
        raise ValueError(f"Tệp kết quả phải có đuôi {suffix}.")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Tệp đã tồn tại: {path}")
    if not path.parent.is_dir():
        raise ValueError("Thư mục xuất không tồn tại.")
    return path


@contextmanager
def staged_output(path: Path, overwrite: bool):
    descriptor, name = tempfile.mkstemp(prefix=".smartcatalog-", suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        if overwrite:
            os.replace(temporary, path)
        else:
            # On Windows rename refuses an existing destination, including a race.
            if os.name == "nt":
                os.rename(temporary, path)
            else:
                os.link(temporary, path)
                temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)


def annotate_page(page, result: SearchResult, page_index: int, options: NoteOptions,
                  cancel=None) -> tuple[str, ...]:
    """Apply the same deduplicated highlights and Unicode HTML notes to each view."""
    options.validate()
    occurrences = {}
    for row in result.rows:
        for hit in row.hits:
            if hit.page_index != page_index:
                continue
            key = hit.rectangles
            occurrence = occurrences.setdefault(key, {"notes": [], "keywords": []})
            if row.row.note.strip() and row.row.note not in occurrence["notes"]:
                occurrence["notes"].append(row.row.note)
            if row.row.keyword not in occurrence["keywords"]:
                occurrence["keywords"].append(row.row.keyword)
    warnings = []
    occupied = []
    bounds = page.rect * page.derotation_matrix
    for rectangles, data in occurrences.items():
        check_cancel(cancel)
        for box in rectangles:
            annot = page.add_highlight_annot(fitz.Rect(box))
            annot.set_colors(stroke=(0.4, 0.8, 0.8))
            annot.set_opacity(0.5)
            annot.update()
            occupied.append(fitz.Rect(box))
    for rectangles, data in occurrences.items():
        check_cancel(cancel)
        if not data["notes"]:
            continue
        anchor = fitz.Rect(rectangles[0])
        for box in rectangles[1:]:
            anchor |= fitz.Rect(box)
        note = "\n".join(data["notes"])
        html = '<div style="white-space:pre-wrap">' + escape(note).replace("\n", "<br>") + '</div>'
        css = f"* {{font-family: sans-serif; font-size: {options.font_size}pt; color: {options.color}; margin: 0;}}"
        placed = False
        width = min(190, bounds.width - 12)
        if width < 20:
            warnings.append(f"Trang {page_index+1}: trang quá hẹp cho ghi chú.")
            continue
        x = anchor.x0 - options.offset_x - width if "Left" in options.position else anchor.x1 + options.offset_x
        x = min(max(bounds.x0 + 6, x), bounds.x1 - width - 6)
        # Deterministic fallbacks stay within the unrotated page, avoiding other notes/hits.
        for height in (max(32, options.font_size * 3), 80, 140, 220):
            height = min(height, bounds.height - 12)
            initial_y = anchor.y0 - options.offset_y - height if "Top" in options.position else anchor.y1 + options.offset_y
            initial_y = min(max(bounds.y0 + 6, initial_y), bounds.y1 - height - 6)
            ys = [initial_y] + list(range(int(bounds.y0 + 6), int(bounds.y1 - height - 5), int(height + 6)))
            for y in ys:
                check_cancel(cancel)
                rect = fitz.Rect(x, y, x + width, y + height)
                if any(rect.intersects(other) for other in occupied):
                    continue
                spare, scale = page.insert_htmlbox(rect, html, css=css, scale_low=1)
                if spare >= 0:
                    occupied.append(rect)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            label = ", ".join(data["keywords"])
            warnings.append(f"Trang {page_index+1} ({label}): ghi chú không vừa; hãy giảm cỡ chữ hoặc rút gọn.")
    return tuple(warnings)


def export_annotated_pdf(result: SearchResult, path: Path, options: NoteOptions = NoteOptions(),
                         *, overwrite: bool = False, cancel=None, progress=None) -> ExportResult:
    options.validate()
    path = validate_output(result, path, ".pdf", overwrite)
    verify_sources(result)
    warnings = []
    with staged_output(path, overwrite) as temporary:
        with fitz.open(result.pdf_path) as doc:
            for index, page in enumerate(doc):
                check_cancel(cancel)
                warnings.extend(annotate_page(page, result, index, options, cancel))
                if progress:
                    progress(index + 1, len(doc))
            check_cancel(cancel)
            doc.save(temporary, garbage=3, deflate=True)
        with fitz.open(temporary) as check:
            if len(check) != result.page_count:
                raise ValueError("Không thể xác minh số trang PDF kết quả.")
        verify_sources(result)
        check_cancel(cancel)
    return ExportResult(path, tuple(warnings))
