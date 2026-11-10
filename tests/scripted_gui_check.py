"""Scripted GUI check: drives the real CsvCleanerApp with stand-in dialog answers.

This is NOT a hands-on GUI test. The Windows file dialogs and message boxes are
replaced with scripted answers, and every message the app shows is recorded.
Run from the project folder:  python tests/scripted_gui_check.py
It writes output/customers_messy_cleaned.csv (git-ignored).
"""
import os
import sys
import tkinter as tk
from unittest import mock

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)
from app import gui  # noqa: E402

SOURCE = os.path.join(PROJECT, "samples", "customers_messy.csv")
OUTPUT = os.path.join(PROJECT, "output", "customers_messy_cleaned.csv")
dialogs = []


def record(kind, answer):
    def fake(*args, **kwargs):
        title = args[0] if args else kwargs.get("title")
        message = args[1] if len(args) > 1 else kwargs.get("message", "")
        dialogs.append((kind, title, message, kwargs))
        return answer
    return fake


def show_dialogs(start):
    for kind, title, message, kwargs in dialogs[start:]:
        extra = f"  [initialdir={kwargs.get('initialdir')}, initialfile={kwargs.get('initialfile')}]" if kind == "save-as" else ""
        print(f"  DIALOG {kind}: {title!r}{extra}")
        if message:
            print("    " + message.replace("\n", "\n    "))


if os.path.exists(OUTPUT):
    os.remove(OUTPUT)
source_before = open(SOURCE, "rb").read()

root = tk.Tk()
app = gui.CsvCleanerApp(root)
root.update()

print("STEP 1: open", SOURCE)
with mock.patch.object(gui.filedialog, "askopenfilename", return_value=SOURCE):
    app.open_file()
root.update()
first = app.table.get_children()[0]
print("  file label:", app.file_label.cget("text"))
print("  preview rows shown:", len(app.table.get_children()))
print("  first preview row as displayed:", root.tk.call(app.table, "item", first, "-values"))
print("  checkboxes:", app.trim_var.get(), app.empty_var.get(), app.duplicates_var.get())

print("\nSTEP 2: Clean and Save As -> output folder")
n = len(dialogs)
with mock.patch.object(gui.messagebox, "askokcancel", record("ok/cancel", True)), \
     mock.patch.object(gui.filedialog, "asksaveasfilename", record("save-as", OUTPUT)), \
     mock.patch.object(gui.messagebox, "askyesno", record("yes/no", True)), \
     mock.patch.object(gui.messagebox, "showerror", record("error", None)):
    app.clean_and_save()
show_dialogs(n)

print("\nSTEP 3: summary box")
print("  " + app.summary_text.get("1.0", "end").strip().replace("\n", "\n  "))

print("\nSTEP 4: saved file as raw text")
raw = open(OUTPUT, "rb").read()
print("  starts with UTF-8 BOM:", raw.startswith(b"\xef\xbb\xbf"))
print("  " + raw.decode("utf-8-sig").replace("\r\n", "\n").strip().replace("\n", "\n  "))

print("\nSTEP 5a: try saving to the ORIGINAL file")
n = len(dialogs)
with mock.patch.object(gui.messagebox, "askokcancel", record("ok/cancel", True)), \
     mock.patch.object(gui.filedialog, "asksaveasfilename", record("save-as", SOURCE)), \
     mock.patch.object(gui.messagebox, "askyesno", record("yes/no", True)), \
     mock.patch.object(gui.messagebox, "showerror", record("error", None)):
    app.clean_and_save()
show_dialogs(n)
print("  original file unchanged:", open(SOURCE, "rb").read() == source_before)

print("\nSTEP 5b: save to the same output name again, answer NO to replace")
output_before = open(OUTPUT, "rb").read()
mtime_before = os.path.getmtime(OUTPUT)
n = len(dialogs)
with mock.patch.object(gui.messagebox, "askokcancel", record("ok/cancel", True)), \
     mock.patch.object(gui.filedialog, "asksaveasfilename", record("save-as", OUTPUT)), \
     mock.patch.object(gui.messagebox, "askyesno", record("yes/no", False)), \
     mock.patch.object(gui.messagebox, "showerror", record("error", None)):
    app.clean_and_save()
show_dialogs(n)
print("  output untouched after NO:", open(OUTPUT, "rb").read() == output_before
      and os.path.getmtime(OUTPUT) == mtime_before)

print("\nSTEP 5c: same name again, answer YES to replace")
n = len(dialogs)
with mock.patch.object(gui.messagebox, "askokcancel", record("ok/cancel", True)), \
     mock.patch.object(gui.filedialog, "asksaveasfilename", record("save-as", OUTPUT)), \
     mock.patch.object(gui.messagebox, "askyesno", record("yes/no", True)), \
     mock.patch.object(gui.messagebox, "showerror", record("error", None)):
    app.clean_and_save()
show_dialogs(n)
print("  replaced, same content:", open(OUTPUT, "rb").read() == output_before)
print("  leftover temp files in output:", [f for f in os.listdir(os.path.dirname(OUTPUT)) if f.endswith(".tmp")])
print("  original file still unchanged:", open(SOURCE, "rb").read() == source_before)

root.destroy()
