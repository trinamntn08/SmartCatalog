from __future__ import annotations

import re


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    sanitized = sanitized.strip("_")
    return sanitized or "item"
