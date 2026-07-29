from pathlib import Path
import tempfile
import unittest

import fitz

from smartcatalog.ui.pdf_crop_window import build_page_layout, search_pdf_pages


class PdfCropSearchTests(unittest.TestCase):
    def test_page_layout_stacks_and_centers_the_whole_document(self):
        layouts = build_page_layout([(100, 200), (80, 120)], zoom=2, gap=10)

        self.assertEqual((layouts[0].left, layouts[0].top), (10, 10))
        self.assertEqual((layouts[0].width, layouts[0].height), (200, 400))
        self.assertEqual((layouts[1].left, layouts[1].top), (30, 420))
        self.assertEqual((layouts[1].width, layouts[1].height), (160, 240))

    def test_searches_all_pages_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "catalog.pdf"
            with fitz.open() as doc:
                first = doc.new_page()
                first.insert_text((72, 72), "Alpha product")
                second = doc.new_page()
                second.insert_text((72, 72), "Needle PRODUCT details")
                doc.save(pdf_path)

            results = search_pdf_pages(pdf_path, "needle product")

        self.assertEqual([result.page_index for result in results], [1])
        self.assertIn("Needle PRODUCT", results[0].snippet)

    def test_blank_query_does_not_open_a_document(self):
        self.assertEqual(search_pdf_pages(Path("unused.pdf"), "   "), [])


if __name__ == "__main__":
    unittest.main()
