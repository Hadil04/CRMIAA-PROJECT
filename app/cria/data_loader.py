"""Data-loading utilities for CRIA.

Two loaders are provided:

load_csv(path)   — original CSV loader; kept as fallback / test option.
load_from_db()   — primary loader; queries dbo.Employees via the app's DB
                   connection.  Must be called inside a Flask app context.

Both return a DataFrame with lower-case columns ``name``, ``department``,
``salary`` so that filter.py / ai_client.py / graph_maker.py work identically
regardless of which loader was used.
"""

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# CSV loader (unchanged, used as fallback)
# ---------------------------------------------------------------------------

def load_csv(path: str) -> pd.DataFrame:
    """Read a CSV file into a pandas DataFrame.

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
    return df


# ---------------------------------------------------------------------------
# Database loader (primary)
# ---------------------------------------------------------------------------

def load_from_db() -> pd.DataFrame:
    """Query dbo.Employees and return a DataFrame with columns
    ``name``, ``department``, ``salary``.

    Must be called inside a Flask application context because it relies on
    ``current_app.config`` via ``get_connection()``.

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
        import pyodbc
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT Name, Department, Salary FROM dbo.Employees ORDER BY Id"
            )
            rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError(
            f"Database query failed: {exc}"
        ) from exc

    if not rows:
        raise ValueError(
            "The Employees table is empty. "
            "Import data via Reports → Import Employees before using CRIA."
        )

    df = pd.DataFrame(
        [(r[0], r[1], r[2]) for r in rows],
        columns=["name", "department", "salary"],
    )
    return df
