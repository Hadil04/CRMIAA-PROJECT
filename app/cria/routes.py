"""CRIA web routes — Admin dashboard integration."""

import sys
import uuid
from pathlib import Path

import pandas as pd
from flask import Blueprint, current_app, flash, render_template, request, session

from app.cria.ai_client import ask_ai, handle_request
from app.cria.data_loader import load_csv, load_from_db
from app.cria.filter import filter_data, parse_filter_request
from app.cria.graph_maker import make_bar_chart, make_pie_chart
from app.utils.decorators import login_required, role_required


cria_bp = Blueprint("cria", __name__, url_prefix="/admin/cria")

SAMPLE_CSV = Path(__file__).with_name("sample.csv")


def _load_dataset() -> tuple[pd.DataFrame, str]:
    """Load CRIA data, preferring the database over the sample CSV.

    Returns:
        (df, source_label) where source_label is a human-readable string
        describing which source was actually used — printed to stderr and
        surfaced in the UI so it is never silent.

    Strategy:
        1. Try load_from_db() — uses dbo.Employees via current app config.
        2. On any failure (connection error, empty table, no app context),
           log a LOUD warning to stderr and fall back to sample.csv.
        3. If the CSV also fails, re-raise so the route can flash an error.
    """
    try:
        df = load_from_db()
        source = f"SQL Server — dbo.Employees ({len(df)} row{'s' if len(df) != 1 else ''})"
        print(f"[CRIA] Data source: {source}", file=sys.stderr, flush=True)
        return df, source
    except Exception as db_exc:
        warning = (
            f"\n[CRIA] WARNING: Could not load data from database "
            f"({db_exc!s}), falling back to sample.csv\n"
        )
        print(warning, file=sys.stderr, flush=True)

    # Fallback — CSV must work or we propagate the error to the caller
    df = load_csv(str(SAMPLE_CSV))
    source = f"sample.csv (fallback — DB unavailable)"
    print(f"[CRIA] Data source: {source}", file=sys.stderr, flush=True)
    return df, source


def _render_index(active_tab: str = "ask", **extra):
    """Render the CRIA page with dataset info and optional result context."""
    df, source = _load_dataset()
    context = {
        "username": session.get("username", "Admin"),
        "row_count": len(df),
        "columns": list(df.columns),
        "active_tab": active_tab,
        "data_source": source,
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
        df, _source = _load_dataset()
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
        df, _source = _load_dataset()
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
        df, _source = _load_dataset()
        chart_df = _apply_optional_filter(df, filter_text)
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


@cria_bp.route("/smart", methods=["POST"])
@login_required
@role_required("Admin")
def smart():
    """Smart mode — single natural-language input, Gemini picks the action.

    Returns the same cria/index.html template with a ``smart_result`` dict
    that the template uses to render the correct output (table / chart / text).
    The existing tabs (Ask AI, Filter, Draw chart) are completely unaffected.
    """
    user_input = request.form.get("smart_input", "").strip()
    if not user_input:
        flash("Please enter a request.", "warning")
        return _render_index(active_tab="smart")

    try:
        df, _source = _load_dataset()
        result = handle_request(
            user_input,
            df,
            charts_dir=_charts_dir(),
        )
    except Exception as exc:
        flash(f"Smart mode error: {exc}", "error")
        return _render_index(active_tab="smart", smart_input=user_input)

    # Normalise the result so the template always gets consistent keys.
    action  = result.get("action", "answer")
    message = result.get("message", "")

    smart_result = {
        "action":       action,
        "message":      message,
        "user_input":   user_input,
        # filter-specific
        "filter_rows":    None,
        "filter_columns": [],
        # chart-specific
        "chart_filename": None,
    }

    if action == "filter":
        filtered_df = result.get("result")
        if filtered_df is not None and not filtered_df.empty:
            smart_result["filter_rows"]    = filtered_df.to_dict(orient="records")
            smart_result["filter_columns"] = list(filtered_df.columns)

    elif action == "chart":
        chart_path = result.get("result", "")
        # chart_path is already relative to static/ (e.g. "cria_charts/chart_xxx.png")
        smart_result["chart_filename"] = chart_path

    return _render_index(
        active_tab="smart",
        smart_input=user_input,
        smart_result=smart_result,
    )
