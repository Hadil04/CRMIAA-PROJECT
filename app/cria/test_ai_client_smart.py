"""Unit tests for handle_request() — Gemini function-calling smart mode.

All tests mock the Gemini client so no real API calls are made.
The four required test cases from the specification are included:

  1. "What is the salary of Karim?"       → answer_question
  2. "Show me people in IT department"    → filter_data
  3. "Draw a bar chart of salary by dept" → make_chart
  4. "What's a good strategy to reduce costs?" → answer_question (general)

Additional tests cover:
  - Argument unmasking (_unmask_args)
  - Graceful fallback when Gemini returns invalid column in filter_data
  - Graceful fallback when Gemini returns invalid column in make_chart
  - Plain-text response (no function call) handled as answer
  - _extract_function_call returns None when response has no function_call parts
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

# ---------------------------------------------------------------------------
# Helpers — build fake Gemini response objects
# ---------------------------------------------------------------------------

def _fc_response(fn_name: str, args: dict):
    """Build a fake Gemini response that contains a single function call."""
    fc = SimpleNamespace(name=fn_name, args=args)
    part = SimpleNamespace(function_call=fc)
    content = SimpleNamespace(parts=[part])
    candidate = SimpleNamespace(content=content)
    response = MagicMock()
    response.candidates = [candidate]
    response.text = None
    return response


def _text_response(text: str):
    """Build a fake Gemini response with plain text and no function call."""
    part = SimpleNamespace(function_call=None)
    content = SimpleNamespace(parts=[part])
    candidate = SimpleNamespace(content=content)
    response = MagicMock()
    response.candidates = [candidate]
    response.text = text
    return response


# ---------------------------------------------------------------------------
# Sample dataset — matches the DB/CSV shape
# ---------------------------------------------------------------------------

SAMPLE_DF = pd.DataFrame({
    "name":       ["Karim",  "Yasmine",   "Mohamed", "Amina"],
    "department": ["IT",     "Marketing", "Sales",   "HR"],
    "salary":     [55000,    47000,       60000,     45000],
})

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class HandleRequestRouting(unittest.TestCase):
    """Gemini function-call routing → correct action in result dict."""

    def _call(self, fn_name, args, user_input="test"):
        """Patch the Gemini client to return fn_name(args) and call handle_request."""
        fake_response = _fc_response(fn_name, args)
        mock_client   = MagicMock()
        mock_client.models.generate_content.return_value = fake_response
        mock_cls = MagicMock(return_value=mock_client)

        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                from app.cria.ai_client import handle_request
                return handle_request(user_input, SAMPLE_DF, charts_dir=None)

    # ---- Spec test 1: salary question → answer_question ------------------
    def test_salary_question_routes_to_answer(self):
        """'What is the salary of Karim?' → Gemini calls answer_question."""
        # Simulate Gemini deciding to call answer_question
        with patch("app.cria.ai_client._execute_answer") as mock_exec:
            mock_exec.return_value = {
                "action": "answer", "result": None,
                "message": "Karim's salary is 55000."
            }
            result = self._call(
                "answer_question",
                {"question": "What is the salary of Karim?"},
                user_input="What is the salary of Karim?",
            )
        self.assertEqual(result["action"], "answer")
        mock_exec.assert_called_once()

    # ---- Spec test 2: filter request → filter_data -----------------------
    def test_filter_routes_to_filter_data(self):
        """'Show me people in IT department' → Gemini calls filter_data."""
        result = self._call(
            "filter_data",
            {"column": "department", "operator": "==", "value": "IT"},
            user_input="Show me people in IT department",
        )
        self.assertEqual(result["action"], "filter")
        self.assertIsNotNone(result["result"])
        # Karim is in IT — should appear in results
        self.assertEqual(len(result["result"]), 1)
        self.assertEqual(result["result"].iloc[0]["name"], "Karim")

    # ---- Spec test 3: bar chart → make_chart -----------------------------
    def test_chart_routes_to_make_chart(self):
        """'Draw a bar chart of salary by department' → Gemini calls make_chart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._call(
                "make_chart",
                {
                    "chart_type":   "bar",
                    "x_column":     "department",
                    "y_column":     "salary",
                    "title":        "Salary by Department",
                    "filter_text":  "",
                },
                user_input="Draw a bar chart of salary by department",
            )
        self.assertEqual(result["action"], "chart")
        self.assertIsNotNone(result["result"])

    # ---- Spec test 4: general question → answer_question -----------------
    def test_general_question_routes_to_answer(self):
        """'What's a good strategy to reduce costs?' → answer_question."""
        with patch("app.cria.ai_client._execute_answer") as mock_exec:
            mock_exec.return_value = {
                "action": "answer", "result": None,
                "message": "Focus on operational efficiency…"
            }
            result = self._call(
                "answer_question",
                {"question": "What's a good strategy to reduce costs?"},
                user_input="What's a good strategy to reduce costs?",
            )
        self.assertEqual(result["action"], "answer")
        mock_exec.assert_called_once()


