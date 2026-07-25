from __future__ import annotations

import unittest
from pathlib import Path

from tests import support as _test_support


class LegacyDispositionTests(unittest.TestCase):
    def test_removed_legacy_modules_are_absent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        removed = (
            "src/smartcatalog/db/update_db_from_pdf.py",
            "src/smartcatalog/extracter/extract_key_info_from_pdf.py",
            "src/smartcatalog/matcher/pdf_matcher.py",
            "src/smartcatalog/ui/controllers/pdf_viewer_controller.py",
            "src/smartcatalog/utils/pdf_exporter.py",
            "src/smartcatalog/config/settings.py",
        )
        self.assertEqual(
            [path for path in removed if (root / path).exists()],
            [],
        )

    def test_requirements_contain_only_active_runtime_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        requirements = {
            line.strip().lower()
            for line in (root / "requirements.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            requirements,
            {"pandas", "pymupdf", "pillow", "openpyxl>=3.1.0"},
        )
