"""
Automated tests for app/cleaner.py.

Run from the project folder with:
    python -m unittest

Each test makes its own temporary folder with small made-up CSV files,
so the tests never touch your real files.
"""

import os
import tempfile
import unittest
from unittest import mock

from app.cleaner import (
    CleanOptions,
    CsvCleanerError,
    OutputExistsError,
    build_summary,
    clean,
    load_csv,
    save_csv,
)

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(PROJECT_FOLDER, "samples")

ALL_ON = CleanOptions(trim_spaces=True, remove_empty_rows=True, remove_duplicates=True)
ALL_OFF = CleanOptions(trim_spaces=False, remove_empty_rows=False, remove_duplicates=False)
BOM = b"\xef\xbb\xbf"


class CsvTestCase(unittest.TestCase):
    """Shared helpers: a fresh temporary folder for every test."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = temp.name

    def path(self, name):
        return os.path.join(self.folder, name)

    def write_text(self, name, text, encoding="utf-8"):
        with open(self.path(name), "w", encoding=encoding, newline="") as file:
            file.write(text)
        return self.path(name)

    def write_bytes(self, name, data):
        with open(self.path(name), "wb") as file:
            file.write(data)
        return self.path(name)

    def read_bytes(self, path):
        with open(path, "rb") as file:
            return file.read()

    def run_cleaner(self, text, options=ALL_ON):
        """Write `text` to a source file, clean it, save it, and return the result."""
        source = self.write_text("source.csv", text)
        result = clean(load_csv(source), options)
        save_csv(result, self.path("out.csv"), source)
        return result


class TestImportExport(CsvTestCase):

    def test_round_trip_keeps_every_value(self):
        text = ('id,name,notes\n'
                '1,"Lee, Ava","She said ""hi"""\n'
                '2,Ben,"Line one\nLine two"\n')
        self.run_cleaner(text, ALL_OFF)
        original = load_csv(self.path("source.csv"))
        saved = load_csv(self.path("out.csv"))
        self.assertEqual(saved, original)
        self.assertEqual(saved.rows[0], ["1", "Lee, Ava", 'She said "hi"'])
        self.assertEqual(saved.rows[1][2], "Line one\nLine two")

    def test_output_is_utf8_with_bom_and_keeps_accents(self):
        self.run_cleaner("name\nJosé\nZoë\n")
        data = self.read_bytes(self.path("out.csv"))
        self.assertTrue(data.startswith(BOM))
        self.assertEqual(load_csv(self.path("out.csv")).rows, [["José"], ["Zoë"]])

    def test_reads_file_saved_by_excel_with_bom(self):
        source = self.write_text("bom.csv", "id,name\n1,Ava\n", encoding="utf-8-sig")
        self.assertEqual(load_csv(source).header, ["id", "name"])

    def test_reads_windows_line_endings(self):
        source = self.write_text("crlf.csv", "id,name\r\n1,Ava\r\n")
        self.assertEqual(load_csv(source).rows, [["1", "Ava"]])


class TestLeadingZeroIds(CsvTestCase):

    def test_ids_stay_text_on_import(self):
        source = self.write_text("ids.csv", "id,amount\n00124,007.50\n")
        row = load_csv(source).rows[0]
        self.assertEqual(row, ["00124", "007.50"])
        self.assertIsInstance(row[0], str)

    def test_ids_survive_clean_and_save(self):
        self.run_cleaner("id,amount\n 00124 ,007.50\n00124,007.50\n")
        self.assertIn(b"00124,007.50", self.read_bytes(self.path("out.csv")))
        self.assertEqual(load_csv(self.path("out.csv")).rows, [["00124", "007.50"]])


class TestWhitespace(CsvTestCase):

    def test_trims_start_and_end_but_not_middle(self):
        result = self.run_cleaner("id,name\n 1 ,  Ava  Lee \t\n")
        self.assertEqual(result.rows, [["1", "Ava  Lee"]])
        self.assertEqual(result.cells_trimmed, 2)

    def test_header_is_trimmed(self):
        result = self.run_cleaner(" id , name \n1,Ava\n")
        self.assertEqual(result.header, ["id", "name"])

    def test_trim_off_keeps_spaces(self):
        result = self.run_cleaner("id,name\n 1 , Ava \n", ALL_OFF)
        self.assertEqual(result.rows, [[" 1 ", " Ava "]])
        self.assertEqual(load_csv(self.path("out.csv")).rows, [[" 1 ", " Ava "]])


class TestEmptyRows(CsvTestCase):

    TEXT = "id,name\n1,Ava\n\n,\n  ,  \n2,Ben\n"

    def test_removes_blank_lines_and_rows_of_empty_cells(self):
        result = self.run_cleaner(self.TEXT)
        self.assertEqual(result.rows, [["1", "Ava"], ["2", "Ben"]])
        self.assertEqual(result.empty_rows_removed, 3)

    def test_keeps_empty_rows_when_option_off(self):
        options = CleanOptions(trim_spaces=False, remove_empty_rows=False, remove_duplicates=False)
        result = self.run_cleaner(self.TEXT, options)
        self.assertEqual(result.rows_read, 5)
        self.assertEqual(result.rows_written, 5)

    def test_partly_empty_row_is_kept(self):
        result = self.run_cleaner("id,name\n1,\n")
        self.assertEqual(result.rows, [["1", ""]])


