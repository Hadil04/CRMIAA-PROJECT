"""Data-loading utilities for CRIA.

Two loaders are provided:

load_csv(path)   — original CSV loader; kept as fallback / test option.
load_from_db()   — primary loader; queries dbo.Employees via the app's DB
                   connection.  Must be called inside a Flask app context.

Both return a DataFrame with lower-case columns ``name``, ``department``,
``salary`` where:

  * ``name`` and ``department`` are str (object) dtype
  * ``salary`` is **int64** (or float64 when any value couldn't be coerced)

The explicit numeric cast is applied at the loading stage so that every
downstream consumer — filter.py, graph_maker.py, ai_client.py — always
receives a properly-typed DataFrame regardless of which loader was used.

Root cause of the original bug
-------------------------------
pyodbc returns SQL Server INT / DECIMAL columns as Python ``Decimal`` objects.
pandas infers a column of ``Decimal`` values as ``object`` dtype, which makes
``pandas.api.types.is_numeric_dtype()`` return False, causing graph_maker.py
to raise "Column 'salary' must be numeric".

Fix: after building the DataFrame, call ``pd.to_numeric(..., errors='coerce')``
on known numeric columns and warn on any rows where conversion produced NaN.
"""

import sys
import warnings
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _coerce_numeric_columns(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    """Cast each listed column to numeric, warn about rows that fail.

    Uses ``errors='coerce'`` so bad values become NaN rather than crashing.
    After coercion, attempts to downcast float64 → int64 when all non-NaN
    values are whole numbers (e.g. salary of 55000.0 → 55000).

    Args:
        df: DataFrame to modify (a copy is returned — original is untouched).
        numeric_cols: Column names to coerce.  Columns not present in df are
                      silently skipped.

    Returns:
        A new DataFrame with the requested columns cast to numeric.
    """
    df = df.copy()

    for col in numeric_cols:
        if col not in df.columns:
            continue

        original = df[col].copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")

        # Identify rows where coercion produced NaN but the original wasn't NaN
        bad_mask = df[col].isna() & original.notna()
        bad_count = bad_mask.sum()
        if bad_count:
            bad_indices = df.index[bad_mask].tolist()
            # Use print to stderr (visible in Flask dev console) + warnings
            msg = (
                f"[CRIA data_loader] WARNING: {bad_count} row(s) in column "
                f"'{col}' could not be converted to numeric and were set to "
                f"NaN. Row indices: {bad_indices}. "
                f"Original values: {original[bad_mask].tolist()}"
            )
            print(msg, file=sys.stderr, flush=True)
            warnings.warn(msg, stacklevel=3)

        # Downcast float64 → Int64 (nullable integer) when all non-NaN values
        # are whole numbers, preserving clean integer display.
        if df[col].dtype == float:
            non_null = df[col].dropna()
            if len(non_null) > 0 and (non_null % 1 == 0).all():
                df[col] = df[col].astype("Int64")  # pandas nullable integer

    return df


# ---------------------------------------------------------------------------
# CSV loader (unchanged interface, now applies numeric coercion)
# ---------------------------------------------------------------------------

def load_csv(path: str) -> pd.DataFrame:
    """Read a CSV file into a pandas DataFrame.

    Column names are lowercased.  The ``salary`` column is explicitly cast to
    a numeric dtype so downstream consumers always receive a typed column.

    Raises:
        FileNotFoundError: If the CSV path does not exist.
        ValueError: If the CSV is empty or cannot be parsed.
    """
    csv_path = Path(path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path, engine="python", on_bad_lines="error")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"CSV file is empty: {csv_path}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV file is malformed: {csv_path}") from exc

    # Normalise column names to lower-case so both loaders produce the same
    # column names regardless of the CSV header casing.
    df.columns = [str(c).lower() for c in df.columns]

    # Explicitly cast numeric columns — guards against mixed-type CSV rows.
    df = _coerce_numeric_columns(df, ["salary"])

    return df


# ---------------------------------------------------------------------------
# Database loader (primary)
# ---------------------------------------------------------------------------

def load_from_db() -> pd.DataFrame:
    """Query dbo.Employees and return a DataFrame with columns
    ``name``, ``department``, ``salary``.

    Must be called inside a Flask application context because it relies on
    ``current_app.config`` via ``get_connection()``.

    The ``salary`` column is explicitly cast to int64/float64 here because
    pyodbc returns SQL Server INT/DECIMAL values as Python ``Decimal`` objects,
    which pandas infers as ``object`` dtype — causing is_numeric_dtype() to
    return False and breaking chart generation and numeric filters.

    Raises:
        RuntimeError: If the database connection fails.
        ValueError:   If the Employees table exists but contains no rows.
    """
    # Import here (not at module top) so this module can be imported in tests
    # or CLI contexts that have no Flask app without triggering an error.
    try:
        from app.db import get_connection
    except Exception as exc:
        raise RuntimeError(
            "Could not import get_connection — ensure this is called inside a "
            "Flask app context."
        ) from exc

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT Name, Department, Salary FROM dbo.Employees ORDER BY Id"
            )
            rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError(f"Database query failed: {exc}") from exc

    if not rows:
        raise ValueError(
            "The Employees table is empty. "
            "Import data via Reports → Import Employees before using CRIA."
        )

    # Build the DataFrame from cursor rows.
    # pyodbc maps SQL Server INT → Python int OR Decimal depending on the
    # driver version and column type.  We convert explicitly below.
    df = pd.DataFrame(
        # Use float() for salary to safely handle both int and Decimal
        [(str(r[0]), str(r[1]), r[2]) for r in rows],
        columns=["name", "department", "salary"],
    )

    # Cast salary to numeric — this is the critical fix.
    # Decimal('55000') → 55000 (int64); any unconvertible value → NaN + warning.
    df = _coerce_numeric_columns(df, ["salary"])

    return df
