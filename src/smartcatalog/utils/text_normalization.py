from __future__ import annotations

import re


def normalize_header_text(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("\n", " ")
    return re.sub(r"\s+", " ", normalized).strip()
