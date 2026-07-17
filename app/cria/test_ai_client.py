"""Tests for CRIA Gemini integration, including dataset-grounded answers."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.cria.ai_client import ask_ai, ask_ai_raw
from app.cria.data_loader import load_csv
from app.cria.security import mask


SAMPLE_PATH = Path(__file__).with_name("sample.csv")


class AskAiDatasetTests(unittest.TestCase):
    """Verify ask_ai uses the dataset and handles typo'd names."""

    @classmethod
    def setUpClass(cls):
        cls.df = load_csv(str(SAMPLE_PATH))

    @patch("google.genai.Client")
    def test_ask_ai_passes_masked_dataset_context(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "The salary is 48000."
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            answer = ask_ai("What is the salary of Nadia?", self.df)

        self.assertIn("48000", answer)
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        prompt = call_kwargs["contents"]
        self.assertIn("Here is the dataset (CSV format):", prompt)
        self.assertIn("52000", prompt)
        self.assertIn("Question:", prompt)

    @patch("google.genai.Client")
    def test_ask_ai_typo_nadai_returns_real_salary(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "The salary is 48000."
        mock_client.models.generate_content.return_value = mock_response

        question = "What is the salary of nadai?"
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            answer = ask_ai(question, self.df)

        self.assertIn("48000", answer)
        masked_question = mask(question)
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        prompt = call_kwargs["contents"]
        self.assertIn(masked_question.split()[-1].rstrip("?"), prompt)

    @patch("google.genai.Client")
    def test_ask_ai_without_df_omits_dataset_block(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "No data available."
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            ask_ai_raw("Hello?", df=None)

        prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
        self.assertNotIn("Here is the dataset", prompt)


if __name__ == "__main__":
    unittest.main()
