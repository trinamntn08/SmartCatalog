"""A product-independent preview canvas; workers supply rendered PNG bytes."""
from __future__ import annotations

from io import BytesIO
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk


class PdfDocumentView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, background="#525b66", highlightthickness=0)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._photo = None
        self.canvas.bind("<MouseWheel>", self._wheel)

    def _wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def clear(self):
        self.canvas.delete("all")
        self._photo = None

    def show_png(self, png: bytes, focus: tuple[float, float] | None = None):
        with Image.open(BytesIO(png)) as image:
            self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(8, 8, image=self._photo, anchor="nw")
        width, height = self._photo.width() + 16, self._photo.height() + 16
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if focus:
            self.canvas.xview_moveto(max(0, focus[0] / width - 0.2))
            self.canvas.yview_moveto(max(0, focus[1] / height - 0.2))
        else:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
