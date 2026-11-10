"""
gui.py - the simple Windows window for CSV Integrity Tool.

Run it from the project folder with:
    python -m app.gui

This file only handles buttons, dialogs and the preview table.
All of the real work is done by the functions in cleaner.py.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.cleaner import (
    CleanOptions,
    CsvCleanerError,
    build_summary,
    clean,
    is_same_file,
    load_csv,
    save_csv,
)

PREVIEW_ROW_LIMIT = 100
PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT_FOLDER = os.path.join(PROJECT_FOLDER, "output")


class CsvCleanerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source_path = None   # the file the user opened
        self.data = None          # its contents (a CsvData object)

        root.title("CSV Integrity Tool")
        root.geometry("900x600")
        root.minsize(600, 450)

        # --- Top: open button and file name ---
        top = ttk.Frame(root, padding=8)
        top.pack(side="top", fill="x")
        ttk.Button(top, text="Open CSV...", command=self.open_file).pack(side="left")
        self.file_label = ttk.Label(top, text="No file loaded")
        self.file_label.pack(side="left", padx=8)

        # --- Bottom: summary box (packed before the preview so it never gets squeezed out) ---
        summary_frame = ttk.LabelFrame(root, text="Summary", padding=4)
        summary_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.summary_text = tk.Text(summary_frame, height=8, wrap="word", state="disabled")
        self.summary_text.pack(fill="both", expand=True)

        # --- Cleaning options and the save button ---
        options_frame = ttk.LabelFrame(root, text="Cleaning options", padding=8)
        options_frame.pack(side="bottom", fill="x", padx=8, pady=8)
        self.trim_var = tk.BooleanVar(value=True)
        self.empty_var = tk.BooleanVar(value=True)
        self.duplicates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Trim spaces at the start and end of each cell",
                        variable=self.trim_var).pack(anchor="w")
        ttk.Checkbutton(options_frame, text="Remove fully empty rows",
                        variable=self.empty_var).pack(anchor="w")
        ttk.Checkbutton(options_frame, text="Remove exact duplicate rows (keeps the first copy)",
                        variable=self.duplicates_var).pack(anchor="w")
        self.save_button = ttk.Button(options_frame, text="Clean and Save As...",
                                      command=self.clean_and_save, state="disabled")
        self.save_button.pack(anchor="w", pady=(8, 0))

        # --- Middle: preview table with scroll bars ---
        preview_frame = ttk.LabelFrame(root, text=f"Preview (first {PREVIEW_ROW_LIMIT} rows)",
                                       padding=4)
        preview_frame.pack(side="top", fill="both", expand=True, padx=8)
        self.table = ttk.Treeview(preview_frame, show="headings")
        y_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.table.yview)
        x_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)

    # -- Button actions ------------------------------------------------------

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open a CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return  # the user pressed Cancel

        try:
            data = load_csv(path)
        except CsvCleanerError as error:
            messagebox.showerror("Could not open the file", str(error))
            return

        self.source_path = path
        self.data = data
        self.file_label.config(
            text=f"{os.path.basename(path)}  -  {len(data.rows)} data rows, "
                 f"{len(data.header)} columns"
        )
        self.show_preview()
        self.save_button.config(state="normal")
        if data.rows:
            self.set_summary("")
        else:
            self.set_summary("This file has a header row but no data rows. You can still "
                             "save it; the output will contain only the header row.")

    def clean_and_save(self):
        if self.data is None:
            return

        options = CleanOptions(
            trim_spaces=self.trim_var.get(),
            remove_empty_rows=self.empty_var.get(),
            remove_duplicates=self.duplicates_var.get(),
        )
        result = clean(self.data, options)

        # Warn about possible formulas BEFORE saving. The values are not changed.
        if result.formula_warnings:
            go_on = messagebox.askokcancel(
                "Possible formulas",
                f"{len(result.formula_warnings)} cell(s) begin with =, +, - or @.\n\n"
                "Spreadsheet apps such as Excel may treat these as formulas when the file "
                "is opened. The values will be saved unchanged.\n\nContinue saving?",
                icon="warning",
            )
            if not go_on:
                return

        file_stem = os.path.splitext(os.path.basename(self.source_path))[0]
        initial_folder = DEFAULT_OUTPUT_FOLDER if os.path.isdir(DEFAULT_OUTPUT_FOLDER) else None
        output_path = filedialog.asksaveasfilename(
            title="Save the cleaned CSV as",
            initialdir=initial_folder,
            initialfile=f"{file_stem}_cleaned.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            confirmoverwrite=False,  # we ask ourselves below, after checking for the original
        )
        if not output_path:
            return  # the user pressed Cancel

        if is_same_file(output_path, self.source_path):
            messagebox.showerror("Choose a different file",
                                 "You cannot save over the original file. Choose a new file name.")
            return

        replace_existing = False
        if os.path.exists(output_path):
            replace_existing = messagebox.askyesno(
                "Replace file?",
                f"{os.path.basename(output_path)} already exists.\n\nDo you want to replace it?",
                icon="warning",
            )
            if not replace_existing:
                return

        try:
            save_csv(result, output_path, self.source_path, replace_existing=replace_existing)
        except CsvCleanerError as error:
            messagebox.showerror("Could not save the file", str(error))
            return

        self.set_summary(build_summary(result, output_path))

    # -- Helpers -------------------------------------------------------------

    def show_preview(self):
        """Fill the table with the column names and the first rows of the file."""
        self.table.delete(*self.table.get_children())
        column_ids = [f"c{index}" for index in range(len(self.data.header))]
        self.table.configure(columns=column_ids)
        for column_id, name in zip(column_ids, self.data.header):
            self.table.heading(column_id, text=name)
            self.table.column(column_id, width=140, minwidth=60, stretch=False)
        for row in self.data.rows[:PREVIEW_ROW_LIMIT]:
            self.table.insert("", "end", values=row)

    def set_summary(self, text: str):
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.config(state="disabled")


def main():
    # Make the window sharp (not blurry) on high-resolution Windows screens.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # not on Windows, or an older Windows version

    root = tk.Tk()
    CsvCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
