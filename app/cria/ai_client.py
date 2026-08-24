"""Gemini client integration for CRIA.

Public API
----------
ask_ai(question, df)          — existing masked Q&A, returns unmasked text
ask_ai_raw(question, df)      — same but returns still-masked text
handle_request(user_input, df)— NEW: smart mode with Gemini function calling
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from app.cria.security import mask, unmask


# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-flash-latest"

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

# Used by ask_ai / ask_ai_raw (plain Q&A, no function calling)
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

# Used by handle_request (function calling / smart mode).
# The masked dataset is injected here so Gemini reasons about masked columns
# and values when deciding which tool to call and what arguments to use.
_SMART_SYSTEM_PROMPT_TEMPLATE = """\
You are a data-assistant for an employee dataset.  The dataset (CSV, with \
anonymised placeholder codes instead of real names/values) is shown below for \
your reference.  You must choose exactly ONE of the three available tools to \
handle the user's request:

  • filter_data   — when the user wants to see rows matching some condition
  • make_chart    — when the user wants a chart/graph/plot/visualisation
  • answer_question — for everything else (questions about the data, general \
advice, or anything that is not clearly a filter or a chart)

PLACEHOLDER CODES: The dataset uses short lowercase codes (e.g. "vrqs") as \
anonymised stand-ins for real names and sensitive values.  Treat them as \
opaque identifiers.  Use the EXACT code from the dataset when specifying \
column values in tool arguments.

Dataset (CSV):
{masked_csv}

Available columns: {column_list}

IMPORTANT: Always call one of the three tools.  Never respond with plain text.\
"""


# ---------------------------------------------------------------------------
# ask_ai / ask_ai_raw  (existing — unchanged)
# ---------------------------------------------------------------------------

def ask_ai(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question and return the unmasked response."""
    return unmask(ask_ai_raw(question, df))


