# smartcatalog/main.py
from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Optional

from smartcatalog.state import AppState
from smartcatalog.db.catalog_db import CatalogDB
from smartcatalog.ui.main_window import create_main_window


def _set_windows_app_id() -> None:
    """
    Ensure Windows taskbar uses this app identity instead of python.exe identity.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartCatalog.App")
    except Exception:
        pass


def _apply_window_icon_windows(window: tk.Misc, icon_path: Path) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        window.update_idletasks()
        hwnd = int(window.winfo_id())
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        hicon = ctypes.windll.user32.LoadImageW(
            None,
            str(icon_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if hicon:
            # Set icon for this specific window.
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
            # Set icon at class level so taskbar/alt-tab pick it consistently.
            GCLP_HICON = -14
            GCLP_HICONSM = -34
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon)
                ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon)
            else:
                ctypes.windll.user32.SetClassLongW(hwnd, GCLP_HICON, hicon)
                ctypes.windll.user32.SetClassLongW(hwnd, GCLP_HICONSM, hicon)
    except Exception:
        pass


def _resolve_icon_path(project_dir: Path) -> Optional[Path]:
    candidates = [
        project_dir / "icon" / "icon.ico",
        project_dir / "icons" / "icon.ico",
    ]
    for icon_path in candidates:
        if icon_path.exists():
            return icon_path
    return None


def _apply_window_icon(window: tk.Misc, project_dir: Path) -> None:
    icon_path = _resolve_icon_path(project_dir)
    if not icon_path:
        return
    try:
        # Use default so all toplevel windows inherit on Tk side.
        window.iconbitmap(default=str(icon_path))
    except Exception:
        pass
    try:
        try:
            window.iconbitmap(str(icon_path))
        except Exception:
            pass
        _apply_window_icon_windows(window, icon_path)
    except Exception:
        pass


def _load_splash_icon_photo(project_dir: Path, size: int = 24):
    icon_path = _resolve_icon_path(project_dir)
    if not icon_path:
        return None
    try:
        from PIL import Image, ImageTk
        with Image.open(icon_path) as pil:
            pil = pil.convert("RGBA")
            pil.thumbnail((size, size))
            return ImageTk.PhotoImage(pil)
    except Exception:
        return None


def _show_startup_splash(root: tk.Tk, project_dir: Path) -> tuple[tk.Toplevel, ttk.Progressbar]:
    splash = tk.Toplevel(root)
    _apply_window_icon(splash, project_dir)
    splash.title("SmartCatalog")
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(bg="#E9EEF5")

    outer = tk.Frame(splash, bg="#E9EEF5", padx=14, pady=14)
    outer.pack(fill="both", expand=True)

    card = tk.Frame(outer, bg="#FFFFFF", bd=0, highlightthickness=1, highlightbackground="#D7DFEA")
    card.pack(fill="both", expand=True)

    accent = tk.Frame(card, bg="#0EA5E9", height=3)
    accent.pack(fill="x")

    body = tk.Frame(card, bg="#FFFFFF", padx=20, pady=18)
    body.pack(fill="both", expand=True)

    header = tk.Frame(body, bg="#FFFFFF")
    header.pack(fill="x")

    splash_icon = _load_splash_icon_photo(project_dir, size=24)
    if splash_icon is not None:
        icon_label = tk.Label(header, image=splash_icon, bg="#FFFFFF")
        icon_label.image = splash_icon  # keep a strong ref
        icon_label.pack(side="left")
    else:
        badge = tk.Canvas(header, width=24, height=24, bg="#FFFFFF", highlightthickness=0)
        badge.pack(side="left")
        badge.create_oval(2, 2, 22, 22, fill="#0EA5E9", outline="#0EA5E9")
        badge.create_text(12, 12, text="S", fill="#FFFFFF", font=("Segoe UI", 10, "bold"))

    text_col = tk.Frame(header, bg="#FFFFFF")
    text_col.pack(side="left", padx=(10, 0))
    tk.Label(
        text_col,
        text="SmartCatalog",
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 15, "bold"),
    ).pack(anchor="w")
    tk.Label(
        text_col,
        text="\u0110ang kh\u1edfi \u0111\u1ed9ng h\u1ec7 th\u1ed1ng",
        bg="#FFFFFF",
        fg="#64748B",
        font=("Segoe UI", 10),
    ).pack(anchor="w")

    ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(14, 12))

    style = ttk.Style(splash)
    style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor="#E2E8F0",
        background="#0EA5E9",
        bordercolor="#E2E8F0",
        lightcolor="#38BDF8",
        darkcolor="#0284C7",
        thickness=7,
    )
    bar = ttk.Progressbar(body, mode="indeterminate", length=340, style="Splash.Horizontal.TProgressbar")
    bar.pack(fill="x")
    bar.start(11)

    tk.Label(
        body,
        text="Vui l\u00f2ng ch\u1edd trong gi\u00e2y l\u00e1t...",
        bg="#FFFFFF",
        fg="#64748B",
        font=("Segoe UI", 9),
    ).pack(anchor="w", pady=(10, 0))

    w, h = 440, 200
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = int((sw - w) / 2)
    y = int((sh - h) / 2)
    splash.geometry(f"{w}x{h}+{x}+{y}")
    return splash, bar


def start_ui(project_dir: Optional[Path] = None) -> None:
    _set_windows_app_id()
    root = tk.Tk()
    root.withdraw()
    resolved_project_dir = Path(project_dir).resolve() if project_dir else Path(__file__).resolve().parents[2]
    _apply_window_icon(root, resolved_project_dir)
    splash, splash_bar = _show_startup_splash(root, resolved_project_dir)

    def _boot() -> None:
        # Get screen size
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()

        # Use a % of screen (recommended)
        w = int(screen_w * 0.9)
        h = int(screen_h * 0.85)

        root.geometry(f"{w}x{h}+50+50")
        root.minsize(1000, 700)

        root.title("SmartCatalog \u2013 Tr\u00edch xu\u1ea5t & \u0110\u1ed1i chi\u1ebfu s\u1ea3n ph\u1ea9m")

        state = AppState(project_dir=resolved_project_dir)

        state.db = CatalogDB(state.db_path, data_dir=state.data_dir)

        main_window = create_main_window(root, state)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Keep splash until first DB load is rendered in the UI.
        try:
            main_window.refresh_items()
            root.update_idletasks()
        except Exception:
            pass

        splash_bar.stop()
        splash.destroy()
        root.deiconify()
        # Re-apply after deiconify; some Windows environments reset icon then.
        _apply_window_icon(root, resolved_project_dir)

    root.after(60, _boot)
    root.mainloop()


if __name__ == "__main__":
    start_ui()
