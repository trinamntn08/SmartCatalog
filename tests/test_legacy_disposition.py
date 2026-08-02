from __future__ import annotations

import unittest
from pathlib import Path

from tests import support as _test_support


class LegacyDispositionTests(unittest.TestCase):
    def test_removed_legacy_modules_are_absent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        removed = (
            "src/smartcatalog/db/update_db_from_pdf.py",
            "src/smartcatalog/loader/pdf_loader.py",
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

    def test_runtime_dependency_input_contains_only_active_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        requirements = {
            line.strip().lower()
            for line in (root / "requirements.in").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            requirements,
            {
                "pandas==2.3.3",
                "pymupdf==1.26.7",
                "pillow==12.1.0",
                "openpyxl==3.1.5",
            },
        )

    def test_build_dependency_input_extends_runtime_with_pyinstaller(self) -> None:
        root = Path(__file__).resolve().parents[1]
        requirements = {
            line.strip().lower()
            for line in (root / "requirements-build.in").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            requirements,
            {"-r requirements.in", "pyinstaller==6.18.0"},
        )

    def test_agent_dependency_input_extends_runtime_with_local_tools(self) -> None:
        root = Path(__file__).resolve().parents[1]
        requirements = {
            line.strip().lower()
            for line in (root / "requirements-dev.in").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(
            requirements,
            {
                "-r requirements.in",
                "pip-tools==7.6.0",
                "ruff==0.15.22",
            },
        )
