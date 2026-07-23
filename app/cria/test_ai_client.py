"""Tests for CRIA Gemini integration.

Covers:
  - Salary lookup for all three dataset names (Ahmed, Sarah, Nadia) — the
    regression suite for Bug 1.
  - Prompt structure: dataset block present/absent, Question: separator clean.
  - Typo tolerance: close misspellings are masked to the correct placeholder.
  - General (non-dataset) questions: answered without injecting the dataset.
  - System prompt placement: always passed as system_instruction, never inline.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.cria.ai_client import SYSTEM_PROMPT, ask_ai, ask_ai_raw
from app.cria.data_loader import load_csv
from app.cria.security import SensitiveDataMasker, mask

SAMPLE_PATH = Path(__file__).with_name("sample.csv")
MAP_PATH = Path(__file__).with_name("mask_map.json")


def _make_mock_client(answer_text: str):
    """Return a (mock_cls, mock_instance) pair wired to return answer_text."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = answer_text
    mock_client.models.generate_content.return_value = mock_response
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls, mock_client


def _last_prompt(mock_client) -> str:
    """Extract the 'contents' string from the last generate_content call."""
    return mock_client.models.generate_content.call_args.kwargs["contents"]


def _last_system_instruction(mock_client) -> str:
    """Extract the system_instruction from the last generate_content call."""
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    return config.system_instruction


# ---------------------------------------------------------------------------
# Helper: expected placeholder codes derived from the live mask_map.json so
# tests stay correct even if the codes are ever rotated.
# ---------------------------------------------------------------------------
_masker = SensitiveDataMasker(map_path=MAP_PATH)
CODE = {
    "Ahmed":  _masker.mapping["Ahmed"],
    "Sarah":  _masker.mapping["Sarah"],
    "Nadia":  _masker.mapping["Nadia"],
    "salary": _masker.mapping["salary"],
}


