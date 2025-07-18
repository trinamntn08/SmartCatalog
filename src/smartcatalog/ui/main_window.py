import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import pandas as pd
import os

from smartcatalog.loader.data_input_loader import load_data_from_docx
from smartcatalog.loader.catalog_loader import load_catalog_excel

catalog_df = None
vi_en_dict = {}
current_dict_path = None

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

def load_catalog_file(status_var):
    global catalog_df
    filepath = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
    if not filepath:
        return
    try:
        catalog_df = load_catalog_excel(filepath)
        status_var.set(f"✅ Đã tải catalog: {os.path.basename(filepath)}")
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể tải catalog: {str(e)}")
        status_var.set("❌ Tải catalog thất bại")

def load_dictionary_file(status_var, treeview):
    global vi_en_dict, current_dict_path
    filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not filepath:
        return
    try:
        df = pd.read_csv(filepath, keep_default_na=False)
        vi_en_dict = dict(zip(df["vietnamese"], df["english"]))
        current_dict_path = filepath
        status_var.set(f"✅ Đã tải từ điển: {os.path.basename(filepath)} ({len(vi_en_dict)} mục)")
        for item in treeview.get_children():
            treeview.delete(item)
        for vi, en in vi_en_dict.items():
            treeview.insert("", "end", values=(vi, en))
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể tải từ điển: {str(e)}")
        status_var.set("❌ Tải từ điển thất bại")

def save_dictionary_file(status_var, treeview):
    global current_dict_path
    if not current_dict_path:
        messagebox.showwarning("Chưa có file", "Bạn cần tải từ điển trước khi lưu.")
        return

    cleaned_data = []
    for item in treeview.get_children():
        vi, en = treeview.item(item, "values")
        if vi.strip() or en.strip():  # <- allow saving partial entries
            cleaned_data.append((vi.strip(), en.strip()))

    if not cleaned_data:
        messagebox.showerror("Lỗi", "Từ điển rỗng hoặc định dạng không hợp lệ.")
        return

    try:
        df = pd.DataFrame(cleaned_data, columns=["vietnamese", "english"])
        df.to_csv(current_dict_path, index=False)
        status_var.set(f"💾 Đã lưu từ điển: {os.path.basename(current_dict_path)} ({len(df)} mục)")
        messagebox.showinfo("Thành công", "Từ điển đã được lưu.")
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể lưu từ điển: {str(e)}")


def add_empty_row(treeview):
    treeview.insert("", "end", values=("", ""))

def on_double_click(event, treeview):
    col_id = treeview.identify_column(event.x)
    row_id = treeview.identify_row(event.y)

    if not row_id:
        # Add a new row and target that
        treeview.insert("", "end", values=("", ""))
        row_id = treeview.get_children()[-1]

    if col_id not in ("#1", "#2"):
        return

    bbox = treeview.bbox(row_id, col_id)
    if not bbox:
        return

    x, y, width, height = bbox
    current_value = treeview.set(row_id, col_id)

    entry = tk.Entry(treeview)
    entry.place(x=x, y=y, width=width, height=height)
    entry.insert(0, current_value)
    entry.focus_set()

    def save_edit(event=None):
        new_value = entry.get()
        values = list(treeview.item(row_id, "values"))

        # Convert col_id to column index
        col_index = int(col_id.replace("#", "")) - 1
        values[col_index] = new_value

        # Set the full row values back
        treeview.item(row_id, values=values)
        entry.destroy()

    entry.bind("<Return>", save_edit)
    entry.bind("<FocusOut>", save_edit)




def start_ui():
    root = tk.Tk()
    root.title("SmartCatalog – Trích xuất & Đối chiếu sản phẩm")

    # Main content layout
    content_frame = tk.Frame(root)
    content_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Left side
    left_frame = tk.Frame(content_frame)
    left_frame.pack(side="left", fill="both", expand=True)

    # Button bar at top of left panel
    btn_inner_frame = tk.Frame(left_frame)
    btn_inner_frame.pack(fill="x", pady=(0, 5))
    tk.Button(btn_inner_frame, text="📄 Tải file word (.docx)", command=lambda: load_word_file(word_display)).pack(side="left", padx=5)
    tk.Button(btn_inner_frame, text="📊 Tải catalog (.xlsx)", command=lambda: load_catalog_file(status_var)).pack(side="left", padx=5)

    # Then the word display
    word_display = scrolledtext.ScrolledText(left_frame, wrap="word", width=60)
    word_display.pack(fill="both", expand=True)

    # Right side
    right_frame = tk.Frame(content_frame)
    right_frame.pack(side="right", fill="both", padx=5)

    # Dictionary control buttons in a single row
    dict_btn_frame = tk.Frame(right_frame)
    dict_btn_frame.pack(side="top", pady=5)
    tk.Button(dict_btn_frame, text="📘 Tải từ điển (.csv)", command=lambda: load_dictionary_file(status_var, tree)).pack(side="left", padx=5)
    tk.Button(dict_btn_frame, text="💾 Lưu từ điển", command=lambda: save_dictionary_file(status_var, tree)).pack(side="left", padx=5)

    # Dictionary table
    tree = ttk.Treeview(right_frame, columns=("Vietnamese", "English"), show="headings", height=30)
    tree.heading("Vietnamese", text="Vietnamese")
    tree.heading("English", text="English")
    tree.column("Vietnamese", width=150)
    tree.column("English", width=150)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda e: on_double_click(e, tree))

    status_var = tk.StringVar(value="Chưa tải dữ liệu")
    tk.Label(root, textvariable=status_var, fg="blue").pack(side="bottom", pady=5)

    root.mainloop()
