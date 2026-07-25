from __future__ import annotations

import re


def normalize_code_soft(value: str) -> str:
    """Preserve the application's current tolerant product-code formatting."""

    if value is None:
        return ""
    normalized = str(value).strip()
    normalized = normalized.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", normalized)


def build_unique_normalized_code_index(codes: list[str]) -> dict[str, str]:
    """Map normalized codes only when the mapping is unambiguous."""

    buckets: dict[str, list[str]] = {}
    for code in codes:
        key = normalize_code_soft(code)
        buckets.setdefault(key, []).append(code)
    return {
        key: values[0]
        for key, values in buckets.items()
        if len(values) == 1
    }
