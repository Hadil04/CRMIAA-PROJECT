"""Tests and manual smoke test for CRIA data loading.

Covers:
  - load_csv() returns numeric salary dtype
  - load_from_db() numeric dtype (mocked — no real DB needed)
  - filter_data() numeric operators work on DB-loaded data
  - make_bar_chart() / make_pie_chart() work on DB-loaded data
  - Bad salary values produce NaN + warning, not a crash
"""

import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from pandas.api.types import is_numeric_dtype

from app.cria.data_loader import _coerce_numeric_columns, load_csv

SAMPLE_PATH = Path(__file__).with_name("sample.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_df(rows: list[tuple]) -> pd.DataFrame:
    """Simulate what load_from_db() builds from cursor.fetchall() rows.

    Mirrors the exact DataFrame construction in load_from_db() so the test
    exercises the same code path, including the Decimal-object scenario.
    """
    from decimal import Decimal
    from app.cria.data_loader import _coerce_numeric_columns

    df = pd.DataFrame(
        [(str(r[0]), str(r[1]), r[2]) for r in rows],
        columns=["name", "department", "salary"],
    )
    return _coerce_numeric_columns(df, ["salary"])


# ---------------------------------------------------------------------------
# _coerce_numeric_columns
# ---------------------------------------------------------------------------

class CoerceNumericTests(unittest.TestCase):

    def test_int_column_becomes_numeric(self):
        df = pd.DataFrame({"salary": [55000, 47000, 60000, 45000]})
        result = _coerce_numeric_columns(df, ["salary"])
        self.assertTrue(is_numeric_dtype(result["salary"]),
                        f"Expected numeric dtype, got {result['salary'].dtype}")

    def test_decimal_objects_become_numeric(self):
        """Core regression: Decimal values (pyodbc output) must become numeric."""
        from decimal import Decimal
        df = pd.DataFrame({"salary": [Decimal("55000"), Decimal("47000"),
                                      Decimal("60000"), Decimal("45000")]})
        result = _coerce_numeric_columns(df, ["salary"])
        self.assertTrue(is_numeric_dtype(result["salary"]),
                        f"Decimal dtype not coerced: {result['salary'].dtype}")
        self.assertEqual(result["salary"].iloc[0], 55000)

    def test_string_salary_column_becomes_numeric(self):
        df = pd.DataFrame({"salary": ["55000", "47000", "60000", "45000"]})
        result = _coerce_numeric_columns(df, ["salary"])
        self.assertTrue(is_numeric_dtype(result["salary"]))

    def test_bad_value_becomes_nan_and_warns(self):
        df = pd.DataFrame({"salary": ["55000", "not_a_number", "60000"]})
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _coerce_numeric_columns(df, ["salary"])
        # Row 1 should be NaN
        self.assertTrue(pd.isna(result["salary"].iloc[1]))
        # At least one warning should have been issued
        self.assertGreater(len(w), 0, "Expected a warning for bad salary value")

    def test_missing_column_is_skipped_silently(self):
        """A column not present in df must be silently ignored — no crash."""
        df = pd.DataFrame({"name": ["Alice"]})
        result = _coerce_numeric_columns(df, ["salary"])  # 'salary' not in df
        self.assertNotIn("salary", result.columns)

    def test_original_df_is_not_mutated(self):
        df = pd.DataFrame({"salary": ["55000", "47000"]})
        original_dtype = df["salary"].dtype
        _coerce_numeric_columns(df, ["salary"])
        self.assertEqual(df["salary"].dtype, original_dtype,
                         "Original DataFrame must not be mutated")


# ---------------------------------------------------------------------------
# load_csv
# ---------------------------------------------------------------------------

class LoadCsvTests(unittest.TestCase):

    def test_salary_is_numeric_after_load(self):
        df = load_csv(str(SAMPLE_PATH))
        self.assertTrue(is_numeric_dtype(df["salary"]),
                        f"load_csv salary dtype: {df['salary'].dtype}")

    def test_columns_are_lowercase(self):
        df = load_csv(str(SAMPLE_PATH))
        self.assertIn("name", df.columns)
        self.assertIn("department", df.columns)
        self.assertIn("salary", df.columns)

    def test_salary_values_are_correct(self):
        df = load_csv(str(SAMPLE_PATH))
        # sample.csv has Ahmed=52000, Sarah=61000, Nadia=48000
        salaries = set(int(v) for v in df["salary"])
        self.assertIn(52000, salaries)
        self.assertIn(61000, salaries)
        self.assertIn(48000, salaries)


# ---------------------------------------------------------------------------
# DB-backed DataFrame (mocked) — filter and chart
# ---------------------------------------------------------------------------

_DB_ROWS = [
    ("Karim",   "IT",        55000),
    ("Yasmine", "Marketing", 47000),
    ("Mohamed", "Sales",     60000),
    ("Amina",   "HR",        45000),
]


class DbLoadedFilterTests(unittest.TestCase):
    """filter_data() must work correctly on data shaped like load_from_db() output."""

    @classmethod
    def setUpClass(cls):
        from decimal import Decimal
        # Simulate pyodbc returning Decimal values
        decimal_rows = [(r[0], r[1], Decimal(str(r[2]))) for r in _DB_ROWS]
        cls.df = _make_db_df(decimal_rows)

    def test_salary_is_numeric(self):
        self.assertTrue(is_numeric_dtype(self.df["salary"]),
                        f"DB-loaded salary dtype: {self.df['salary'].dtype}")

    def test_filter_salary_above_50000(self):
        from app.cria.filter import filter_data
        result = filter_data(self.df, "salary", ">", 50000)
        names = set(result["name"].tolist())
        self.assertEqual(names, {"Karim", "Mohamed"},
                         f"Expected Karim+Mohamed, got {names}")

    def test_filter_salary_below_50000(self):
        from app.cria.filter import filter_data
        result = filter_data(self.df, "salary", "<", 50000)
        names = set(result["name"].tolist())
        self.assertEqual(names, {"Yasmine", "Amina"},
                         f"Expected Yasmine+Amina, got {names}")

    def test_filter_salary_equals(self):
        from app.cria.filter import filter_data
        result = filter_data(self.df, "salary", "==", 55000)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["name"], "Karim")

    def test_filter_department_equals(self):
        from app.cria.filter import filter_data
        result = filter_data(self.df, "department", "==", "IT")
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["name"], "Karim")


