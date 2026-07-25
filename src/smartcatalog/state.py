# smartcatalog/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any
import shutil
import sys

from smartcatalog.domain.models import CatalogItem


DEFAULT_DATABASE_PATH = Path("sql") / "catalog.db"


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

    assets_dir: Path = field(init=False)

    # current-session selection
    catalog_pdf_path: Optional[Path] = None

    # runtime objects used by controllers
    db: Optional[Any] = None
    items_cache: List[CatalogItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.project_dir = Path(self.project_dir).resolve()
        self.data_dir = self.project_dir / "config" / "database"
        self.assets_dir = self.data_dir / "assets"

        self.ensure_dirs()
        self.db_path = (self.data_dir / DEFAULT_DATABASE_PATH).resolve()
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
    # PDF selection
    # -------------------------

    def set_catalog_pdf(self, src_path: str) -> None:
        """
        Copy selected PDF into: config/database/catalog_pdfs/
        Keep the chosen path for the current application session.
        """
        if not src_path:
            self.catalog_pdf_path = None
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
