from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz
from openpyxl import Workbook, load_workbook

from tests import support as _test_support

from smartcatalog.domain.pdf_search import (
    KeywordInput, KeywordRow, NoteOptions, SearchCancelled, WorkbookInput,
)
from smartcatalog.loader.keyword_workbook import file_digest, read_keyword_workbook
from smartcatalog.services.pdf_keyword_search import search_keywords
from smartcatalog.services.pdf_annotation_export import export_annotated_pdf, annotate_page
from smartcatalog.services.keyword_results_export import export_keyword_results


class PdfKeywordToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / "source.PDF"
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((72, 100), "ABC-12 ABC-123 XABC-12 ABC-12.4 abc-12")
            page.insert_text((72, 150), "wrapped")
            page.insert_text((72, 170), "phrase")
            page = doc.new_page()
            page.insert_text((72, 100), "ABC-12 another result")
            page.set_rotation(90)
            doc.save(self.pdf)
        self.xlsx = self.root / "keywords.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.title = "Keywords"
        sheet.append(["Keyword", "Pages", "Note", "Keep"])
        sheet.append(["ABC-12", "old", "Ghi chú tiếng Việt: dụng cụ y tế", "=1+2"])
        sheet.append(["ABC-12", None, "Another note"])
        sheet.append(["missing", None, None])
        sheet.append(["00012", None, "=literal note"])
        sheet["C5"].data_type = "s"
        book.save(self.xlsx)
        book.close()
        self.config = WorkbookInput(self.xlsx, "Keywords")
        self.source = read_keyword_workbook(self.config)

    def search(self, **kwargs):
        return search_keywords(self.pdf, self.source, **kwargs)

    def test_whole_codes_preserve_duplicates_geometry_and_pages(self):
        result = self.search(whole_code=True)
        self.assertEqual(result.rows[0].pages, (1, 2))
        self.assertEqual(len(result.rows[0].hits), 3)
        self.assertEqual(result.rows[0].hits, result.rows[1].hits)
        self.assertNotEqual(result.rows[0].row.note, result.rows[1].row.note)
        self.assertEqual(result.rows[2].hits, ())
        self.assertTrue(all(hit.rectangles for hit in result.rows[0].hits))
        self.assertEqual(len(self.search().rows[0].hits), 6)

    def test_wrapped_phrase_and_rotated_page_geometry(self):
        source = KeywordInput((KeywordRow(1, "wrapped phrase"),))
        result = search_keywords(self.pdf, source)
        self.assertEqual(result.rows[0].pages, (1,))
        self.assertEqual(len(result.rows[0].hits[0].rectangles), 2)

    def test_reading_keeps_rows_and_warns_about_existing_results(self):
        self.assertEqual([row.source_row for row in self.source.rows], [2, 3, 4, 5])
        self.assertEqual(self.source.rows[-1].keyword, "00012")
        self.assertTrue(self.source.rows[0].warnings)
        with self.assertRaises(ValueError):
            read_keyword_workbook(replace(self.config, result_column="A"))
        with self.assertRaises(ValueError):
            read_keyword_workbook(replace(self.config, first_row=0))

    def test_formula_without_cached_value_and_numeric_keywords_warn(self):
        book = Workbook()
        sheet = book.active
        sheet.append(["Keyword", "Pages", "Note"])
        sheet.append(["=1+2", None, None])
        sheet.append([123, None, True])
        path = self.root / "numbers.xlsx"
        book.save(path)
        book.close()
        source = read_keyword_workbook(WorkbookInput(path, sheet.title))
        self.assertEqual(source.rows[0].keyword, "123")
        self.assertEqual(source.rows[0].note, "True")
        self.assertTrue(any("công thức" in warning for warning in source.warnings))
        self.assertTrue(any("ô số" in warning for warning in source.rows[0].warnings))

    def test_exports_preserve_sources_and_formulas_and_literal_report_text(self):
        before = (file_digest(self.pdf), file_digest(self.xlsx))
        result = self.search(whole_code=True)
        copied = self.root / "copy.xlsx"
        report = self.root / "report.xlsx"
        export_keyword_results(result, copied, copy_workbook=True)
        export_keyword_results(result, report)
        book = load_workbook(copied)
        try:
            self.assertEqual(book["Keywords"]["B2"].value, "1, 2")
            self.assertEqual(book["Keywords"]["D2"].value, "=1+2")
            self.assertEqual(book["Keywords"]["D2"].data_type, "f")
        finally:
            book.close()
        book = load_workbook(report)
        try:
            self.assertEqual(book["PDF Search"].max_row, 5)
            self.assertEqual(book["PDF Search"]["D5"].value, "=literal note")
            self.assertEqual(book["PDF Search"]["D5"].data_type, "s")
        finally:
            book.close()
        self.assertEqual(before, (file_digest(self.pdf), file_digest(self.xlsx)))

    def test_annotated_pdf_deduplicates_and_renders_vietnamese(self):
        result = self.search(whole_code=True)
        target = self.root / "annotated.pdf"
        exported = export_annotated_pdf(result, target)
        self.assertFalse(exported.warnings)
        with fitz.open(target) as doc:
            annotations = [annot for page in doc for annot in (page.annots() or ())]
            self.assertEqual(len(annotations), 3)
            text = " ".join(page.get_text() for page in doc)
            self.assertIn("tiếng Việt", text)
            self.assertIn("Another note", text)
            self.assertEqual(doc[1].rotation, 90)
            self.assertGreater(len(doc[1].get_pixmap().samples), 0)

    def test_note_overflow_is_visible_and_not_silent(self):
        source = KeywordInput((KeywordRow(1, "ABC-12", "word " * 5000),))
        result = search_keywords(self.pdf, source, whole_code=True)
        with fitz.open(self.pdf) as doc:
            warnings = annotate_page(doc[0], result, 0, NoteOptions(font_size=36))
        self.assertTrue(any("không vừa" in warning for warning in warnings))

    def test_source_overwrites_collisions_and_changed_inputs_are_rejected(self):
        result = self.search()
        with self.assertRaises(ValueError):
            export_annotated_pdf(result, self.pdf, overwrite=True)
        with self.assertRaises(ValueError):
            export_keyword_results(result, self.xlsx, overwrite=True)
        existing = self.root / "exists.pdf"
        existing.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            export_annotated_pdf(result, existing)
        self.assertEqual(existing.read_bytes(), b"keep")
        with self.xlsx.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Excel"):
            export_keyword_results(result, self.root / "changed.xlsx")

    def test_cancellation_and_failed_publish_leave_no_partial_outputs(self):
        with self.assertRaises(SearchCancelled):
            self.search(cancel=lambda: True)
        result = self.search()
        target = self.root / "cancelled.pdf"
        with self.assertRaises(SearchCancelled):
            export_annotated_pdf(result, target, cancel=lambda: True)
        self.assertFalse(target.exists())
        with patch("smartcatalog.services.pdf_annotation_export.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                export_annotated_pdf(result, target, overwrite=True)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".smartcatalog-*")))

    def test_textless_and_encrypted_pdfs_have_actionable_outcomes(self):
        blank = self.root / "blank.pdf"
        with fitz.open() as doc:
            doc.new_page()
            doc.save(blank)
        result = search_keywords(blank, self.source)
        self.assertTrue(any("OCR" in warning for warning in result.warnings))
        locked = self.root / "locked.pdf"
        with fitz.open(self.pdf) as doc:
            doc.save(locked, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        with self.assertRaisesRegex(ValueError, "mật khẩu"):
            search_keywords(locked, self.source)

    def test_options_reject_nan_and_invalid_values(self):
        for options in (NoteOptions(font_size=float("nan")), NoteOptions(offset_x=-1),
                        NoteOptions(color="invalid"), NoteOptions(font_size=100)):
            with self.assertRaises(ValueError):
                options.validate()


if __name__ == "__main__":
    unittest.main()
