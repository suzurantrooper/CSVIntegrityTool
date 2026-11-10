"""
cleaner.py - the cleaning logic for CSV Integrity Tool.

This file has NO user-interface code. The window (gui.py) and the tests
(tests/test_cleaner.py) both call the functions below, so the same rules
apply everywhere.

The main steps are:
    1. load_csv()       read a CSV file into a header row and data rows
    2. clean()          trim spaces, remove empty rows, remove duplicates
    3. save_csv()       write the result safely to a NEW file
    4. build_summary()  describe what changed in plain English

Every value is kept as text (a Python str) from start to finish, so an ID
such as 00124 is never turned into the number 124.
"""

import csv
import io
import os
import tempfile
from dataclasses import dataclass, field

# Spreadsheet apps (Excel, LibreOffice, Google Sheets) may treat a cell that
# starts with one of these characters as a formula when the CSV is opened.
FORMULA_PREFIXES = ("=", "+", "-", "@")

# How many formula warnings to list one by one in the summary.
MAX_WARNINGS_LISTED = 10


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CsvCleanerError(Exception):
    """A problem we can explain to the user in plain English."""


class OutputExistsError(CsvCleanerError):
    """The chosen output file already exists and replacing it was not confirmed."""


# ---------------------------------------------------------------------------
# Simple data containers
# ---------------------------------------------------------------------------

@dataclass
class CsvData:
    """The contents of a CSV file: the first row (column names) and the rest."""
    header: list[str]
    rows: list[list[str]]


@dataclass
class CleanOptions:
    """Which cleaning steps the user has switched on."""
    trim_spaces: bool = True
    remove_empty_rows: bool = True
    remove_duplicates: bool = True


@dataclass
class FormulaWarning:
    """One cell whose value starts with =, +, - or @."""
    row_number: int     # counted like a spreadsheet: the header is row 1
    column_name: str
    value: str


@dataclass
class CleanResult:
    """The cleaned data plus the numbers needed for the summary."""
    header: list[str]
    rows: list[list[str]]
    options: CleanOptions
    rows_read: int
    cells_trimmed: int = 0
    empty_rows_removed: int = 0
    duplicates_removed: int = 0
    formula_warnings: list[FormulaWarning] = field(default_factory=list)

    @property
    def rows_written(self) -> int:
        return len(self.rows)


# ---------------------------------------------------------------------------
# Step 1: load
# ---------------------------------------------------------------------------

def load_csv(path: str) -> CsvData:
    """Read a CSV file. Every value stays as text.

    The file is only opened for reading, so it is never changed.
    Raises CsvCleanerError with a clear message if the file cannot be used.
    """
    text = _read_text(path)
    if text.strip() == "":
        raise CsvCleanerError("The file is empty. There is nothing to clean.")

    # strict=True makes the csv module stop at bad quoting instead of guessing.
    reader = csv.reader(io.StringIO(text), strict=True)
    rows_with_line_numbers = []
    try:
        for row in reader:
            rows_with_line_numbers.append((reader.line_num, row))
    except csv.Error as error:
        raise CsvCleanerError(
            f"The file is not valid CSV (problem near line {reader.line_num}: {error}). "
            'Check for a missing or extra quote mark (").'
        ) from None

    first_line, header = rows_with_line_numbers[0]
    if _is_blank(header):
        raise CsvCleanerError(
            f"Line {first_line} should contain the column names, but it is blank."
        )

    rows = []
    for line_number, row in rows_with_line_numbers[1:]:
        # A completely blank row is allowed whatever its length; it is an
        # "empty row", which the user may choose to remove.
        if len(row) != len(header) and not _is_blank(row):
            raise CsvCleanerError(
                f"Line {line_number} has {len(row)} values, but the header has "
                f"{len(header)} columns. Every row must have the same number of values."
            )
        rows.append(row)

    return CsvData(header=header, rows=rows)


def _read_text(path: str) -> str:
    """Return the whole file as text, turning low-level errors into clear ones."""
    try:
        # "utf-8-sig" reads normal UTF-8 and also UTF-8 files that Excel saved
        # with a hidden marker (a "BOM") at the start.
        # newline="" lets the csv module handle line breaks inside quoted cells.
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            return file.read()
    except FileNotFoundError:
        raise CsvCleanerError(f"The file could not be found: {path}") from None
    except UnicodeDecodeError:
        raise CsvCleanerError(
            "The file is not saved as UTF-8 text. In Excel, use "
            "'Save As' > 'CSV UTF-8 (Comma delimited)' and try again."
        ) from None
    except OSError as error:
        raise CsvCleanerError(f"The file could not be opened: {error.strerror or error}") from None


# ---------------------------------------------------------------------------
# Step 2: clean
# ---------------------------------------------------------------------------

def clean(data: CsvData, options: CleanOptions) -> CleanResult:
    """Apply the chosen cleaning steps and return the result.

    The steps always run in this order:
        trim spaces -> remove empty rows -> remove duplicate rows
    The `data` passed in is not changed; new lists are returned.
    """
    header = list(data.header)
    rows = [list(row) for row in data.rows]
    rows_read = len(rows)

    # Trim spaces, tabs and line breaks at the start and end of every cell.
    cells_trimmed = 0
    if options.trim_spaces:
        header, count = _trim_cells(header)
        cells_trimmed += count
        trimmed_rows = []
        for row in rows:
            trimmed_row, count = _trim_cells(row)
            cells_trimmed += count
            trimmed_rows.append(trimmed_row)
        rows = trimmed_rows

    # Remove rows where every cell is blank.
    empty_rows_removed = 0
    if options.remove_empty_rows:
        kept_rows = [row for row in rows if not _is_blank(row)]
        empty_rows_removed = len(rows) - len(kept_rows)
        rows = kept_rows

    # Remove rows that exactly match an earlier row. The first copy is kept.
    duplicates_removed = 0
    if options.remove_duplicates:
        seen = set()
        kept_rows = []
        for row in rows:
            key = tuple(row)  # lists can't go in a set, tuples can
            if key in seen:
                duplicates_removed += 1
            else:
                seen.add(key)
                kept_rows.append(row)
        rows = kept_rows

    return CleanResult(
        header=header,
        rows=rows,
        options=options,
        rows_read=rows_read,
        cells_trimmed=cells_trimmed,
        empty_rows_removed=empty_rows_removed,
        duplicates_removed=duplicates_removed,
        formula_warnings=find_formula_cells(header, rows),
    )


