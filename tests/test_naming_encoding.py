from __future__ import annotations

import unittest
from pathlib import Path

from tests import support as _test_support


class SourceEncodingTests(unittest.TestCase):
    def test_active_python_source_is_utf8_without_common_mojibake(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        markers = ("Ã", "Â", "â€", "Ä‘", "áº", "á»")
        failures: list[str] = []

        for path in sorted(source_root.rglob("*.py")):
            text = path.read_bytes().decode("utf-8", errors="strict")
            found = [marker for marker in markers if marker in text]
            if found:
                failures.append(
                    f"{path.relative_to(source_root)}: {', '.join(found)}"
                )

        self.assertEqual(failures, [])