class SalaryRegressionTests(unittest.TestCase):
    """Bug-1 regression: salary lookup must work for ALL three names.

    Previously Ahmed returned "I don't have that information" while Nadia
    worked, because the masked CSV had a trailing \\r\\n that collapsed the
    blank-line separator before "Question:", making Gemini treat the question
    as a 6th data row.
    """

    @classmethod
    def setUpClass(cls):
        cls.df = load_csv(str(SAMPLE_PATH))

    # -- individual salary tests -----------------------------------------

    @patch("google.genai.Client")
    def test_salary_ahmed(self, mock_cls):
        mock_cls, mock_client = _make_mock_client("The salary is 52000.")
        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of Ahmed?", self.df)

        # Unmasked answer must contain the correct salary
        self.assertIn(
            "52000", answer,
            "Ahmed's salary (52000) must appear in the unmasked answer.",
        )

    @patch("google.genai.Client")
    def test_salary_sarah(self, mock_cls):
        mock_cls, mock_client = _make_mock_client("The salary is 61000.")
        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of Sarah?", self.df)

        self.assertIn(
            "61000", answer,
            "Sarah's salary (61000) must appear in the unmasked answer.",
        )

    @patch("google.genai.Client")
    def test_salary_nadia(self, mock_cls):
        mock_cls, mock_client = _make_mock_client("The salary is 48000.")
        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of Nadia?", self.df)

        self.assertIn(
            "48000", answer,
            "Nadia's salary (48000) must appear in the unmasked answer.",
        )

    # -- prompt-structure tests ------------------------------------------

    @patch("google.genai.Client")
    def test_prompt_contains_all_salaries_in_data_block(self, mock_cls):
        """All three salary values must be present in the masked data block."""
        mock_cls, mock_client = _make_mock_client("52000.")
        with patch("google.genai.Client", mock_cls):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("What is the salary of Ahmed?", self.df)

        prompt = _last_prompt(mock_client)
        for salary in ("52000", "61000", "48000"):
            self.assertIn(salary, prompt, f"{salary} must be in the data block.")

    @patch("google.genai.Client")
    def test_prompt_placeholder_consistent_across_data_and_question(self, mock_cls):
        """The same placeholder code must appear in BOTH the data block and
        the question line — for every name in the dataset."""
        cases = [
            ("What is the salary of Ahmed?", "Ahmed"),
            ("What is the salary of Sarah?", "Sarah"),
            ("What is the salary of Nadia?", "Nadia"),
        ]
        for question, name in cases:
            with self.subTest(name=name):
                mock_cls2, mock_client2 = _make_mock_client(f"salary.")
                with patch("google.genai.Client", mock_cls2):
                    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                        ask_ai_raw(question, self.df)

                prompt = _last_prompt(mock_client2)
                code = CODE[name]

                # Data block check
                data_block = prompt.split("Question:")[0]
                self.assertIn(
                    code, data_block,
                    f"Placeholder {code!r} for {name} must be in the data block.",
                )
                # Question line check
                question_part = prompt.split("Question:", 1)[1]
                self.assertIn(
                    code, question_part,
                    f"Placeholder {code!r} for {name} must be in the question line.",
                )

    @patch("google.genai.Client")
    def test_question_separator_is_clean_double_newline(self, mock_cls):
        """'Question:' must be preceded by exactly \\n\\n — not run directly
        into the last CSV row.  This was the root-cause separator bug."""
        mock_cls2, mock_client2 = _make_mock_client("52000.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("What is the salary of Ahmed?", self.df)

        prompt = _last_prompt(mock_client2)
        self.assertIn(
            "\n\nQuestion:",
            prompt,
            "Data block and Question: must be separated by exactly \\n\\n.",
        )
        # Paranoia check: no raw \\r\\n immediately before Question:
        self.assertNotIn(
            "\r\nQuestion:",
            prompt,
            "Trailing \\r\\n must be stripped before the Question: separator.",
        )

    @patch("google.genai.Client")
    def test_prompt_has_dataset_header_line(self, mock_cls):
        """Prompt must start with the dataset header line."""
        mock_cls2, mock_client2 = _make_mock_client("ok.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("What is the salary of Ahmed?", self.df)

        prompt = _last_prompt(mock_client2)
        self.assertTrue(
            prompt.startswith("Here is the dataset (CSV format):"),
            "Prompt must begin with the dataset header line.",
        )


class SystemPromptTests(unittest.TestCase):
    """The system prompt must be passed as system_instruction, never inline."""

    @classmethod
    def setUpClass(cls):
        cls.df = load_csv(str(SAMPLE_PATH))

    @patch("google.genai.Client")
    def test_system_instruction_is_set(self, mock_cls):
        mock_cls2, mock_client2 = _make_mock_client("ok.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("What is the salary of Nadia?", self.df)

        si = _last_system_instruction(mock_client2)
        self.assertEqual(
            si,
            SYSTEM_PROMPT,
            "system_instruction must be the module-level SYSTEM_PROMPT constant.",
        )

    @patch("google.genai.Client")
    def test_system_prompt_not_in_user_contents(self, mock_cls):
        """The system prompt text must NOT be injected into the user-facing
        'contents' string — it belongs in config.system_instruction only."""
        mock_cls2, mock_client2 = _make_mock_client("ok.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("What is the salary of Ahmed?", self.df)

        prompt = _last_prompt(mock_client2)
        # A phrase unique to SYSTEM_PROMPT that would never appear in a salary
        # question or CSV row
        self.assertNotIn(
            "PLACEHOLDER CODES",
            prompt,
            "SYSTEM_PROMPT text must not appear in the user 'contents' string.",
        )


class GeneralQuestionTests(unittest.TestCase):
    """Requirement 2: non-dataset questions must not inject the CSV block."""

    @patch("google.genai.Client")
    def test_general_question_without_df_omits_dataset_block(self, mock_cls):
        mock_cls2, mock_client2 = _make_mock_client(
            "Focus on intrinsic motivation and clear career paths."
        )
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai(
                    "What's the best strategy to increase employee retention?",
                    df=None,
                )

        prompt = _last_prompt(mock_client2)
        self.assertNotIn(
            "Here is the dataset",
            prompt,
            "General question with df=None must not include a dataset block.",
        )
        self.assertNotIn(
            "name,department",
            prompt,
            "CSV header must not appear for a general question.",
        )
        # The answer itself (after unmask, which is a no-op here) should pass
        # through intact
        self.assertIn("motivation", answer)

    @patch("google.genai.Client")
    def test_general_question_prompt_is_just_the_question(self, mock_cls):
        """When df=None the prompt must equal the masked question and nothing
        else — no dataset preamble, no 'Answer based only on this data'."""
        mock_cls2, mock_client2 = _make_mock_client("Here are some tips.")
        question = "How can I improve team productivity?"
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw(question, df=None)

        prompt = _last_prompt(mock_client2)
        expected = mask(question)
        self.assertEqual(
            prompt,
            expected,
            "For df=None the entire prompt must be exactly mask(question).",
        )


class TypoToleranceTests(unittest.TestCase):
    """Typo'd names must be masked to the correct placeholder before sending."""

    @classmethod
    def setUpClass(cls):
        cls.df = load_csv(str(SAMPLE_PATH))

    @patch("google.genai.Client")
    def test_typo_nadai_question_contains_nadia_placeholder(self, mock_cls):
        mock_cls2, mock_client2 = _make_mock_client("The salary is 48000.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of nadai?", self.df)

        self.assertIn("48000", answer)
        prompt = _last_prompt(mock_client2)
        # The typo must be gone; Nadia's placeholder must appear
        self.assertIn(CODE["Nadia"], prompt)
        self.assertNotIn("nadai", prompt.lower())

    @patch("google.genai.Client")
    def test_typo_ahled_question_contains_ahmed_placeholder(self, mock_cls):
        mock_cls2, mock_client2 = _make_mock_client("The salary is 52000.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of Ahled?", self.df)

        self.assertIn("52000", answer)
        prompt = _last_prompt(mock_client2)
        self.assertIn(CODE["Ahmed"], prompt)
        self.assertNotIn("Ahled", prompt)

    @patch("google.genai.Client")
    def test_ask_ai_passes_masked_dataset_context(self, mock_cls):
        """Original smoke test preserved: dataset context is injected and
        all salary values are present in the prompt."""
        mock_cls2, mock_client2 = _make_mock_client("The salary is 48000.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                answer = ask_ai("What is the salary of Nadia?", self.df)

        self.assertIn("48000", answer)
        prompt = _last_prompt(mock_client2)
        self.assertIn("Here is the dataset (CSV format):", prompt)
        self.assertIn("52000", prompt)
        self.assertIn("Question:", prompt)

    @patch("google.genai.Client")
    def test_ask_ai_without_df_omits_dataset_block(self, mock_cls):
        """Original smoke test preserved: no dataset block when df=None."""
        mock_cls2, mock_client2 = _make_mock_client("No data available.")
        with patch("google.genai.Client", mock_cls2):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                ask_ai_raw("Hello?", df=None)

        prompt = _last_prompt(mock_client2)
        self.assertNotIn("Here is the dataset", prompt)


if __name__ == "__main__":
    unittest.main()