def ask_ai_raw(question: str, df: pd.DataFrame | None = None) -> str:
    """Ask Gemini a masked question and return the raw (still-masked) response."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Set it in your .env file.")

    masked_question = mask(question)

    if df is not None:
        masked_data = mask(df.to_csv(index=False)).strip()
        prompt = (
            f"Here is the dataset (CSV format):\n"
            f"{masked_data}\n\n"
            f"Question: {masked_question}"
        )
    else:
        prompt = masked_question

    _debug_print(prompt)

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


# ---------------------------------------------------------------------------
# handle_request  (new — smart / function-calling mode)
# ---------------------------------------------------------------------------

# Tool declarations sent to Gemini.  Column names and values in arguments
# will use the masked representations because Gemini only ever sees masked data.
_TOOL_DECLARATIONS = [
    {
        "name": "filter_data",
        "description": (
            "Filter the employee dataset to rows that match a condition. "
            "Use this when the user wants to see a subset of the data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": (
                        "The dataset column to filter on. "
                        "Must be one of the available columns."
                    ),
                },
                "operator": {
                    "type": "string",
                    "enum": ["==", "!=", ">", "<", ">=", "<=", "contains"],
                    "description": "Comparison operator.",
                },
                "value": {
                    "type": "string",
                    "description": (
                        "The value to compare against. "
                        "For numeric columns supply a number as a string. "
                        "For text columns use the exact placeholder code or "
                        "value from the dataset."
                    ),
                },
            },
            "required": ["column", "operator", "value"],
        },
    },
    {
        "name": "make_chart",
        "description": (
            "Generate a bar chart or pie chart from the employee dataset. "
            "Use this when the user asks for a chart, graph, or visualisation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "pie"],
                    "description": "Type of chart to generate.",
                },
                "x_column": {
                    "type": "string",
                    "description": (
                        "Bar charts: the column for the X-axis (categories). "
                        "Leave empty for pie charts."
                    ),
                },
                "y_column": {
                    "type": "string",
                    "description": (
                        "Bar charts: the column for the Y-axis (numeric values). "
                        "Leave empty for pie charts."
                    ),
                },
                "label_column": {
                    "type": "string",
                    "description": (
                        "Pie charts: the column for slice labels. "
                        "Leave empty for bar charts."
                    ),
                },
                "value_column": {
                    "type": "string",
                    "description": (
                        "Pie charts: the column for slice sizes (numeric). "
                        "Leave empty for bar charts."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Optional chart title. Leave empty to auto-generate.",
                },
                "filter_text": {
                    "type": "string",
                    "description": (
                        "Optional plain-English filter to apply before charting, "
                        "e.g. 'department is Finance'. Leave empty for no filter."
                    ),
                },
            },
            "required": ["chart_type"],
        },
    },
    {
        "name": "answer_question",
        "description": (
            "Answer a question using the dataset or general knowledge. "
            "Use this for any request that is NOT a filter or a chart — "
            "including questions about specific values, summaries, "
            "general business advice, or anything else."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to answer.",
                },
            },
            "required": ["question"],
        },
    },
]


def handle_request(
    user_input: str,
    df: pd.DataFrame,
    charts_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Smart-mode entry point: Gemini decides which action to take.

    Masks the input and dataset, calls Gemini with function declarations,
    dispatches to the appropriate real Python function, unmasks results,
    and returns a uniform result dict:

        {
            "action":  "filter" | "chart" | "answer",
            "result":  pd.DataFrame | str (chart path) | None,
            "message": str,          # human-readable summary / answer text
            "columns": list[str],    # present for "filter" action
        }

    Args:
        user_input:  The user's natural-language request (plain text).
        df:          The loaded employee DataFrame (real, unmasked values).
        charts_dir:  Directory to save chart PNGs.  Defaults to the cria
                     package directory.  Pass current_app.static_folder /
                     "cria_charts" from Flask routes.

    Raises:
        ValueError:  If GEMINI_API_KEY is missing.
        RuntimeError: If the google-genai package is not installed.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Set it in your .env file.")

    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        raise RuntimeError(
            "The google-genai package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    # ------------------------------------------------------------------
    # 1. Mask the input and build the system prompt with masked dataset.
    # ------------------------------------------------------------------
    masked_input = mask(user_input)
    masked_csv   = mask(df.to_csv(index=False)).strip()
    column_list  = ", ".join(df.columns.tolist())

    system_prompt = _SMART_SYSTEM_PROMPT_TEMPLATE.format(
        masked_csv=masked_csv,
        column_list=column_list,
    )

    _debug_print(masked_input, label="SMART MODE — masked user input")

    # ------------------------------------------------------------------
    # 2. Build Tool config and call Gemini.
    # ------------------------------------------------------------------
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(**decl) for decl in _TOOL_DECLARATIONS
        ]
    )

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=masked_input,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[tool],
                # ANY — model may or may not call a function; we handle both
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY",
                    )
                ),
            ),
        )
    except errors.APIError as exc:
        return _answer_result(f"The AI service could not answer right now: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _answer_result(f"Unexpected error calling Gemini: {exc}")

    # ------------------------------------------------------------------
    # 3. Inspect response — function call or plain text?
    # ------------------------------------------------------------------
    function_call = _extract_function_call(response)

    if function_call is None:
        # Gemini returned plain text (shouldn't happen with mode=ANY, but
        # handle it gracefully by unmasking and returning as an answer).
        raw_text = getattr(response, "text", None) or ""
        return _answer_result(unmask(raw_text) if raw_text else "No response from AI.")

    fn_name = function_call.name
    args    = dict(function_call.args)  # mapping of argument name → value

    _debug_print(
        f"Function call: {fn_name}({args})",
        label="SMART MODE — Gemini chose",
    )

    # ------------------------------------------------------------------
    # 4. Unmask argument values so real Python functions receive real data.
    # ------------------------------------------------------------------
    args = _unmask_args(args)

    # ------------------------------------------------------------------
    # 5. Dispatch to the real function.
    # ------------------------------------------------------------------
    if fn_name == "filter_data":
        return _execute_filter(df, args)

    if fn_name == "make_chart":
        return _execute_chart(df, args, charts_dir)

    if fn_name == "answer_question":
        return _execute_answer(args.get("question", user_input), df)

    # Unknown function name — fall back to plain Q&A
    return _execute_answer(user_input, df)


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------

def _execute_filter(df: pd.DataFrame, args: dict) -> dict:
    """Execute filter_data and return a uniform result dict."""
    from app.cria.filter import filter_data

    column   = args.get("column", "")
    operator = args.get("operator", "==")
    value    = args.get("value", "")

    try:
        result_df = filter_data(df, column=column, operator=operator, value=value)
    except ValueError as exc:
        return _answer_result(
            f"Could not apply that filter: {exc}. "
            f"Available columns: {', '.join(df.columns)}."
        )

    if result_df.empty:
        return {
            "action":  "filter",
            "result":  result_df,
            "columns": list(result_df.columns),
            "message": f"No rows matched: {column} {operator} {value}.",
        }

    return {
        "action":  "filter",
        "result":  result_df,
        "columns": list(result_df.columns),
        "message": (
            f"Found {len(result_df)} row{'s' if len(result_df) != 1 else ''} "
            f"where {column} {operator} {value}."
        ),
    }


def _execute_chart(
    df: pd.DataFrame,
    args: dict,
    charts_dir: str | Path | None,
) -> dict:
    """Execute make_bar_chart or make_pie_chart and return a uniform result dict."""
    from app.cria.filter import filter_data, parse_filter_request
    from app.cria.graph_maker import make_bar_chart, make_pie_chart

    chart_type   = args.get("chart_type", "bar").lower()
    title        = args.get("title") or None
    filter_text  = args.get("filter_text", "").strip()

    # Resolve the save path.
    if charts_dir is not None:
        save_dir  = Path(charts_dir)
    else:
        save_dir  = Path(__file__).parent.parent.parent / "app" / "static" / "cria_charts"
    save_dir.mkdir(parents=True, exist_ok=True)
    filename  = f"chart_{uuid.uuid4().hex}.png"
    save_path = str(save_dir / filename)

    # Apply an optional pre-filter.
    chart_df = df
    if filter_text:
        try:
            parsed   = parse_filter_request(filter_text)
            chart_df = filter_data(chart_df, **parsed)
        except ValueError:
            pass  # ignore bad filter text — chart from full dataset

    if chart_df.empty:
        return _answer_result("No data left after applying the filter — chart not generated.")

    try:
        if chart_type == "bar":
            x_col = args.get("x_column", "")
            y_col = args.get("y_column", "")
            if not x_col or not y_col:
                return _answer_result(
                    "To draw a bar chart I need both an X-axis column and a "
                    f"Y-axis column. Available columns: {', '.join(df.columns)}."
                )
            make_bar_chart(chart_df, x_col, y_col, title=title, save_path=save_path)
        else:
            label_col = args.get("label_column", "")
            value_col = args.get("value_column", "")
            if not label_col or not value_col:
                return _answer_result(
                    "To draw a pie chart I need both a label column and a "
                    f"value column. Available columns: {', '.join(df.columns)}."
                )
            make_pie_chart(chart_df, label_col, value_col, title=title, save_path=save_path)

    except ValueError as exc:
        return _answer_result(f"Could not generate chart: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _answer_result(f"Unexpected error generating chart: {exc}")

    # Return the path relative to static/ so Flask's url_for can serve it.
    # If save_dir is the standard cria_charts folder, derive the relative path;
    # otherwise return the full absolute path (CLI usage).
    try:
        static_root = save_dir.parent
        relative    = Path(save_path).relative_to(static_root)
        chart_path  = str(relative)
    except ValueError:
        chart_path = save_path

    return {
        "action":  "chart",
        "result":  chart_path,
        "message": f"{chart_type.title()} chart generated.",
    }


def _execute_answer(question: str, df: pd.DataFrame) -> dict:
    """Run the existing masked Q&A and return a uniform result dict."""
    try:
        answer = ask_ai(question, df)
    except Exception as exc:  # noqa: BLE001
        answer = f"Could not get an answer: {exc}"
    return _answer_result(answer)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _answer_result(message: str) -> dict:
    """Shorthand for returning a plain-text answer result."""
    return {"action": "answer", "result": None, "message": message}


def _unmask_args(args: dict) -> dict:
    """Unmask any string values in a function-call argument dict.

    Gemini only ever sees masked placeholders, so any string value it
    supplies in a function call may contain a placeholder code that needs
    to be converted back to the real value before passing to Python functions.
    """
    unmasked = {}
    for key, val in args.items():
        if isinstance(val, str):
            unmasked[key] = unmask(val)
        else:
            unmasked[key] = val
    return unmasked


def _extract_function_call(response):
    """Extract the first FunctionCall from a Gemini response, or None.

    Handles the google-genai response structure robustly:
      response.candidates[0].content.parts[N].function_call
    """
    try:
        for candidate in response.candidates:
            for part in candidate.content.parts:
                fc = getattr(part, "function_call", None)
                if fc is not None and getattr(fc, "name", None):
                    return fc
    except (AttributeError, IndexError, TypeError):
        pass
    return None


def _debug_print(text: str, label: str = "CRIA DEBUG") -> None:
    """Print a labelled debug block to stderr (visible in Flask dev console)."""
    sep = "-" * 64
    print(
        f"\n[{label}]\n{sep}\n{text}\n{sep}\n",
        file=sys.stderr,
        flush=True,
    )
