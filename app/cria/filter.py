"""DataFrame filtering helpers for CRIA."""

import difflib
import re
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype


SUPPORTED_OPERATORS = ("==", "!=", ">", "<", ">=", "<=", "contains")
NUMERIC_OPERATORS = (">", "<", ">=", "<=")
DEFAULT_COLUMNS = ("name", "department", "salary")
FUZZY_MATCH_CUTOFF = 0.75


def filter_data(
    df: pd.DataFrame,
    column: str,
    operator: str,
    value: Any,
) -> pd.DataFrame:
    """Return rows from df that match the requested filter."""
    _validate_column(df, column)
    _validate_operator(operator)

    series = df[column]

    if operator in NUMERIC_OPERATORS:
        _validate_numeric_column(df, column)
        numeric_value = _as_number(value, column)
        mask = _apply_numeric_operator(series, operator, numeric_value)
    elif operator == "contains":
        if is_numeric_dtype(series):
            raise ValueError(f"Column '{column}' is numeric and cannot use 'contains'.")
        corrected_value = _fuzzy_correct_value(series, str(value))
        mask = series.astype(str).str.contains(corrected_value, case=False, na=False)
    elif operator == "==":
        if is_numeric_dtype(series):
            mask = series == _coerce_value_for_series(series, value)
        else:
            corrected_value = _fuzzy_correct_value(series, str(value))
            mask = series.astype(str).str.lower() == corrected_value.lower()
    else:
        if is_numeric_dtype(series):
            mask = series != _coerce_value_for_series(series, value)
        else:
            corrected_value = _fuzzy_correct_value(series, str(value))
            mask = series.astype(str).str.lower() != corrected_value.lower()

    return df.loc[mask].reset_index(drop=True)


def _fuzzy_correct_value(series: pd.Series, value: str) -> str:
    """If value doesn't exactly match any value in series (case-insensitive),
    try to correct it to the closest known value (typo tolerance)."""
    known_values = series.astype(str).unique().tolist()

    # Exact (case-insensitive) match already exists — nothing to correct.
    if any(value.lower() == known.lower() for known in known_values):
        return value

    close = difflib.get_close_matches(
        value.lower(),
        [known.lower() for known in known_values],
        n=1,
        cutoff=FUZZY_MATCH_CUTOFF,
    )
    if not close:
        return value

    corrected = next(known for known in known_values if known.lower() == close[0])
    return corrected


def parse_filter_request(text: str) -> dict:
    """Parse a simple natural-language filter request into filter arguments."""
    if not text or not text.strip():
        raise ValueError("Could not parse filter request. Please rephrase it.")

    request = text.strip()
    lower_request = request.lower()
    column = _detect_column(lower_request)
    operator = _detect_operator(lower_request, column)
    value = _extract_value(request, lower_request, column, operator)

    if column is None or operator is None or value in (None, ""):
        raise ValueError("Could not parse filter request. Please rephrase it.")

    return {"column": column, "operator": operator, "value": value}


def _validate_column(df: pd.DataFrame, column: str) -> None:
    """Raise if column is not available in df."""
    if column not in df.columns:
        available = ", ".join(str(name) for name in df.columns)
        raise ValueError(f"Column '{column}' not found. Available columns: {available}")


def _validate_operator(operator: str) -> None:
    """Raise if operator is unsupported."""
    if operator not in SUPPORTED_OPERATORS:
        valid = ", ".join(SUPPORTED_OPERATORS)
        raise ValueError(f"Unsupported operator '{operator}'. Valid operators: {valid}")


def _validate_numeric_column(df: pd.DataFrame, column: str) -> None:
    """Raise if column is not numeric."""
    if not is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' is not numeric and cannot use numeric filters.")


def _apply_numeric_operator(
    series: pd.Series,
    operator: str,
    value: int | float,
) -> pd.Series:
    """Apply a numeric comparison operator to a series."""
    if operator == ">":
        return series > value
    if operator == "<":
        return series < value
    if operator == ">=":
        return series >= value
    return series <= value


def _as_number(value: Any, column: str) -> int | float:
    """Convert a value to int or float for numeric comparisons."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Value '{value}' is not numeric for column '{column}'.") from exc

    if numeric_value.is_integer():
        return int(numeric_value)
    return numeric_value


def _coerce_value_for_series(series: pd.Series, value: Any) -> Any:
    """Coerce comparison value to numeric when the target series is numeric."""
    if is_numeric_dtype(series):
        return _as_number(value, series.name)
    return value


def _detect_column(lower_request: str) -> str | None:
    """Detect a supported column name in a lowercase request."""
    for column in DEFAULT_COLUMNS:
        if re.search(rf"\b{re.escape(column)}\b", lower_request):
            return column

    if re.search(r"\bpeople\s+in\b", lower_request):
        return "department"

    return None


def _detect_operator(lower_request: str, column: str | None) -> str | None:
    """Detect a filter operator from keywords."""
    operator_keywords = (
        (">=", (r"\bat\s+least\b", r"\bgreater\s+than\s+or\s+equal\s+to\b")),
        ("<=", (r"\bat\s+most\b", r"\bless\s+than\s+or\s+equal\s+to\b")),
        (">", (r"\babove\b", r"\bgreater\s+than\b", r"\bmore\s+than\b")),
        ("<", (r"\bbelow\b", r"\bless\s+than\b", r"\bunder\b")),
        ("!=", (r"\bnot\b", r"\bis\s+not\b", r"\bdoes\s+not\s+equal\b")),
        ("==", (r"\bis\b", r"\bequals\b", r"\bequal\s+to\b")),
        ("contains", (r"\bcontains\b", r"\bin\b")),
    )

    for operator, patterns in operator_keywords:
        if any(re.search(pattern, lower_request) for pattern in patterns):
            return operator

    if column:
        return "contains"

    return None


def _extract_value(
    request: str,
    lower_request: str,
    column: str | None,
    operator: str | None,
) -> str | int | float | None:
    """Extract the filter value from a simple request."""
    if column == "salary" or operator in NUMERIC_OPERATORS:
        number_match = re.search(r"\b\d+(?:\.\d+)?\b", request)
        if number_match:
            return _parse_number(number_match.group(0))
        return None

    quoted_match = re.search(r"['\"]([^'\"]+)['\"]", request)
    if quoted_match:
        return quoted_match.group(1).strip()

    if re.search(r"\bpeople\s+in\b", lower_request):
        match = re.search(r"\bpeople\s+in\s+(.+)$", request, flags=re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))

    if column:
        pattern = rf"\b{re.escape(column)}\b\s+(?:is|equals|equal\s+to|contains|in)?\s*(.+)$"
        match = re.search(pattern, request, flags=re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))

    capitalized = re.findall(r"\b[A-Z][A-Za-z0-9_-]*\b", request)
    ignored = {"Show", "What", "Tell", "People"}
    candidates = [word for word in capitalized if word not in ignored]
    if candidates:
        return candidates[-1]

    return None


def _parse_number(value: str) -> int | float:
    """Parse a numeric text value as int when possible, otherwise float."""
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _clean_value(value: str) -> str:
    """Trim common trailing punctuation and filler from extracted values."""
    return value.strip().strip(".?!,;:")