"""Tests for CRIA DataFrame filtering, including typo tolerance."""

import unittest
from pathlib import Path

from app.cria.data_loader import load_csv
from app.cria.filter import filter_data, parse_filter_request


SAMPLE_PATH = Path(__file__).with_name("sample.csv")


class FilterTypoTests(unittest.TestCase):
    """Verify fuzzy correction against real column values."""

    @classmethod
    def setUpClass(cls):
        cls.df = load_csv(str(SAMPLE_PATH))

    def test_finace_department_returns_finance_rows(self):
        parsed = parse_filter_request("show me people in finace")
        result = filter_data(self.df, **parsed)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["name"], "Sarah")
        self.assertEqual(result.iloc[0]["department"], "Finance")

    def test_department_is_nadai_does_not_match_name_column(self):
        parsed = parse_filter_request("department is nadai")
        result = filter_data(self.df, **parsed)

        self.assertTrue(result.empty)

    def test_direct_fuzzy_department_filter(self):
        result = filter_data(self.df, "department", "==", "finace")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["department"], "Finance")

    def test_salary_filter_unchanged(self):
        parsed = parse_filter_request("salary above 50000")
        result = filter_data(self.df, **parsed)

        self.assertEqual(len(result), 2)
        names = set(result["name"].tolist())
        self.assertEqual(names, {"Ahmed", "Sarah"})


if __name__ == "__main__":
    unittest.main()
