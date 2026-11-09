from __future__ import annotations

import unittest
from contextlib import closing
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests import support as _test_support
from tests.support.fixtures import TemporaryProject
from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.domain.models import CatalogItem
from smartcatalog.ui.controllers.images_controller import ImagesControllerMixin
from smartcatalog.ui.controllers.items_controller import ItemsControllerMixin


class StartupImportTests(unittest.TestCase):
    def test_entry_import_leaves_heavy_dependencies_for_the_splash_boot(self):
        probe = (
            "import sys; sys.path.insert(0,'src'); import smartcatalog.main; "
            "assert not {'smartcatalog.ui.main_window','pandas','openpyxl','fitz','pymupdf'}"
            ".intersection(sys.modules)"
        )
        subprocess.run(
            [sys.executable, "-c", probe],
            cwd=Path(__file__).resolve().parents[1], check=True,
        )


class TreeStub:
    def __init__(self):
        self.rows = {}
        self.selected = ()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, *rows):
        for row in rows:
            del self.rows[row]

    def insert(self, _parent, _position, *, iid, tags, values):
        self.rows[iid] = {"values": values, "tags": tags}

    def selection(self):
        return self.selected

    def selection_set(self, iid):
        self.selected = (iid,)

    def focus(self, iid):
        self.focused = iid

    def item(self, iid, field):
        return self.rows[iid][field]


class RootStub:
    def __init__(self):
        self.jobs = {}
        self.sequence = 0

    def after(self, _delay, callback):
        self.sequence += 1
        self.jobs[self.sequence] = callback
        return self.sequence

    def after_cancel(self, job):
        self.jobs.pop(job, None)

    def run_pending(self):
        for job, callback in list(self.jobs.items()):
            self.jobs.pop(job)
            callback()


def make_item(item_id=1, **values):
    fields = dict(
        id=item_id, code=f"A-{item_id}", description="Kéo phẫu thuật tim đỏ",
        description_excel="Surgical scissors", description_vietnames_from_excel="",
        pdf_path="", page=3, images=[],
    )
    fields.update(values)
    return CatalogItem(**fields)


class ItemsPanel(ItemsControllerMixin):
    def __init__(self, items):
        self.state = SimpleNamespace(db=None, items_cache=items)
        self.root = RootStub()
        self.items_tree = TreeStub()
        self.query = ""
        self.search_var = SimpleNamespace(get=lambda: self.query)
        self._selected = None
        self._sort_col = "id"
        self._sort_desc = False
        self._update_sort_headers = Mock()
        self._set_status = Mock()
        self._update_pdf_tools_label = Mock()
        self._render_candidates_for_page = Mock()
        self._reload_selected_into_form = Mock(
            side_effect=lambda: self._render_candidates_for_page(self._selected.page - 1)
        )


