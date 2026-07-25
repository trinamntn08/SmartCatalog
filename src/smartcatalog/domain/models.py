from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CatalogItem:
    id: int
    code: str
    description: str
    description_excel: str
    description_vietnames_from_excel: str
    pdf_path: str
    page: Optional[int]
    images: List[str]
    validated: bool = False
    validated_at: str = ""

    category: str = ""
    author: str = ""
    dimension: str = ""
    small_description: str = ""
    shape: str = ""
    blade_tip: str = ""
    surface_treatment: str = ""
    material: str = ""
