from __future__ import annotations

import hashlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from tests import support as _test_support  # Ensures src/ is importable.
from tests.support.fixtures import TemporaryProject, create_image_fixture

from smartcatalog.domain.models import CatalogItem as DomainCatalogItem
from smartcatalog.state import CatalogItem as StateCatalogItem
from smartcatalog.ui.main_window import _safe_ui
from smartcatalog.utils.code_normalization import (
    build_unique_normalized_code_index,
    normalize_code_soft,
)
from smartcatalog.utils.filename_utils import sanitize_filename
from smartcatalog.utils.hashing import sha256_bytes, sha256_text
from smartcatalog.utils.text_normalization import normalize_header_text
from smartcatalog.utils.ui_dispatch import dispatch_to_tk
from smartcatalog.utils.workbook_images import get_image_anchor_row, image_to_pil


class CatalogItemCompatibilityTests(unittest.TestCase):
    def test_state_reexports_the_active_domain_model(self) -> None:
        self.assertIs(StateCatalogItem, DomainCatalogItem)
        item = StateCatalogItem(
            id=1,
            code="12-345-67",
            description="",
            description_excel="",
            description_vietnames_from_excel="",
            pdf_path="",
            page=None,
            images=[],
        )
        self.assertIsInstance(item, DomainCatalogItem)


class CodeNormalizationTests(unittest.TestCase):
    def test_unique_index_removes_ambiguous_normalized_codes(self) -> None:
        codes = [
            "12-345-67",
            "98-765-43",
            "98–765–43",
            "77 777 77",
            "",
        ]
        index = build_unique_normalized_code_index(codes)
        self.assertEqual(index["12-345-67"], "12-345-67")
        self.assertNotIn("98-765-43", index)


class TextAndFilenameCompatibilityTests(unittest.TestCase):
    def test_header_normalization_contract(self) -> None:
        self.assertEqual(normalize_header_text(" Product\n Code "), "product code")
        self.assertEqual(normalize_header_text("  QTY   VALUE  "), "qty value")
        self.assertEqual(normalize_header_text(None), "")

    def test_filename_sanitization_contract(self) -> None:
        self.assertEqual(sanitize_filename("***"), "item")
        self.assertEqual(sanitize_filename("Catalog Sheet"), "Catalog_Sheet")
        self.assertEqual(sanitize_filename("12 / 345 / 67"), "12_345_67")


class HashingCompatibilityTests(unittest.TestCase):
    def test_byte_and_text_hashes_match_sha256_contract(self) -> None:
        data = "Sản phẩm".encode("utf-8")
        expected = hashlib.sha256(data).hexdigest()

        self.assertEqual(sha256_bytes(data), expected)
        self.assertEqual(sha256_text("Sản phẩm"), expected)


class WorkbookImageCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TemporaryProject()
        self.project.__enter__()
        self.addCleanup(self.project.__exit__, None, None, None)

    def test_anchor_helper_supports_current_shapes(self) -> None:
        marker_anchor = SimpleNamespace(
            _from=SimpleNamespace(row=4),
        )
        direct_anchor = SimpleNamespace(row=7)
        for image in (
            SimpleNamespace(anchor=marker_anchor),
            SimpleNamespace(anchor=direct_anchor),
            SimpleNamespace(anchor=None),
            SimpleNamespace(),
        ):
            with self.subTest(image=image):
                anchor = get_image_anchor_row(image)
                self.assertIn(anchor, (5, 8, None))

    def test_image_loader_reads_embedded_data(self) -> None:
        buffer = io.BytesIO()
        with Image.new("RGB", (9, 7), (10, 20, 30)) as source:
            source.save(buffer, format="PNG")
        data = buffer.getvalue()

        class EmbeddedImage:
            @staticmethod
            def _data() -> bytes:
                return data

        shared_image = image_to_pil(EmbeddedImage())
        try:
            self.assertEqual(shared_image.size, (9, 7))
            self.assertEqual(shared_image.getpixel((0, 0)), (10, 20, 30))
        finally:
            shared_image.close()

    def test_image_loader_preserves_file_reference_fallback(self) -> None:
        image_path = create_image_fixture(
            self.project.path("image.png"),
            size=(11, 8),
        )

        class ReferencedImage:
            ref = str(image_path)

            @staticmethod
            def _data():
                raise ValueError("force reference fallback")

        loaded = image_to_pil(ReferencedImage())
        try:
            self.assertEqual(loaded.size, (11, 8))
        finally:
            loaded.close()


class UIDispatchCompatibilityTests(unittest.TestCase):
    class Root:
        def __init__(self) -> None:
            self.calls: list[tuple[int, object]] = []

        def after(self, delay: int, callback) -> None:
            self.calls.append((delay, callback))
            callback()

    def test_wrapper_and_shared_dispatch_use_zero_delay(self) -> None:
        wrapper_root = self.Root()
        shared_root = self.Root()
        values: list[str] = []

        _safe_ui(wrapper_root, lambda: values.append("wrapper"))
        dispatch_to_tk(shared_root, lambda: values.append("shared"))

        self.assertEqual(wrapper_root.calls[0][0], 0)
        self.assertEqual(shared_root.calls[0][0], 0)
        self.assertEqual(values, ["wrapper", "shared"])


if __name__ == "__main__":
    unittest.main()