class ItemListPerformanceTests(unittest.TestCase):
    def test_search_retains_accents_tokens_fields_order_and_match_tags(self):
        panel = ItemsPanel([
            make_item(1), make_item(2, description="Forceps", material="Titanium"),
            make_item(3, description_vietnames_from_excel="Kẹp mạch máu"),
        ])
        for query, expected in [
            ("TIM, do", ["1", "3"]), ("tim đỏ", ["1", "3"]),
            ("titanium", ["2"]), ("kep mach", ["3"]),
            ("scissors A-2", ["2"]), ("no such product", []),
            ("", ["1", "2", "3"]),
        ]:
            with self.subTest(query=query):
                panel.query = query
                panel._filter_items()
                self.assertEqual(list(panel.items_tree.rows), expected)
                for row in panel.items_tree.rows.values():
                    self.assertEqual(row["tags"], ("match",) if query else ())

    def test_cached_search_and_dates_follow_edited_and_replaced_items(self):
        item = make_item(validated=True, validated_at="2026-01-01T12:00:00")
        panel = ItemsPanel([item])
        panel.query = "tim do"
        panel._filter_items()
        self.assertEqual(panel.items_tree.rows["1"]["values"][-1], "01/01/2026 12:00:00")
        item.description = "Forceps"
        panel._filter_items()
        self.assertEqual(panel.items_tree.rows, {})
        panel.state.items_cache = [make_item(validated=False, validated_at="bad date")]
        panel._filter_items()
        self.assertEqual(panel.items_tree.rows["1"]["values"][-1], "")
        self.assertEqual(panel._format_validated_at_vi("bad date"), "bad date")

    def test_typing_coalesces_and_refresh_cancels_pending_search(self):
        panel = ItemsPanel([make_item()])
        for query in ("t", "ti", "tim do"):
            panel.query = query
            panel._schedule_filter_items()
        self.assertEqual(len(panel.root.jobs), 1)
        panel.root.run_pending()
        self.assertEqual(list(panel.items_tree.rows), ["1"])
        panel.query = "titanium"
        panel._schedule_filter_items()
        panel.state.db = SimpleNamespace(list_items=lambda: [make_item(2, material="Titanium")])
        panel.refresh_items()
        self.assertEqual(panel.root.jobs, {})
        self.assertEqual(list(panel.items_tree.rows), ["2"])

    def test_sorting_still_toggles_and_keeps_search_filter(self):
        panel = ItemsPanel([make_item(2), make_item(1), make_item(3, description="Forceps")])
        panel.query = "tim do"
        panel._sort_by("code")
        self.assertEqual(list(panel.items_tree.rows), ["1", "2"])
        panel._sort_by("code")
        self.assertEqual(list(panel.items_tree.rows), ["2", "1"])

    def test_selection_requests_page_images_once_and_preserves_cancelled_edits(self):
        panel = ItemsPanel([make_item(1), make_item(2)])
        panel._filter_items()
        panel.items_tree.selection_set("1")
        panel._on_select_item()
        panel._render_candidates_for_page.assert_called_once_with(2)
        panel._handle_unsaved_before_switch = Mock(return_value=False)
        panel.items_tree.selection_set("2")
        panel._on_select_item()
        self.assertEqual(panel._selected.id, 1)
        self.assertEqual(panel.items_tree.selection(), ("1",))
        panel._reload_selected_into_form.assert_called_once()


class ThumbnailSelectionPerformanceTests(unittest.TestCase):
    def test_selection_updates_borders_and_preview_without_rebuilding_images(self):
        cells = [Mock(), Mock()]
        refs = [object(), object()]
        panel = SimpleNamespace(
            _thumb_cells=[("first.png", cells[0]), ("second.png", cells[1])],
            _thumb_refs=refs,
            _render_thumbnails=Mock(), _set_preview_image=Mock(),
        )
        ImagesControllerMixin._on_select_thumbnail(panel, "second.png")
        self.assertEqual(panel._selected_image_path, "second.png")
        self.assertIs(panel._thumb_refs, refs)
        cells[0].configure.assert_called_once_with(relief="flat", borderwidth=0)
        cells[1].configure.assert_called_once_with(relief="solid", borderwidth=2)
        panel._set_preview_image.assert_called_once_with("second.png")
        panel._render_thumbnails.assert_not_called()


class CatalogReadPerformanceTests(unittest.TestCase):
    def test_paths_are_resolved_once_per_read_and_refreshed_on_next_read(self):
        with TemporaryProject() as project:
            data_dir = project.create_runtime_layout()
            db = CatalogDB(data_dir / "sql" / "catalog.db", data_dir=data_dir)
            with closing(db.connect()) as conn:
                with conn:
                    conn.executemany(
                        "INSERT INTO items(code, pdf_path) VALUES(?,?)",
                        [(f"A-{i}", "catalog_pdfs/shared.pdf") for i in range(100)],
                    )
            with patch.object(db, "from_db_path", wraps=db.from_db_path) as resolver:
                first = db.list_items()
                self.assertEqual(len(first), 100)
                resolver.assert_called_once_with("catalog_pdfs/shared.pdf")
                second = db.list_items()
                self.assertEqual(resolver.call_count, 2)
                self.assertEqual(first, second)
            self.assertEqual(first[0].pdf_path, str((data_dir / "catalog_pdfs/shared.pdf").resolve()))


if __name__ == "__main__":
    unittest.main()