class TestDuplicates(CsvTestCase):

    def test_removes_exact_duplicates_and_keeps_first_copy_in_order(self):
        result = self.run_cleaner("id,name\n1,A\n2,B\n1,A\n3,C\n2,B\n")
        self.assertEqual(result.rows, [["1", "A"], ["2", "B"], ["3", "C"]])
        self.assertEqual(result.duplicates_removed, 2)

    def test_rows_that_differ_in_case_are_not_duplicates(self):
        result = self.run_cleaner("id,name\n1,ava\n1,Ava\n")
        self.assertEqual(result.duplicates_removed, 0)

    def test_rows_matching_after_trim_are_duplicates(self):
        text = "id,name\n1,Ava\n1, Ava \n"
        self.assertEqual(self.run_cleaner(text, ALL_ON).duplicates_removed, 1)
        no_trim = CleanOptions(trim_spaces=False, remove_empty_rows=True, remove_duplicates=True)
        self.assertEqual(clean(load_csv(self.path("source.csv")), no_trim).duplicates_removed, 0)

    def test_duplicates_kept_when_option_off(self):
        options = CleanOptions(trim_spaces=True, remove_empty_rows=True, remove_duplicates=False)
        result = self.run_cleaner("id,name\n1,A\n1,A\n", options)
        self.assertEqual(result.rows_written, 2)


class TestMalformedInput(CsvTestCase):

    def assert_load_error(self, path, expected_text):
        with self.assertRaises(CsvCleanerError) as caught:
            load_csv(path)
        self.assertIn(expected_text, str(caught.exception))

    def test_empty_file(self):
        self.assert_load_error(self.write_bytes("empty.csv", b""), "empty")

    def test_file_with_only_blank_lines(self):
        self.assert_load_error(self.write_text("blank.csv", "\n  \n\n"), "empty")

    def test_blank_header_line(self):
        self.assert_load_error(self.write_text("h.csv", "\nid,name\n1,A\n"), "column names")

    def test_row_with_too_many_values(self):
        self.assert_load_error(self.write_text("m.csv", "id,name\n1,A\n2,B,extra\n"), "Line 3")

    def test_row_with_too_few_values(self):
        self.assert_load_error(self.write_text("m.csv", "id,name,city\n1,A\n"), "Line 2")

    def test_unclosed_quote(self):
        self.assert_load_error(self.write_text("q.csv", 'id,name\n1,"Ava\n2,Ben\n'),
                               "not valid CSV")

    def test_text_after_closing_quote(self):
        self.assert_load_error(self.write_text("q.csv", 'id,name\n1,"Ava"x\n'), "not valid CSV")

    def test_file_that_is_not_utf8(self):
        self.assert_load_error(self.write_bytes("latin1.csv", b"id,name\n1,Jos\xe9\n"), "UTF-8")

    def test_missing_file(self):
        self.assert_load_error(self.path("does_not_exist.csv"), "could not be found")


class TestHeaderOnly(CsvTestCase):

    def test_header_only_file_loads(self):
        source = self.write_text("h.csv", "id,name\n")
        self.assertEqual(load_csv(source).rows, [])

    def test_header_only_without_final_line_break(self):
        source = self.write_text("h.csv", "id,name")
        self.assertEqual(load_csv(source).header, ["id", "name"])

    def test_header_only_output_and_summary(self):
        result = self.run_cleaner("id,name\n")
        self.assertEqual(self.read_bytes(self.path("out.csv")), BOM + b"id,name\r\n")
        self.assertIn("no data rows to clean", build_summary(result))


class TestFormulaWarnings(CsvTestCase):

    TEXT = "id,note\n1,=SUM(A1)\n2,+44 7700\n3,-5\n4,@user\n5,a = b\n"

    def test_detects_cells_starting_with_formula_characters(self):
        result = self.run_cleaner(self.TEXT)
        found = [(w.row_number, w.column_name, w.value) for w in result.formula_warnings]
        self.assertEqual(found, [
            (2, "note", "=SUM(A1)"),
            (3, "note", "+44 7700"),
            (4, "note", "-5"),
            (5, "note", "@user"),
        ])

    def test_values_are_saved_unchanged(self):
        self.run_cleaner(self.TEXT)
        self.assertEqual(load_csv(self.path("out.csv")), load_csv(self.path("source.csv")))

    def test_warning_is_in_summary(self):
        summary = build_summary(self.run_cleaner(self.TEXT))
        self.assertIn("WARNING: 4 cell(s)", summary)
        self.assertIn('Row 2, column "note": =SUM(A1)', summary)

    def test_no_warning_for_normal_values(self):
        result = self.run_cleaner("id,note\n1,hello\n")
        self.assertEqual(result.formula_warnings, [])
        self.assertNotIn("WARNING", build_summary(result))


