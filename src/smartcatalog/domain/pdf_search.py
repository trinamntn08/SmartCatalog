"""Immutable contracts for read-only PDF keyword search workflows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SearchCancelled(Exception):
    """A user cancelled a search or an unpublished export."""


@dataclass(frozen=True)
class KeywordRow:
    source_row: int
    keyword: str
    note: str = ""
    sheet: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkbookInput:
    path: Path
    sheet: str
    first_row: int = 2
    keyword_column: str = "A"
    note_column: str = "C"
    result_column: str = "B"


@dataclass(frozen=True)
class KeywordInput:
    rows: tuple[KeywordRow, ...]
    warnings: tuple[str, ...] = ()
    workbook: WorkbookInput | None = None
    workbook_digest: str = ""


@dataclass(frozen=True)
class PdfHit:
    page_index: int
    rectangles: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class KeywordResult:
    row: KeywordRow
    hits: tuple[PdfHit, ...]

    @property
    def pages(self) -> tuple[int, ...]:
        return tuple(sorted({hit.page_index + 1 for hit in self.hits}))


@dataclass(frozen=True)
class SearchResult:
    pdf_path: Path
    pdf_digest: str
    source: KeywordInput
    rows: tuple[KeywordResult, ...]
    page_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteOptions:
    position: str = "Top Right"
    offset_x: float = 5
    offset_y: float = 5
    color: str = "black"
    font_size: float = 8

    def validate(self) -> None:
        import math
        if self.position not in ("Top Right", "Top Left", "Bottom Right", "Bottom Left"):
            raise ValueError("Vị trí ghi chú không hợp lệ.")
        if self.color not in ("black", "blue", "green", "red", "yellow"):
            raise ValueError("Màu ghi chú không hợp lệ.")
        if not math.isfinite(self.font_size) or not 6 <= self.font_size <= 36:
            raise ValueError("Cỡ chữ phải từ 6 đến 36 pt.")
        if any(not math.isfinite(v) or not 0 <= v <= 200 for v in (self.offset_x, self.offset_y)):
            raise ValueError("Độ lệch phải từ 0 đến 200 pt.")


@dataclass(frozen=True)
class ExportResult:
    path: Path
    warnings: tuple[str, ...] = ()
