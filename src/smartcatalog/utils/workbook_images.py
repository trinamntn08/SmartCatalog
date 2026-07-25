from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


def get_image_anchor_row(image) -> Optional[int]:
    try:
        anchor = getattr(image, "anchor", None)
        if anchor is None:
            return None
        if hasattr(anchor, "_from") and getattr(anchor._from, "row", None) is not None:
            return int(anchor._from.row) + 1
        if getattr(anchor, "row", None) is not None:
            return int(anchor.row) + 1
    except Exception:
        return None
    return None


def image_to_pil(image) -> Optional[Image.Image]:
    from PIL import Image

    try:
        data = image._data()
        return Image.open(io.BytesIO(data))
    except Exception:
        pass
    try:
        reference = getattr(image, "ref", None)
        if reference:
            path = Path(reference)
            if path.exists():
                return Image.open(path)
    except Exception:
        return None
    return None