class TestSourceFileProtection(CsvTestCase):

    TEXT = "id,name\n 1 ,Ava\n\n1,Ava\n"

    def test_refuses_to_save_over_the_source(self):
        source = self.write_text("source.csv", self.TEXT)
        before = self.read_bytes(source)
        result = clean(load_csv(source), ALL_ON)
        with self.assertRaises(CsvCleanerError):
            save_csv(result, source, source, replace_existing=True)
        self.assertEqual(self.read_bytes(source), before)

    def test_refuses_source_path_spelled_differently(self):
        source = self.write_text("source.csv", self.TEXT)
        before = self.read_bytes(source)
        other_spelling = os.path.join(self.folder, ".", "SOURCE.csv")
        result = clean(load_csv(source), ALL_ON)
        with self.assertRaises(CsvCleanerError):
            save_csv(result, other_spelling, source, replace_existing=True)
        self.assertEqual(self.read_bytes(source), before)

    def test_clean_and_save_leaves_source_unchanged(self):
        source = self.write_text("source.csv", self.TEXT)
        before = self.read_bytes(source)
        save_csv(clean(load_csv(source), ALL_ON), self.path("out.csv"), source)
        self.assertEqual(self.read_bytes(source), before)


class TestSafeSaving(CsvTestCase):

    def setUp(self):
        super().setUp()
        self.source = self.write_text("source.csv", "id,name\n1,Ava\n")
        self.result = clean(load_csv(self.source), ALL_ON)
        self.output = self.path("out.csv")

    def temp_files(self):
        return [name for name in os.listdir(self.folder) if name.endswith(".tmp")]

    def test_existing_output_is_not_replaced_without_permission(self):
        self.write_text("out.csv", "old")
        with self.assertRaises(OutputExistsError):
            save_csv(self.result, self.output, self.source)
        self.assertEqual(self.read_bytes(self.output), b"old")

    def test_existing_output_is_replaced_with_permission(self):
        self.write_text("out.csv", "old")
        save_csv(self.result, self.output, self.source, replace_existing=True)
        self.assertEqual(load_csv(self.output).rows, [["1", "Ava"]])

    def test_no_temporary_file_left_after_success(self):
        save_csv(self.result, self.output, self.source)
        self.assertEqual(sorted(os.listdir(self.folder)), ["out.csv", "source.csv"])

    def test_failed_write_leaves_no_partial_output(self):
        broken_writer = mock.Mock()
        broken_writer.writerows.side_effect = OSError(28, "No space left on device")
        with mock.patch("app.cleaner.csv.writer", return_value=broken_writer):
            with self.assertRaises(CsvCleanerError) as caught:
                save_csv(self.result, self.output, self.source)
        self.assertIn("No output file was created or changed", str(caught.exception))
        self.assertFalse(os.path.exists(self.output))
        self.assertEqual(self.temp_files(), [])

    def test_failed_replace_keeps_existing_output_untouched(self):
        self.write_text("out.csv", "old")
        with mock.patch("app.cleaner.os.replace", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(CsvCleanerError) as caught:
                save_csv(self.result, self.output, self.source, replace_existing=True)
        self.assertIn("close it and try again", str(caught.exception))
        self.assertEqual(self.read_bytes(self.output), b"old")
        self.assertEqual(self.temp_files(), [])

    def test_missing_output_folder_gives_clear_error(self):
        with self.assertRaises(CsvCleanerError):
            save_csv(self.result, self.path(os.path.join("no_such_folder", "out.csv")), self.source)


class TestSampleFiles(CsvTestCase):
    """The files in samples/ behave as the docs describe."""

    def test_messy_customers_sample(self):
        source = os.path.join(SAMPLES, "customers_messy.csv")
        before = self.read_bytes(source)
        result = clean(load_csv(source), ALL_ON)
        save_csv(result, self.path("customers_cleaned.csv"), source)

        self.assertEqual(result.rows_read, 9)
        self.assertEqual(result.cells_trimmed, 3)
        self.assertEqual(result.empty_rows_removed, 2)
        self.assertEqual(result.duplicates_removed, 2)
        self.assertEqual(result.rows_written, 5)
        self.assertEqual(len(result.formula_warnings), 2)
        self.assertEqual([row[0] for row in result.rows],
                         ["00124", "00125", "00126", "00127", "00128"])
        self.assertEqual(self.read_bytes(source), before)

    def test_malformed_samples_are_rejected(self):
        for name in ("malformed_wrong_columns.csv", "malformed_bad_quotes.csv", "empty.csv"):
            with self.subTest(name=name):
                with self.assertRaises(CsvCleanerError):
                    load_csv(os.path.join(SAMPLES, name))

    def test_header_only_sample(self):
        data = load_csv(os.path.join(SAMPLES, "header_only.csv"))
        self.assertEqual(data.rows, [])


if __name__ == "__main__":
    unittest.main()
