"""CRIA web routes — Admin dashboard integration."""

import uuid
from pathlib import Path

import pandas as pd
from flask import Blueprint, current_app, flash, render_template, request, session

from app.cria.ai_client import ask_ai
from app.cria.data_loader import load_csv
from app.cria.filter import filter_data, parse_filter_request
from app.cria.graph_maker import make_bar_chart, make_pie_chart
from app.utils.decorators import login_required, role_required


cria_bp = Blueprint("cria", __name__, url_prefix="/admin/cria")

SAMPLE_CSV = Path(__file__).with_name("sample.csv")


def _load_dataset() -> pd.DataFrame:
    """Load the CRIA sample dataset."""
    return load_csv(str(SAMPLE_CSV))


def _render_index(active_tab: str = "ask", **extra):
    """Render the CRIA page with dataset info and optional result context."""
    df = _load_dataset()
    context = {
        "username": session.get("username", "Admin"),
        "row_count": len(df),
        "columns": list(df.columns),
        "active_tab": active_tab,
        **extra,
    }
    return render_template("cria/index.html", **context)


def _charts_dir() -> Path:
    """Return the folder where chart PNGs are saved, creating it if needed."""
    charts_dir = Path(current_app.static_folder) / "cria_charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir


def _apply_optional_filter(df: pd.DataFrame, filter_text: str) -> pd.DataFrame:
    """Apply a natural-language filter when filter_text is provided."""
    if not filter_text or not filter_text.strip():
        return df
    parsed = parse_filter_request(filter_text.strip())
    return filter_data(df, **parsed)


@cria_bp.route("/")
@login_required
@role_required("Admin")
def index():
    """Main CRIA page with dataset info and interactive sections."""
    return _render_index()


@cria_bp.route("/ask", methods=["POST"])
@login_required
@role_required("Admin")
def ask():
    """Handle an AI question about the data."""
    question = request.form.get("question", "").strip()
    if not question:
        flash("Please enter a question.", "warning")
        return _render_index(active_tab="ask")

    try:
        df = _load_dataset()
        answer = ask_ai(question, df)
    except Exception as exc:
        flash(f"Could not get an answer: {exc}", "error")
        return _render_index(active_tab="ask", ask_question=question)

    return _render_index(active_tab="ask", ask_question=question, ask_answer=answer)


@cria_bp.route("/filter", methods=["POST"])
@login_required
@role_required("Admin")
def filter_rows():
    """Handle a natural-language filter request."""
    filter_text = request.form.get("filter_text", "").strip()
    if not filter_text:
        flash("Please enter a filter request.", "warning")
        return _render_index(active_tab="filter")

    try:
        df = _load_dataset()
        parsed = parse_filter_request(filter_text)
        filtered = filter_data(df, **parsed)
    except ValueError as exc:
        flash(f"Could not parse or apply filter: {exc}", "error")
        return _render_index(active_tab="filter", filter_text=filter_text)
    except Exception as exc:
        flash(f"Something went wrong: {exc}", "error")
        return _render_index(active_tab="filter", filter_text=filter_text)

    return _render_index(
        active_tab="filter",
        filter_text=filter_text,
        filter_columns=list(filtered.columns),
        filter_rows=filtered.to_dict(orient="records"),
    )


@cria_bp.route("/graph", methods=["POST"])
@login_required
@role_required("Admin")
def graph():
    """Handle a chart request, optionally applying a filter first."""
    chart_type = request.form.get("chart_type", "").strip().lower()
    title = request.form.get("title", "").strip()
    filter_text = request.form.get("filter_text", "").strip()
    x_column = request.form.get("x_column", "").strip()
    y_column = request.form.get("y_column", "").strip()
    label_column = request.form.get("label_column", "").strip()
    value_column = request.form.get("value_column", "").strip()

    form_context = {
        "chart_type": chart_type,
        "title": title,
        "filter_text": filter_text,
        "x_column": x_column,
        "y_column": y_column,
        "label_column": label_column,
        "value_column": value_column,
    }

    if chart_type not in {"bar", "pie"}:
        flash("Please choose a valid chart type (bar or pie).", "warning")
        return _render_index(active_tab="graph", **form_context)

    try:
        chart_df = _apply_optional_filter(_load_dataset(), filter_text)
        if chart_df.empty:
            flash("No data left after applying the filter.", "warning")
            return _render_index(active_tab="graph", **form_context)

        filename = f"chart_{uuid.uuid4().hex}.png"
        save_path = str(_charts_dir() / filename)

        if chart_type == "bar":
            if not x_column or not y_column:
                flash("Bar charts require both X-axis and Y-axis columns.", "warning")
                return _render_index(active_tab="graph", **form_context)
            make_bar_chart(
                chart_df,
                x_column,
                y_column,
                title=title or None,
                save_path=save_path,
            )
        else:
            if not label_column or not value_column:
                flash("Pie charts require both label and value columns.", "warning")
                return _render_index(active_tab="graph", **form_context)
            make_pie_chart(
                chart_df,
                label_column,
                value_column,
                title=title or None,
                save_path=save_path,
            )
    except ValueError as exc:
        flash(str(exc), "error")
        return _render_index(active_tab="graph", **form_context)
    except Exception as exc:
        flash(f"Could not create chart: {exc}", "error")
        return _render_index(active_tab="graph", **form_context)

    return _render_index(
        active_tab="graph",
        **form_context,
        chart_filename=f"cria_charts/{filename}",
    )
