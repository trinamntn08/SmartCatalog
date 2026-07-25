from __future__ import annotations

from typing import Callable


def dispatch_to_tk(root, callback: Callable[[], None]) -> None:
    """Schedule a callback on the Tk event loop using current UI semantics."""

    root.after(0, callback)
