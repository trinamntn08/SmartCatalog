from __future__ import annotations

import ast
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "smartcatalog"
FORBIDDEN_LAYER_IMPORTS = {
    "domain": {"db", "loader", "services", "ui", "utils"},
    "db": {"loader", "services", "ui"},
    "loader": {"db", "services", "ui"},
    "services": {"ui"},
    "utils": {"db", "loader", "services", "ui"},
}


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_lower_layers_do_not_import_forbidden_smartcatalog_layers(self) -> None:
        violations: list[str] = []
        for source_layer, forbidden_layers in FORBIDDEN_LAYER_IMPORTS.items():
            for path in (PACKAGE_ROOT / source_layer).rglob("*.py"):
                for module in imported_modules(path):
                    prefix = "smartcatalog."
                    if not module.startswith(prefix):
                        continue
                    imported_layer = module[len(prefix) :].split(".", 1)[0]
                    if imported_layer in forbidden_layers:
                        relative = path.relative_to(PACKAGE_ROOT.parent)
                        violations.append(f"{relative}: imports {module}")

        self.assertEqual(violations, [])

    def test_services_remain_free_of_tkinter_imports(self) -> None:
        violations = [
            str(path.relative_to(PACKAGE_ROOT.parent))
            for path in (PACKAGE_ROOT / "services").rglob("*.py")
            if any(
                module == "tkinter" or module.startswith("tkinter.")
                for module in imported_modules(path)
            )
        ]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
