r"""Opt-in Tk benchmark using a generated catalog, never the user's database.

Run from the repository root:
    .\.venv-agent\Scripts\python.exe tests/benchmark_performance.py --items 10000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.ui.controllers.items_controller import ItemsControllerMixin


class BenchmarkPanel(ItemsControllerMixin):
    pass


def run_benchmark(count: int) -> dict[str, float | int]:
    result: dict[str, float | int] = {"items": count}
    import_probe = (
        "import sys,time; sys.path.insert(0,'src'); "
        "t=time.perf_counter(); import smartcatalog.main; "
        "print(time.perf_counter()-t)"
    )
    result["entry_import_seconds"] = float(subprocess.check_output(
        [sys.executable, "-c", import_probe], cwd=ROOT, text=True,
    ).strip())
    with tempfile.TemporaryDirectory(prefix="smartcatalog-benchmark-") as directory:
        db = CatalogDB(Path(directory) / "catalog.db", data_dir=directory)
        conn = db.connect()
        try:
            conn.executemany(
                "INSERT INTO items(code,description,pdf_path,page,validated,validated_at) VALUES(?,?,?,?,?,?)",
                [(f"A-{i:05}", "Kéo phẫu thuật tim đỏ mô tả sản phẩm " * 4,
                  "catalog_pdfs/catalog.pdf", i // 20 + 1, 1, "2026-01-01 12:00:00")
                 for i in range(count)],
            )
            conn.commit()
        finally:
            conn.close()
        started = time.perf_counter()
        items = db.list_items()
        result["database_read_seconds"] = time.perf_counter() - started
        root = tk.Tk()
        root.withdraw()
        try:
            panel = BenchmarkPanel()
            panel.root = root
            panel.state = SimpleNamespace(items_cache=items)
            panel.search_var = tk.StringVar(root, value="")
            panel.items_tree = ttk.Treeview(root, columns=[str(i) for i in range(14)])
            for key, query in (
                ("initial_table_seconds", ""),
                ("first_search_seconds", "tim do"),
                ("repeat_search_seconds", "tim do"),
                ("no_match_search_seconds", "nonmatching"),
            ):
                panel.search_var.set(query)
                started = time.perf_counter()
                panel._filter_items()
                result[key] = time.perf_counter() - started
        finally:
            root.destroy()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, default=10000)
    args = parser.parse_args()
    if args.items < 1:
        parser.error("--items must be positive")
    print(json.dumps(run_benchmark(args.items), indent=2))