class HandleRequestEdgeCases(unittest.TestCase):
    """Error handling and edge-case behaviour."""

    def _call_with_response(self, fake_response, user_input="test"):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = fake_response
        mock_cls = MagicMock(return_value=mock_client)
        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                from app.cria.ai_client import handle_request
                return handle_request(user_input, SAMPLE_DF, charts_dir=None)

    def test_plain_text_response_returns_answer(self):
        """If Gemini returns plain text (no function call), wrap as answer."""
        response = _text_response("Here is some plain text.")
        result   = self._call_with_response(response)
        self.assertEqual(result["action"], "answer")
        self.assertIn("plain text", result["message"])

    def test_invalid_column_in_filter_returns_answer(self):
        """filter_data with a non-existent column → graceful answer fallback."""
        response = _fc_response(
            "filter_data",
            {"column": "nonexistent_column", "operator": "==", "value": "X"},
        )
        result = self._call_with_response(response)
        self.assertEqual(result["action"], "answer")
        self.assertIn("filter", result["message"].lower())

    def test_invalid_column_in_chart_returns_answer(self):
        """make_chart with a non-existent column → graceful answer fallback."""
        response = _fc_response(
            "make_chart",
            {
                "chart_type": "bar",
                "x_column":   "nonexistent",
                "y_column":   "salary",
            },
        )
        result = self._call_with_response(response)
        self.assertEqual(result["action"], "answer")
        self.assertIn("chart", result["message"].lower())

    def test_missing_chart_columns_returns_answer(self):
        """make_chart bar without x_column/y_column → helpful answer."""
        response = _fc_response(
            "make_chart",
            {"chart_type": "bar"},   # x_column and y_column absent
        )
        result = self._call_with_response(response)
        self.assertEqual(result["action"], "answer")

    def test_unknown_function_name_falls_back_to_answer(self):
        """An unknown function name Gemini returns → falls back to answer."""
        response = _fc_response("totally_unknown_tool", {"q": "hello"})
        with patch("app.cria.ai_client._execute_answer") as mock_exec:
            mock_exec.return_value = {
                "action": "answer", "result": None, "message": "fallback"
            }
            result = self._call_with_response(response)
        self.assertEqual(result["action"], "answer")


class UnmaskArgsTests(unittest.TestCase):
    """_unmask_args converts masked string values back to real values."""

    def test_string_values_are_unmasked(self):
        from app.cria.ai_client import _unmask_args
        from app.cria.security import SensitiveDataMasker
        from pathlib import Path

        masker = SensitiveDataMasker(
            map_path=Path(__file__).with_name("mask_map.json")
        )
        # Mask "Ahmed" to get its code, then verify _unmask_args reverses it
        code = masker.mapping.get("Ahmed")
        if code is None:
            self.skipTest("Ahmed not in mask_map.json — skipping")

        args = {"column": "name", "operator": "==", "value": code}
        result = _unmask_args(args)
        self.assertEqual(result["value"], "Ahmed")
        # Non-string values pass through unchanged
        self.assertEqual(result["column"], "name")
        self.assertEqual(result["operator"], "==")

    def test_numeric_values_pass_through_unchanged(self):
        from app.cria.ai_client import _unmask_args
        args = {"value": 50000, "threshold": 1.5, "flag": True}
        result = _unmask_args(args)
        self.assertEqual(result["value"],     50000)
        self.assertEqual(result["threshold"], 1.5)
        self.assertEqual(result["flag"],      True)

    def test_empty_args_returns_empty(self):
        from app.cria.ai_client import _unmask_args
        self.assertEqual(_unmask_args({}), {})