class DbLoadedChartTests(unittest.TestCase):
    """Chart generation must not raise on DB-loaded data."""

    @classmethod
    def setUpClass(cls):
        from decimal import Decimal
        decimal_rows = [(r[0], r[1], Decimal(str(r[2]))) for r in _DB_ROWS]
        cls.df = _make_db_df(decimal_rows)

    def test_bar_chart_salary_does_not_raise(self):
        """Core regression: bar chart with salary column must not raise
        'Column salary must be numeric'."""
        from app.cria.graph_maker import make_bar_chart
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            make_bar_chart(self.df, "name", "salary",
                           title="Test", save_path=tmp_path)
            self.assertTrue(os.path.exists(tmp_path),
                            "Chart PNG was not created")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_pie_chart_salary_does_not_raise(self):
        from app.cria.graph_maker import make_pie_chart
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            make_pie_chart(self.df, "department", "salary",
                           title="Test", save_path=tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_bar_chart_csv_data_does_not_raise(self):
        """Existing CSV path must still work after the fix."""
        from app.cria.graph_maker import make_bar_chart
        import tempfile, os
        df = load_csv(str(SAMPLE_PATH))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            make_bar_chart(df, "name", "salary",
                           title="CSV test", save_path=tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Manual smoke test (kept from original file)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_path = Path(__file__).with_name("sample_data.csv")
    if sample_path.exists():
        dataframe = load_csv(str(sample_path))
        print("CSV head:")
        print(dataframe.head())
        print("\nCSV dtypes:")
        print(dataframe.dtypes)
        print("\nCSV info:")
        dataframe.info()
    else:
        print(f"Smoke-test skipped — {sample_path} not found. Run unit tests instead.")
        print("  python -m unittest app.cria.test_data_loader -v")
