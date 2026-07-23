"""Gemini client integration for CRIA."""

import os
import sys

import pandas as pd
from dotenv import load_dotenv

from app.cria.security import mask, unmask


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
# Two-mode assistant:
#   • Dataset questions  — answer using ONLY the CSV rows provided.
#   • General questions  — answer normally using built-in knowledge.
#
# Critical masking instruction: the dataset and question share the same set of
# placeholder codes (short lowercase strings such as "vrqs", "bndx").  A code
# that appears in both the "name" column of the dataset AND in the question
# refers to the SAME person / value.  Perform an exact string match between
# the code in the question and the code in the dataset — do NOT try to
# interpret the code as a word or acronym.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a helpful assistant that has access to a small dataset (provided in \
each user message as CSV).

RULES — follow them in order:

1. PLACEHOLDER CODES: The dataset and the question may contain short \
lowercase codes such as "vrqs" or "bndx". These are anonymised stand-ins for \
real names or sensitive values. Do NOT interpret them as words or acronyms — \
treat each code as an opaque identifier. When the question contains a code, \
find the EXACT same code in the dataset (case-sensitive exact match) and use \
the value from the same row to answer.

2. DATASET QUESTIONS: If the question asks about something that is present in \
the dataset (people, departments, salaries, or any column value), answer \
strictly using the dataset rows. Look up the code from the question in the \
"name" column of the dataset, then return the value from the requested column \
on that same row.

3. FUZZY NAMES: If the question contains a slight misspelling of a name or \
code that closely matches an entry in the dataset, assume the user means that \
entry and answer accordingly — do not refuse because of a spelling difference.

4. GENERAL QUESTIONS: If the question is NOT about the dataset (e.g. general \
business advice, strategy, productivity tips, unrelated topics), answer \
normally and helpfully using your own knowledge. Do not mention the dataset.

5. TRULY MISSING DATA: Only say "I don't have that information" if the \
question is clearly about the dataset AND the specific value being asked for \
genuinely does not appear anywhere in the provided rows.\
"""

MODEL_NAME = "gemini-flash-latest"


def ask_ai(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question, optionally with dataset context, and
    return the unmasked response."""
    raw_answer = ask_ai_raw(question, df)
    return unmask(raw_answer)


def ask_ai_raw(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question and return the raw (still-masked) response.

    A debug summary of the exact prompt is printed to stderr so it is visible
    in the Flask development console without polluting normal stdout output.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Set GEMINI_API_KEY in your .env file."
        )

    masked_question = mask(question)

    if df is not None:
        # Mask every value in the CSV so no sensitive data leaves the machine.
        masked_data = mask(df.to_csv(index=False))

        # Strip any trailing whitespace/newlines from the CSV block so the
        # "Question:" line is always cleanly separated by exactly two newlines.
        masked_data = masked_data.strip()

        prompt = (
            f"Here is the dataset (CSV format):\n"
            f"{masked_data}\n\n"
            f"Question: {masked_question}"
        )
    else:
        prompt = masked_question

    # ------------------------------------------------------------------
    # DEBUG: print the exact prompt to stderr so it is visible in the
    # Flask development console.  Remove or gate on an env-var once the
    # inconsistency is confirmed fixed.
    # ------------------------------------------------------------------
    _debug_separator = "-" * 64
    print(
        f"\n[CRIA DEBUG] Prompt sent to Gemini:\n"
        f"{_debug_separator}\n"
        f"{prompt}\n"
        f"{_debug_separator}\n",
        file=sys.stderr,
        flush=True,
    )

    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        raise RuntimeError(
            "The google-genai package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
    except errors.APIError as exc:
        return f"Sorry, the AI service could not answer right now: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"Sorry, the AI service could not answer right now: {exc}"

    return response.text or ""
