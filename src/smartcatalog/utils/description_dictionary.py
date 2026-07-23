from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional


DEFAULT_DICTIONARY_PATH = Path("config") / "database" / "dictionary.csv"


def resolve_description_dictionary(project_dir: str | Path) -> Optional[Path]:
    """Return the application dictionary stored under config/database."""
    candidate = Path(project_dir).resolve() / DEFAULT_DICTIONARY_PATH
    return candidate if candidate.is_file() else None


def read_description_dictionary(path: str | Path) -> dict[str, tuple[str, str]]:
    """Read CSV rows in the form: code, Vietnamese description, English description."""
    result: dict[str, tuple[str, str]] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream):
            if len(row) < 3:
                continue
            code = str(row[0] or "").strip()
            if not code:
                continue
            result[code] = (
                str(row[1] or "").strip(),
                str(row[2] or "").strip(),
            )
    return result


def import_dictionary_into_db(db, project_dir: str | Path) -> int:
    """
    Fill empty bilingual descriptions from the bundled CSV dictionary.

    User-entered database values always win. Returns the number of matched
    dictionary rows whose database item was found.
    """
    dictionary_path = resolve_description_dictionary(project_dir)
    if dictionary_path is None:
        return 0

    entries = read_description_dictionary(dictionary_path)
    if not entries:
        return 0

    matched = 0
    conn = db.connect()
    try:
        for code, (description_vi, description_en) in entries.items():
            if db.update_excel_descriptions_by_code(
                code=code,
                description_vi=description_vi,
                description_en=description_en,
                only_fill_empty=True,
                conn=conn,
            ):
                matched += 1
        conn.commit()
    finally:
        conn.close()
    return matched
