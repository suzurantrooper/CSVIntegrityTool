# CSV Integrity Tool

A small Windows desktop tool that tidies up CSV files without changing your data.

- Opens a CSV and shows a preview.
- Keeps every value as text, so IDs like `00124` keep their leading zeros.
- Optional cleaning steps: trim surrounding spaces, remove fully empty rows,
  remove exact duplicate rows.
- Saves to a **new** file you choose. The original file is never changed.
- Shows a summary of what changed, including a warning for cells that start
  with `=`, `+`, `-` or `@` (spreadsheet apps may treat those as formulas).
- Rejects empty or broken files with a clear message and writes nothing.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (from python.org; tkinter is included)

No extra packages are needed.

## Run the app

From this folder (`excel-cleaner`):

```
python -m app.gui
```

1. Click **Open CSV...** and pick a file (try `samples\customers_messy.csv`).
2. Tick the cleaning options you want.
3. Click **Clean and Save As...** and choose a new file name.
4. Read the summary at the bottom of the window.

## Run the tests

From this folder:

```
python -m unittest -v
```

There is also a scripted GUI check (`python tests/scripted_gui_check.py`).
It drives the window with scripted dialog answers and is not a hands-on
test. `docs/gui-checks.md` has its results and, separately, a
user-reported hands-on workflow check.

## Build the Windows executable (optional)

Uses PyInstaller in a project-only virtual environment. From this folder:

```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name CSVIntegrityTool --paths . --distpath dist --workpath build --specpath build app\gui.py
```

The result is `dist\CSVIntegrityTool.exe`. `.venv\`, `build\` and `dist\` are
ignored by git. Built and start-tested with PyInstaller 6.22.3 and
Python 3.13.3. The exe is unsigned and not yet ready for clients.

## Project layout

```
app/
    cleaner.py      cleaning logic (no window code)
    gui.py          the Windows window (calls cleaner.py)
tests/
    test_cleaner.py automated tests
samples/            made-up example files, including broken ones
output/             a handy place to save cleaned files (ignored by git)
docs/
    how-it-works.md beginner walkthrough of every file
```

## Not in version 1

Excel (.xlsx) files, date conversion, cloud upload.

## Good to know

If you double-click a CSV to open it in Excel, Excel itself may show `00124`
as `124`. The file still contains `00124`; it is only Excel's display. Use
Excel's **Data > From Text/CSV** import and set the column to *Text* to see it.
