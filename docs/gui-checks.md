# GUI checks

## Status

| Check type | Done? |
|---|---|
| Automated logic tests (`python -m unittest`) | Yes - 44 tests pass |
| **Scripted GUI checks** (below) | Yes - all passed on 2026-11-07 |
| **User-reported hands-on workflow check** (below) | Partly - core clean-and-save workflow reported working on 2026-11-07; other steps not confirmed |
| Full hands-on GUI test of every step | **Not yet done** |

## User-reported hands-on workflow check - 2026-11-07

Reported by the project owner after using the window by hand. This record
lists only what was reported; it was not independently observed.

Input: `samples/customers_messy.csv`.

| Check | Result |
|---|---|
| Opened the GUI | Reported working |
| Loaded `customers_messy.csv` | Reported working |
| Used **Clean and Save As** | Reported working |
| Summary showed 9 read, 3 trimmed, 2 empty rows removed, 2 duplicates removed, 5 written, 2 formula warnings | Reported as observed |
| Output file saved successfully | Reported working |
| Launch method (`python -m app.gui` or `dist\CSVCleaner.exe`) | **Not confirmed** |
| Preview shows `00124` | **Not confirmed** |
| Saving to the original file is refused | **Not confirmed** |
| Asks before replacing an existing output file | **Not confirmed** |
| Formula warning pop-up before the save dialog | Not reported |
| Saved file checked in a text editor for `00124` | Not reported |

Because the launch method is not confirmed, this check does not show
whether the executable was used.

## Scripted GUI checks

### What "scripted GUI check" means

`tests/scripted_gui_check.py` creates the real `CsvCleanerApp` window and
calls its button actions (`open_file`, `clean_and_save`) directly. The
Windows **Open** and **Save As** dialogs and the pop-up message boxes are
replaced with scripted answers, and every message the app tries to show is
recorded.

It proves the window's logic and messages are correct. It does **not** prove:

- the real Windows file dialogs and pop-ups look and behave correctly,
- the layout is readable and usable at different window sizes or screen scaling,
- keyboard and mouse use work as expected.

Those still need a hands-on test.

Run it from the project folder:

```
python tests/scripted_gui_check.py
```

It saves `output/customers_messy_cleaned.csv` (ignored by git). It is not
part of `python -m unittest` because it opens a window and writes to `output/`.

### Scripted GUI check results - 2026-11-07, Windows 11, Python 3.13.3

Input: `samples/customers_messy.csv`, all three cleaning options ticked.

| # | Check | Result |
|---|---|---|
| 1 | Preview shows `00124` (not `124`) | Pass - first row displayed as `00124`; label "9 data rows, 5 columns" |
| 2 | Formula warning appears before the save dialog | Pass - "2 cell(s) begin with =, +, - or @ ... The values will be saved unchanged. Continue saving?" |
| 2 | Save dialog starts in `output/` with a suggested name | Pass - `customers_messy_cleaned.csv` |
| 3 | Summary: 9 read, 3 trimmed, 2 empty removed, 2 duplicates removed, 5 written, 2 formula warnings | Pass - warnings listed: row 5 `=1+1`, row 6 `-call back` |
| 4 | Saved file contains `00124` as text | Pass - raw file starts with UTF-8 BOM, `00124` present, quoted comma value intact, formula-like values unchanged |
| 5 | Saving to the original file is refused | Pass - "You cannot save over the original file. Choose a new file name."; original bytes unchanged |
| 5 | Same output name asks before replacing | Pass - "customers_messy_cleaned.csv already exists. Do you want to replace it?" |
| 5 | Answering No leaves the existing output untouched | Pass - same bytes and modified time |
| 5 | Answering Yes replaces it with no temporary files left | Pass |
| - | Original sample unchanged after all steps | Pass |
