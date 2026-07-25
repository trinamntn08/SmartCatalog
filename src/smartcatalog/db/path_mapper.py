from __future__ import annotations

from pathlib import Path
from typing import Optional


class DatabasePathMapper:
    def __init__(self, data_dir: Optional[str | Path] = None):
        self.data_dir: Optional[Path] = Path(data_dir).resolve() if data_dir else None

    def to_db_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text or text.lower().startswith("excel:") or not self.data_dir:
            return text
        try:
            path = Path(text)
            if path.is_absolute():
                try:
                    return str(path.resolve().relative_to(self.data_dir))
                except Exception:
                    return text
        except Exception:
            return text
        return text

    def from_db_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text or text.lower().startswith("excel:") or not self.data_dir:
            return text
        try:
            path = Path(text)
            if not path.is_absolute():
                return str((self.data_dir / path).resolve())
        except Exception:
            return text
        return text
