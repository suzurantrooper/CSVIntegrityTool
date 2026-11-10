# Case study: cleaning a messy inventory export

*All data in this demo is synthetic. The shop, products and suppliers are invented.*

## The problem

A small hardware shop exported its stock list from two systems and pasted
the results into one CSV (`inventory_messy.csv`, 21 data rows). Before it
could be imported into a new stock system, it had several problems:

- **Duplicate items.** Two SKUs appeared twice word-for-word (`000418`,
  `000430`). A third, `000419`, appeared twice but one copy had extra spaces
  (`Brass Hinge 75mm ` and `  96`), so a plain "remove duplicates" would miss it.
- **Blank rows.** One empty line, one row of commas only, and one row of
  spaces only - all left over from copy-and-paste.
- **Stray spaces** at the start or end of names, quantities and prices
  (`  Steel Hinge 75mm`, `  88  `, `8.90 `). These break lookups and make
  numbers fail to import.
- **SKUs with leading zeros** (`000418`). Many tools silently turn these
  into `418`, which no longer matches the shop's labels.
- **Commas inside values** (`"Wood Screw 4x40, box of 200"`), which must stay
  correctly quoted or the columns shift.

## Cleaning choices

All three cleaning options were switched on, and they run in this order:

1. **Trim surrounding spaces** in every cell (spaces inside a value, such as
   `Steel Hinge 75mm`, are kept).
2. **Remove fully empty rows.**
3. **Remove exact duplicate rows**, keeping the first copy. Because trimming
   runs first, the spaced-out copy of `000419` is correctly recognised as a duplicate.

What was deliberately **not** changed:

- Every value is kept as text. `000418` stays `000418`; `2.40` stays `2.40`.
- No values were reworded, re-cased, converted or "corrected".
- The original file was not modified; the result was saved as a new file.
- No cells began with `=`, `+`, `-` or `@`, so there were no formula warnings.

## Before and after

| | Rows |
|---|---|
| Data rows in the original | **21** |
| Empty rows removed | 3 |
| Duplicate rows removed | 3 |
| Data rows in the cleaned file | **15** |

Cells trimmed: **13**. Every SKU from `000418` to `000432` appears exactly
once in the cleaned file, in its original order, with its leading zeros intact.

### Sample rows

Before:
```
000419,Brass Hinge 75mm ,Hardware,  96,2.40,Northgate Supply,A-01
000426,Sandpaper Assorted (pack of 10),Decorating,  88  ,3.75,Brightwall Supplies,C-02
000419,Brass Hinge 75mm,Hardware,96,2.40,Northgate Supply,A-01
```
After:
```
000419,Brass Hinge 75mm,Hardware,96,2.40,Northgate Supply,A-01
000426,Sandpaper Assorted (pack of 10),Decorating,88,3.75,Brightwall Supplies,C-02
```

## Deliverables

| File | What it is |
|---|---|
| `inventory_cleaned.csv` | The cleaned CSV, UTF-8, ready to import. |
| `summary.txt` | The change summary produced by the tool (rows read, cells trimmed, rows removed, rows written). |
| The original file | Returned untouched. |

## How it was produced

Cleaned with the CSV Cleaner in this repository (`app/cleaner.py`), run
through its Windows interface with the three options above. The summary in
`summary.txt` is the tool's own output; only the saved-file path was
shortened to a project-relative path.

Note: if you double-click a CSV to open it in Excel, Excel may *display*
`000418` as `418`. The file itself still contains `000418`.
