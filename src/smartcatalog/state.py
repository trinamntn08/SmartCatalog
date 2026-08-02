# smartcatalog/state.py
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Optional, List, Any
import shutil
import sys

from smartcatalog.domain.models import CatalogItem


DEFAULT_DATABASE_PATH = Path("sql") / "catalog.db"


def database_data_dir(database_path: str | Path) -> Path:
    """Return the portable data root containing a catalog database."""
    parent = Path(database_path).resolve().parent
    if parent.name.casefold() == "sql":
        return parent.parent
    return parent


def get_app_dir() -> Path:
    """
    Resolve the application root directory.
    - Frozen .exe: folder containing app.exe
    - Source run: project root (src/..)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppState:
    """
    Global application state.
    """
    project_dir: Path = field(default_factory=get_app_dir)

    # filesystem layout
    data_dir: Path = field(init=False)
    db_path: Path = field(init=False)
    settings_path: Path = field(init=False)

    assets_dir: Path = field(init=False)

    # current-session selection
    catalog_pdf_path: Optional[Path] = None

    # runtime objects used by controllers
    db: Optional[Any] = None
    items_cache: List[CatalogItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.project_dir = Path(self.project_dir).resolve()
        self.data_dir = self.project_dir / "config" / "database"
        self.settings_path = self.data_dir / "settings.json"
        self.assets_dir = self.data_dir / "assets"

        self.ensure_dirs()
        self._load_settings()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.assets_dir.mkdir(parents=True, exist_ok=True)
        (self.assets_dir / "excel_import").mkdir(parents=True, exist_ok=True)
        (self.assets_dir / "pdf_import").mkdir(parents=True, exist_ok=True)
        (self.assets_dir / "manual_import").mkdir(parents=True, exist_ok=True)

        (self.data_dir / "catalog_pdfs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "sql").mkdir(parents=True, exist_ok=True)

    # -------------------------
    # Settings persistence
    # -------------------------

    def _resolve_settings_path(self, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.settings_path.parent / path
        return path.resolve()

    def _settings_path_value(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        try:
            return str(resolved.relative_to(self.settings_path.parent))
        except ValueError:
            return str(resolved)

    def _load_settings(self) -> None:
        data: dict[str, Any] = {}
        should_save = not self.settings_path.exists()
        if self.settings_path.exists():
            try:
                loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
                else:
                    should_save = True
            except (OSError, ValueError, TypeError):
                should_save = True

        database_value = str(data.get("database_path") or "").strip()
        if not database_value:
            database_value = str(DEFAULT_DATABASE_PATH)
            should_save = True

        self.db_path = self._resolve_settings_path(database_value)
        self.data_dir = database_data_dir(self.db_path)
        self.assets_dir = self.data_dir / "assets"

        pdf_value = str(data.get("catalog_pdf_path") or "").strip()
        if pdf_value:
            pdf_path = self._resolve_settings_path(pdf_value)
            if pdf_path.exists():
                self.catalog_pdf_path = pdf_path

        if should_save:
            try:
                self._save_settings()
            except OSError:
                # Startup can still use the default database if settings cannot
                # be written. An explicit database switch reports this failure.
                pass

    def _save_settings(self) -> None:
        payload = {
            "database_path": self._settings_path_value(self.db_path),
            "catalog_pdf_path": (
                self._settings_path_value(self.catalog_pdf_path)
                if self.catalog_pdf_path
                else ""
            ),
        }
        temporary_path = self.settings_path.with_name(
            f"{self.settings_path.name}.tmp"
        )
        temporary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(self.settings_path)

    def set_database_path(self, database_path: str | Path) -> None:
        """Persist and activate a database selected by the user."""
        selected_path = Path(database_path).resolve()
        previous_db_path = self.db_path
        previous_pdf_path = self.catalog_pdf_path
        self.db_path = selected_path
        self.catalog_pdf_path = None
        try:
            self._save_settings()
        except OSError:
            self.db_path = previous_db_path
            self.catalog_pdf_path = previous_pdf_path
            raise

        self.data_dir = database_data_dir(selected_path)
        self.assets_dir = self.data_dir / "assets"

    # -------------------------
    # PDF selection
    # -------------------------

    def set_catalog_pdf(self, src_path: str) -> None:
        """
        Copy selected PDF into: config/database/catalog_pdfs/
        Persist the chosen path for the next application launch.
        """
        if not src_path:
            self.catalog_pdf_path = None
            self._save_settings()
            return

        self.ensure_dirs()

        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"PDF not found: {src}")

        dest_dir = self.data_dir / "catalog_pdfs"
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / src.name

        # Copy only if needed
        if (not dest.exists()) or (dest.stat().st_size != src.stat().st_size):
            shutil.copy2(str(src), str(dest))

        self.catalog_pdf_path = dest
        self._save_settings()
