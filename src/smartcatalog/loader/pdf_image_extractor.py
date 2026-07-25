from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Optional

import fitz
from PIL import Image


def distance_between_rects(rect1: fitz.Rect, rect2: fitz.Rect) -> float:
    c1x = (rect1.x0 + rect1.x1) / 2.0
    c1y = (rect1.y0 + rect1.y1) / 2.0
    c2x = (rect2.x0 + rect2.x1) / 2.0
    c2y = (rect2.y0 + rect2.y1) / 2.0
    return math.hypot(c2x - c1x, c2y - c1y)


def handle_jpeg2000_conversion(
    image_bytes: bytes,
    image_ext: str,
) -> tuple[bytes, str]:
    if image_ext.lower() in ("jp2", "jpx", "j2k", "j2c"):
        with Image.open(io.BytesIO(image_bytes)) as image:
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue(), "png"
    return image_bytes, image_ext


def nearest_image_for_code_on_page(
    page: fitz.Page,
    keyword_rect: fitz.Rect,
) -> Optional[tuple[bytes, str, fitz.Rect]]:
    try:
        nearest: Optional[tuple[bytes, str, fitz.Rect]] = None
        nearest_distance = float("inf")

        for image in page.get_images(full=True):
            xref = image[0]
            rectangles = page.get_image_rects(xref) or []
            if not rectangles:
                continue

            extracted = page.parent.extract_image(xref)
            image_bytes = extracted["image"]
            image_ext = extracted.get("ext", "png")

            for rectangle in rectangles:
                image_rect = fitz.Rect(rectangle)
                if keyword_rect.y1 < image_rect.y0:
                    continue

                distance = distance_between_rects(image_rect, keyword_rect)
                if distance < nearest_distance:
                    image_bytes, image_ext = handle_jpeg2000_conversion(
                        image_bytes,
                        image_ext,
                    )
                    nearest = (image_bytes, image_ext, image_rect)
                    nearest_distance = distance

        return nearest
    except Exception:
        return None


def save_image_bytes_as_png(image_bytes: bytes, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source if source.mode == "RGBA" else source.convert("RGBA")
        try:
            with Image.new(
                "RGBA",
                image.size,
                (255, 255, 255, 255),
            ) as white_background:
                with Image.alpha_composite(
                    white_background,
                    image,
                ).convert("RGB") as flattened:
                    flattened.save(out_path, format="PNG", quality=95)
        finally:
            if image is not source:
                image.close()