class ExtractFunctionCallTests(unittest.TestCase):
    """_extract_function_call handles various response shapes."""

    def test_returns_function_call_when_present(self):
        from app.cria.ai_client import _extract_function_call
        response = _fc_response("filter_data", {"column": "name"})
        fc = _extract_function_call(response)
        self.assertIsNotNone(fc)
        self.assertEqual(fc.name, "filter_data")

    def test_returns_none_when_no_function_call(self):
        from app.cria.ai_client import _extract_function_call
        response = _text_response("hello")
        fc = _extract_function_call(response)
        self.assertIsNone(fc)

    def test_returns_none_on_malformed_response(self):
        from app.cria.ai_client import _extract_function_call
        bad = MagicMock()
        bad.candidates = []     # empty candidates
        fc = _extract_function_call(bad)
        self.assertIsNone(fc)


class FilterExecutionTests(unittest.TestCase):
    """_execute_filter runs real filter_data on the sample DataFrame."""

    def test_filter_it_department_returns_karim(self):
        from app.cria.ai_client import _execute_filter
        result = _execute_filter(
            SAMPLE_DF,
            {"column": "department", "operator": "==", "value": "IT"},
        )
        self.assertEqual(result["action"], "filter")
        self.assertEqual(len(result["result"]), 1)
        self.assertEqual(result["result"].iloc[0]["name"], "Karim")

    def test_filter_salary_above_50000(self):
        from app.cria.ai_client import _execute_filter
        result = _execute_filter(
            SAMPLE_DF,
            {"column": "salary", "operator": ">", "value": "50000"},
        )
        self.assertEqual(result["action"], "filter")
        names = set(result["result"]["name"].tolist())
        self.assertIn("Karim",   names)
        self.assertIn("Mohamed", names)
        self.assertNotIn("Yasmine", names)
        self.assertNotIn("Amina",   names)

    def test_filter_bad_column_returns_answer(self):
        from app.cria.ai_client import _execute_filter
        result = _execute_filter(
            SAMPLE_DF,
            {"column": "no_such_col", "operator": "==", "value": "X"},
        )
        self.assertEqual(result["action"], "answer")
        self.assertIn("filter", result["message"].lower())

    def test_empty_result_still_returns_filter_action(self):
        from app.cria.ai_client import _execute_filter
        result = _execute_filter(
            SAMPLE_DF,
            {"column": "department", "operator": "==", "value": "Nonexistent"},
        )
        self.assertEqual(result["action"], "filter")
        self.assertTrue(result["result"].empty)


class ChartExecutionTests(unittest.TestCase):
    """_execute_chart runs real make_bar/pie_chart on the sample DataFrame."""

    def test_bar_chart_creates_png(self):
        from app.cria.ai_client import _execute_chart
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _execute_chart(
                SAMPLE_DF,
                {
                    "chart_type": "bar",
                    "x_column":   "department",
                    "y_column":   "salary",
                    "title":      "Test",
                },
                charts_dir=tmpdir,
            )
        self.assertEqual(result["action"], "chart")
        self.assertIsNotNone(result["result"])

    def test_pie_chart_creates_png(self):
        from app.cria.ai_client import _execute_chart
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _execute_chart(
                SAMPLE_DF,
                {
                    "chart_type":   "pie",
                    "label_column": "department",
                    "value_column": "salary",
                },
                charts_dir=tmpdir,
            )
        self.assertEqual(result["action"], "chart")

    def test_bar_missing_columns_returns_answer(self):
        from app.cria.ai_client import _execute_chart
        result = _execute_chart(
            SAMPLE_DF,
            {"chart_type": "bar"},   # no x_column / y_column
            charts_dir=None,
        )
        self.assertEqual(result["action"], "answer")

    def test_invalid_y_column_returns_answer(self):
        from app.cria.ai_client import _execute_chart
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _execute_chart(
                SAMPLE_DF,
                {
                    "chart_type": "bar",
                    "x_column":   "department",
                    "y_column":   "does_not_exist",
                },
                charts_dir=tmpdir,
            )
        self.assertEqual(result["action"], "answer")


if __name__ == "__main__":
    unittest.main()
