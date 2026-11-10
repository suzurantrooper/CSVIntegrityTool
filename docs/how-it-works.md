# How CSV Integrity Tool works

This guide explains every file in the project and what happens when you clean a file.

## The big idea: logic and window are separate

```
gui.py  (buttons, dialogs, preview)
   |
   |  calls
   v
cleaner.py  (load, clean, save, summary)   <---  test_cleaner.py also calls these
```

`cleaner.py` never shows a window, and `gui.py` never reads or writes CSV
files itself. This means the tests can check all the important rules
without clicking anything, and the window could later be replaced (for
example by a web page) without touching the cleaning rules.

## File by file

### `app/cleaner.py` - the cleaning logic

| Part | What it does |
|---|---|
| `CsvCleanerError` | The one kind of error the app shows to users. Its message is always plain English. |
| `OutputExistsError` | A special `CsvCleanerError` meaning "that output file already exists and you did not agree to replace it". |
| `CsvData` | Holds a loaded file: `header` (the column names) and `rows` (everything else). |
| `CleanOptions` | The three tick boxes: `trim_spaces`, `remove_empty_rows`, `remove_duplicates`. |
| `CleanResult` | The cleaned header and rows, plus the counts used in the summary. |
| `load_csv(path)` | Reads the file as UTF-8 text and splits it into rows with Python's `csv` module in **strict** mode. Every value stays a string. Stops with a clear error if the file is empty, has bad quotes, has a row with the wrong number of values, or is not UTF-8. |
| `clean(data, options)` | Runs the chosen steps in a fixed order (see below) and counts what changed. |
| `find_formula_cells(...)` | Finds cells starting with `=`, `+`, `-` or `@`. It only reports them; it never changes them. |
| `save_csv(result, output, source, replace_existing)` | Writes the result safely (see "Safe saving" below). |
| `is_same_file(a, b)` | Checks whether two paths are really the same file, even if typed differently (`C:\x\A.csv` vs `c:\x\.\a.csv`). |
| `build_summary(result, output)` | Turns the counts and warnings into the text shown in the window. |

Names starting with `_` (like `_trim_cells`) are small helpers used only
inside this file.

### `app/gui.py` - the window

Built with **tkinter**, which comes with Python on Windows.

- `CsvCleanerApp.__init__` builds the window: an Open button, a preview
  table (first 100 rows), three tick boxes, a Save button and a summary box.
- `open_file` asks for a file, calls `load_csv`, and fills the preview. If
  loading fails, it shows the error message and nothing else changes.
- `clean_and_save`:
  1. calls `clean` with the ticked options,
  2. warns about possible formulas and lets you cancel,
  3. asks where to save,
  4. refuses if you picked the original file,
  5. asks before replacing a file that already exists,
  6. calls `save_csv`, then shows the summary.
- `main` starts the program. Run it with `python -m app.gui`.

### `app/__init__.py`

An almost empty file. It tells Python that `app` is a *package*, which is
what makes `python -m app.gui` and `from app.cleaner import ...` work.

### `tests/test_cleaner.py` - automated tests

Uses Python's built-in `unittest`. Every test creates its own temporary
folder, so your real files are never touched. Test groups:

| Group | Checks |
|---|---|
| `TestImportExport` | Values with commas, quotes and line breaks survive a load-and-save round trip; UTF-8 with and without BOM; Windows line endings. |
| `TestLeadingZeroIds` | `00124` stays `00124` when loaded, cleaned and saved. |
| `TestWhitespace` | Spaces at the start/end are trimmed (spaces in the middle are kept); the header is trimmed too; nothing is trimmed when the option is off. |
| `TestEmptyRows` | Blank lines and rows of empty cells are removed; partly empty rows are kept. |
| `TestDuplicates` | Exact duplicates are removed, the first copy is kept, order is kept; case differences are not duplicates. |
| `TestMalformedInput` | Empty file, blank header, wrong number of values, bad quotes, non-UTF-8, missing file. |
| `TestHeaderOnly` | A file with only column names is accepted, saved, and the summary says there were no data rows. |
| `TestFormulaWarnings` | `=`, `+`, `-`, `@` cells are reported with row and column, saved unchanged, and listed in the summary. |
| `TestSourceFileProtection` | Saving over the original is refused (even if the path is spelled differently), and the original's bytes never change. |
| `TestSafeSaving` | Existing files are only replaced with permission; a failed save leaves no partial file and no temporary file. |
| `TestSampleFiles` | The files in `samples/` give the results described below. |

### `tests/__init__.py`

Empty. It lets `python -m unittest` find the tests folder.

### `samples/` - made-up example data

All names and emails are invented (`example.com` addresses are reserved for examples).

| File | What it shows |
|---|---|
| `customers_messy.csv` | 9 data rows. Cleaning with all options on: 3 cells trimmed, 2 empty rows removed, 2 duplicates removed (one only matches after trimming), 5 rows written, 2 formula warnings (`=1+1`, `-call back`). |
| `header_only.csv` | Column names only. Accepted; output is just the header. |
| `empty.csv` | Zero bytes. Rejected: "The file is empty." |
| `malformed_wrong_columns.csv` | Line 3 has an extra value. Rejected with the line number. |
| `malformed_bad_quotes.csv` | A quote mark is never closed. Rejected. |

### `output/`

A convenient place to save cleaned files. Git ignores its contents
(`.gitkeep` is just there so the empty folder is kept).

### `.gitignore`

Tells git not to track generated output, virtual environments, Python
cache files and build artifacts.

## The cleaning steps, in order

1. **Trim spaces** - removes spaces, tabs and line breaks at the start and
   end of every cell, including the column names. `"  Ava  Lee "` becomes
   `"Ava  Lee"`.
2. **Remove empty rows** - removes rows where every cell is blank.
3. **Remove duplicates** - removes a row if an identical row appeared
   earlier. Comparison is exact (case-sensitive), after step 1 if it is on.

Trimming runs first on purpose: `00125,Ben,York` and `00125,Ben,  York  `
only count as duplicates once the extra spaces are gone.

## Safe saving

`save_csv` protects your files in three ways:

1. **The original is off limits.** If the output path is the source file,
   it stops with an error. The source file is only ever opened for reading.
2. **No surprise replacements.** If the output file already exists, it is
   only replaced when `replace_existing=True` (the window asks you first).
3. **All or nothing.** The data is written to a hidden temporary file
   (`.csv-cleaner-....tmp`) *in the same folder* as the output. Only when
   the whole write has finished is it renamed to the final name with
   `os.replace`, which happens in one step. If anything goes wrong (disk full,
   file open in Excel...), the temporary file is deleted and the old output
   file, if any, is left exactly as it was.

The output is written as UTF-8 with a BOM, which helps Excel show accented
letters correctly.

## Why some cells get a "formula" warning

If a cell starts with `=`, `+`, `-` or `@`, Excel and similar apps may run
it as a formula when the CSV is opened. That can show wrong values or, with
untrusted data, be a security risk ("CSV injection"). V1 does **not** change
these values. It warns you before saving and lists them in the summary.
Note that ordinary negative numbers such as `-5` are also listed.
