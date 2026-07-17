"""Chart generation helpers for CRIA."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pandas.api.types import is_numeric_dtype


def make_bar_chart(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str | None = None,
    save_path: str = "app/cria/output_chart.png",
) -> str:
    """Build a bar chart from df and save it as a PNG file."""
    _validate_columns(df, x_column, y_column)
    _validate_numeric_column(df, y_column, y_column)

    chart_title = title or f"{y_column} by {x_column}"

    fig, ax = plt.subplots()
    ax.bar(df[x_column].astype(str), df[y_column])
    ax.set_xlabel(x_column)
    ax.set_ylabel(y_column)
    ax.set_title(chart_title)
    fig.tight_layout()

    output_path = _save_figure(fig, save_path)
    return str(output_path)


def make_pie_chart(
    df: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str | None = None,
    save_path: str = "app/cria/output_pie.png",
) -> str:
    """Build a pie chart from df and save it as a PNG file."""
    _validate_columns(df, label_column, value_column)
    _validate_numeric_column(df, value_column, value_column)

    chart_title = title or f"{value_column} by {label_column}"

    fig, ax = plt.subplots()
    ax.pie(
        df[value_column],
        labels=df[label_column].astype(str),
        autopct="%1.1f%%",
    )
    ax.set_title(chart_title)
    fig.tight_layout()

    output_path = _save_figure(fig, save_path)
    return str(output_path)


def _validate_columns(df: pd.DataFrame, *columns: str) -> None:
    """Raise if any requested column is missing from df."""
    missing = [column for column in columns if column not in df.columns]
    if not missing:
        return

    available = ", ".join(str(name) for name in df.columns)
    if len(missing) == 1:
        raise ValueError(f"Column '{missing[0]}' not found. Available columns: {available}")

    missing_list = ", ".join(f"'{column}'" for column in missing)
    raise ValueError(f"Columns {missing_list} not found. Available columns: {available}")


def _validate_numeric_column(df: pd.DataFrame, column: str, label: str) -> None:
    """Raise if column is not numeric."""
    if not is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{label}' must be numeric for chart values.")


def _save_figure(fig: plt.Figure, save_path: str) -> Path:
    """Save a figure to disk and close it."""
    output_path = Path(save_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format="png")
    plt.close(fig)
    return output_path
