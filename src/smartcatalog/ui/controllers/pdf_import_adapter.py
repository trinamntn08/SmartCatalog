from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from smartcatalog.loader.extract_item import extract_items_from_page
from smartcatalog.services.pdf_import import import_pdf_catalog
from smartcatalog.state import AppState


def _ui_call(widget_or_root: Any, fn: Callable[[], None]) -> None:
    """Schedule a callback through Tk when a widget/root is available."""
    if widget_or_root is None:
        return
    after = getattr(widget_or_root, "after", None)
    if callable(after):
        widget_or_root.after(0, fn)
    else:
        fn()


def _set_preview_text(source_preview: Any, text: str) -> None:
    def update_preview() -> None:
        try:
            source_preview.configure(state="normal")
            source_preview.delete("1.0", "end")
            source_preview.insert("1.0", text)
            source_preview.configure(state="disabled")
        except Exception:
            pass

    _ui_call(source_preview, update_preview)


def _set_status(status_var: Any, text: str) -> None:
    def update_status() -> None:
        try:
            status_var.set(text)
        except Exception:
            pass

    _ui_call(status_var, update_status)


def build_or_update_db_from_pdf(
    state: AppState,
    source_preview: Any = None,
    status_message: Any = None,
    *,
    page_start: int = 1,
    page_end: Optional[int] = None,
    on_existing_item_decision: Optional[Callable[[str], bool]] = None,
) -> None:
    """Adapt the headless PDF import service to the controller's Tk callbacks."""
    import_pdf_catalog(
        state,
        page_start=page_start,
        page_end=page_end,
        on_existing_item_decision=on_existing_item_decision,
        status_callback=lambda text: _set_status(status_message, text),
        preview_callback=lambda text: _set_preview_text(source_preview, text),
        page_extractor=extract_items_from_page,
    )
