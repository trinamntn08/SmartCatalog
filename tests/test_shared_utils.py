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
from smartcatalog.loader.excel_loader import normalize_code_soft as loader_normalize_code
from smartcatalog.state import CatalogItem as StateCatalogItem
from smartcatalog.ui.main_window import (
    _build_db_code_index,
    _get_image_anchor_row,
    _image_to_pil,
    _normalize_code_soft,
    _normalize_header_text,
    _safe_ui,
    _sanitize_filename,
)
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


class CodeNormalizationCompatibilityTests(unittest.TestCase):
    def test_all_active_entry_points_return_identical_results(self) -> None:
        values = [
            None,
            "",
            " 12-345-67 ",
            "12 – 345 — 67",
            "12 345 67",
            "ABC / 123",
        ]
        for value in values:
            with self.subTest(value=value):
                expected = normalize_code_soft(value)
                self.assertEqual(loader_normalize_code(value), expected)
                self.assertEqual(_normalize_code_soft(value), expected)

    def test_unique_index_wrapper_matches_shared_implementation(self) -> None:
        codes = [
            "12-345-67",
            "98-765-43",
            "98–765–43",
            "77 777 77",
            "",
        ]
        self.assertEqual(
            _build_db_code_index(codes),
            build_unique_normalized_code_index(codes),
        )
        self.assertNotIn("98-765-43", _build_db_code_index(codes))


class TextAndFilenameCompatibilityTests(unittest.TestCase):
    def test_header_wrapper_matches_shared_implementation(self) -> None:
        for value in (None, "", " Product\n Code ", "  QTY   VALUE  ", 123):
            with self.subTest(value=value):
                self.assertEqual(
                    _normalize_header_text(value),
                    normalize_header_text(value),
                )

    def test_filename_wrapper_matches_shared_implementation(self) -> None:
        for value in (
            None,
            "",
            "***",
            "Catalog Sheet",
            "12 / 345 / 67",
            "_already-safe_",
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    _sanitize_filename(value),
                    sanitize_filename(value),
                )


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

    def test_anchor_wrapper_matches_shared_helper_for_supported_shapes(self) -> None:
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
                self.assertEqual(
                    _get_image_anchor_row(image),
                    get_image_anchor_row(image),
                )

    def test_image_wrapper_matches_shared_data_loader(self) -> None:
        buffer = io.BytesIO()
        with Image.new("RGB", (9, 7), (10, 20, 30)) as source:
            source.save(buffer, format="PNG")
        data = buffer.getvalue()

        class EmbeddedImage:
            @staticmethod
            def _data() -> bytes:
                return data

        wrapper_image = _image_to_pil(EmbeddedImage())
        shared_image = image_to_pil(EmbeddedImage())
        try:
            self.assertEqual(wrapper_image.size, shared_image.size)
            self.assertEqual(wrapper_image.getpixel((0, 0)), shared_image.getpixel((0, 0)))
        finally:
            wrapper_image.close()
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
