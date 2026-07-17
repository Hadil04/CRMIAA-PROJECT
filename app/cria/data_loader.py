"""CSV loading utilities for CRIA."""

from pathlib import Path

import pandas as pd


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
        return pd.read_csv(csv_path, engine="python", on_bad_lines="error")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"CSV file is empty: {csv_path}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV file is malformed: {csv_path}") from exc

