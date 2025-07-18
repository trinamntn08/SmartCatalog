# src/smartcatalog/ui/main_window.py

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd

from smartcatalog.loader.data_input_loader import load_data_from_docx
from smartcatalog.loader.catalog_loader import load_catalog_excel



catalog_df = None

# Load word file
def load_word_file(display_widget):
    filepath = filedialog.askopenfilename(filetypes=[("Word Files", "*.docx")])
    if not filepath:
        return
    try:
        result = load_data_from_docx(filepath)
        display_widget.delete("1.0", tk.END)
        if result:
            for line in result:
                display_widget.insert(tk.END, line + "\n\n")
        else:
            display_widget.insert(tk.END, "Không tìm thấy nội dung yêu cầu.")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

# Load Catalog file
def load_catalog_file(status_var):
    global catalog_df
    filepath = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
    if not filepath:
        return
    try:
        catalog_df = load_catalog_excel(filepath)
        status_var.set(f"✅ Đã tải: {filepath.split('/')[-1]}")
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể tải catalog: {str(e)}")
        status_var.set("❌ Tải catalog thất bại")

def start_ui():
    root = tk.Tk()
    root.title("SmartCatalog – Trích xuất & Đối chiếu sản phẩm")

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    ehsmt_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=30)
    ehsmt_display.pack(padx=10, pady=10)

    catalog_status = tk.StringVar()
    catalog_status.set("Catalog chưa được tải")
    status_label = tk.Label(root, textvariable=catalog_status, fg="blue")
    status_label.pack()

    load_ehsmt_btn = tk.Button(btn_frame, text="📄 Tải file word (.docx)", command=lambda: load_word_file(ehsmt_display))
    load_ehsmt_btn.grid(row=0, column=0, padx=10)

    load_catalog_btn = tk.Button(btn_frame, text="📊 Tải catalog (.xlsx)", command=lambda: load_catalog_file(catalog_status))
    load_catalog_btn.grid(row=0, column=1, padx=10)

    root.mainloop()