def find_formula_cells(header: list[str], rows: list[list[str]]) -> list[FormulaWarning]:
    """List every cell that starts with =, +, - or @. Values are NOT changed."""
    warnings = []
    all_rows = [header] + rows
    for row_index, row in enumerate(all_rows):
        for column_index, value in enumerate(row):
            if value.startswith(FORMULA_PREFIXES):
                if column_index < len(header):
                    column_name = header[column_index]
                else:
                    column_name = f"column {column_index + 1}"
                warnings.append(FormulaWarning(row_index + 1, column_name, value))
    return warnings


def _trim_cells(row: list[str]) -> tuple[list[str], int]:
    """Return the row with each cell trimmed, plus how many cells changed."""
    trimmed_row = [cell.strip() for cell in row]
    changed = sum(1 for old, new in zip(row, trimmed_row) if old != new)
    return trimmed_row, changed


def _is_blank(row: list[str]) -> bool:
    """True if every cell in the row is empty or only spaces."""
    return all(cell.strip() == "" for cell in row)


# ---------------------------------------------------------------------------
# Step 3: save
# ---------------------------------------------------------------------------

def save_csv(result: CleanResult, output_path: str, source_path: str,
             replace_existing: bool = False) -> None:
    """Write the cleaned data to output_path safely.

    Safety rules:
      * Never write over the original (source) file.
      * Never replace an existing file unless replace_existing is True.
      * Write everything to a temporary file in the same folder first, and
        only move it into place once the whole write has succeeded. If
        anything fails, the temporary file is deleted and no partial output
        is left behind.
    """
    if is_same_file(output_path, source_path):
        raise CsvCleanerError(
            "The output file cannot be the original file. Choose a new file name."
        )
    if os.path.exists(output_path) and not replace_existing:
        raise OutputExistsError(f"The file already exists: {output_path}")

    folder = os.path.dirname(os.path.abspath(output_path))
    try:
        handle, temp_path = tempfile.mkstemp(prefix=".csv-cleaner-", suffix=".tmp", dir=folder)
    except OSError as error:
        raise CsvCleanerError(
            f"Could not write to the folder {folder}: {error.strerror or error}"
        ) from None

    try:
        # "utf-8-sig" adds the marker that helps Excel show accented letters correctly.
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(result.header)
            writer.writerows(result.rows)
        # os.replace swaps the finished file into place in one step.
        os.replace(temp_path, output_path)
    except Exception as error:
        _delete_quietly(temp_path)
        if isinstance(error, OSError):
            message = f"The file could not be saved: {error.strerror or error}."
            if isinstance(error, PermissionError):
                message += " If the file is open in another program such as Excel, close it and try again."
            raise CsvCleanerError(message + " No output file was created or changed.") from None
        raise


def is_same_file(path_a: str, path_b: str) -> bool:
    """True if both paths point to the same file (even if spelled differently)."""
    if os.path.exists(path_a) and os.path.exists(path_b):
        return os.path.samefile(path_a, path_b)
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _delete_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Step 4: summary
# ---------------------------------------------------------------------------

def build_summary(result: CleanResult, output_path: str | None = None) -> str:
    """Describe what the cleaning did, in plain English."""
    lines = []
    if result.rows_read == 0:
        lines.append("There were no data rows to clean. The output contains only the header row.")
        lines.append("")

    lines.append(f"Data rows read: {result.rows_read} (not counting the header)")
    lines.append(_step_line("Cells trimmed", result.options.trim_spaces, result.cells_trimmed))
    lines.append(_step_line("Empty rows removed", result.options.remove_empty_rows,
                            result.empty_rows_removed))
    lines.append(_step_line("Duplicate rows removed", result.options.remove_duplicates,
                            result.duplicates_removed))
    lines.append(f"Data rows written: {result.rows_written}")
    if output_path:
        lines.append(f"Saved to: {output_path}")

    warnings = result.formula_warnings
    if warnings:
        lines.append("")
        lines.append(
            f"WARNING: {len(warnings)} cell(s) begin with =, +, - or @. Spreadsheet apps "
            "such as Excel may treat these as formulas when the file is opened. "
            "The values were kept unchanged."
        )
        for warning in warnings[:MAX_WARNINGS_LISTED]:
            value = warning.value if len(warning.value) <= 60 else warning.value[:57] + "..."
            lines.append(f'  - Row {warning.row_number}, column "{warning.column_name}": {value}')
        if len(warnings) > MAX_WARNINGS_LISTED:
            lines.append(f"  ...and {len(warnings) - MAX_WARNINGS_LISTED} more.")

    return "\n".join(lines)


def _step_line(label: str, enabled: bool, count: int) -> str:
    if enabled:
        return f"{label}: {count}"
    return f"{label}: skipped (option was off)"
