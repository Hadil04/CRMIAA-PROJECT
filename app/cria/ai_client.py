"""Gemini client integration for CRIA."""

import os

import pandas as pd
from dotenv import load_dotenv

from app.cria.security import mask, unmask


SYSTEM_PROMPT = (
    "You are a helpful data assistant. You will be given a dataset and a "
    "question. Answer the question using ONLY the dataset provided below, "
    "clearly and concisely. The dataset and the question may contain "
    "placeholder codes (short lowercase strings like 'vrqs'). Treat each one "
    "as a person's name or sensitive value that has been hidden from you. Do "
    "not try to interpret or expand it as an acronym or real word — just use "
    "it as-is, as if it were a name you do not need to define. If the user's "
    "question contains a slight misspelling of a name or value that closely "
    "matches an entry in the dataset, assume they mean that entry and answer "
    "using it — do not refuse just because of a spelling difference. If the "
    "answer is not in the dataset, say you don't have that information."
)
MODEL_NAME = "gemini-2.5-flash"


def ask_ai(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question, optionally with dataset context, and
    return the unmasked response."""
    raw_answer = ask_ai_raw(question, df)
    return unmask(raw_answer)


def ask_ai_raw(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question and return the raw masked response."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Set GEMINI_API_KEY in your .env file.")

    masked_question = mask(question)

    if df is not None:
        # Mask the data too, so no sensitive value leaves the machine.
        masked_data = mask(df.to_csv(index=False))
        prompt = (
            f"Here is the dataset (CSV format):\n{masked_data}\n\n"
            f"Question: {masked_question}\n\n"
            "Answer based only on this data."
        )
    else:
        prompt = masked_question

    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        raise RuntimeError(
            "The google-genai package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
    except errors.APIError as exc:
        return f"Sorry, the AI service could not answer right now: {exc}"
    except Exception as exc:
        return f"Sorry, the AI service could not answer right now: {exc}"

    return response.text or ""