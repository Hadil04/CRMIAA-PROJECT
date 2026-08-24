"""CRIA CLI — interactive menu for data questions, filtering, and charts."""

import sys
from pathlib import Path

import pandas as pd

from app.cria.ai_client import ask_ai, handle_request
from app.cria.data_loader import load_csv, load_from_db
from app.cria.filter import filter_data, parse_filter_request
from app.cria.graph_maker import make_bar_chart, make_pie_chart


SAMPLE_CSV = Path(__file__).with_name("sample.csv")


def load_data() -> pd.DataFrame:
    """Load CRIA data, preferring dbo.Employees over the sample CSV.

    Strategy (same as routes.py):
        1. Create a Flask app context so get_connection() works.
        2. Call load_from_db(); on success, print the source and return.
        3. On any error, print a LOUD warning and fall back to sample.csv.
        4. If the CSV also fails, re-raise.
    """
    # Import here to avoid circular imports at module load time.
    from app import create_app

    app = create_app()
    with app.app_context():
        try:
            df = load_from_db()
            source = (
                f"SQL Server — dbo.Employees "
                f"({len(df)} row{'s' if len(df) != 1 else ''})"
            )
            print(f"[CRIA] Data source: {source}")
            return df
        except Exception as db_exc:
            print(
                f"\n[CRIA] WARNING: Could not load data from database "
                f"({db_exc!s}), falling back to sample.csv\n",
                file=sys.stderr,
                flush=True,
            )

    # Fallback — outside the app context; load_csv needs no Flask context.
    df = load_csv(str(SAMPLE_CSV))
    print(f"[CRIA] Data source: sample.csv (fallback — {len(df)} rows)")
    return df


def print_menu() -> None:
    """Display the main menu."""
    print("\nCRIA — What would you like to do?")
    print("1. Ask a question about the data (AI)")
    print("2. Filter the data")
    print("3. Draw a graph")
    print("4. Smart mode — natural language (auto-detect action)")
    print("5. Exit")


def read_menu_choice() -> str | None:
    """Read and validate a menu choice, or None if invalid."""
    choice = input("\nEnter choice (1-5): ").strip()
    if choice in {"1", "2", "3", "4", "5"}:
        return choice
    print("Invalid choice. Please enter a number from 1 to 5.")
    return None


def prompt_filter(df: pd.DataFrame) -> pd.DataFrame | None:
    """Prompt for a filter request and return the filtered DataFrame, or None to cancel."""
    while True:
        filter_request = input(
            "\nEnter a filter request (e.g. 'salary above 50000'), "
            "or press Enter to cancel: "
        ).strip()
        if not filter_request:
            print("Cancelled.")
            return None

        try:
            parsed = parse_filter_request(filter_request)
            filtered = filter_data(df, **parsed)
            print("\nFiltered rows:")
            if filtered.empty:
                print("(no matching rows)")
            else:
                print(filtered)
            return filtered
        except ValueError as exc:
            print(f"\nCould not parse or apply filter: {exc}")
            again = input("Try again? (y/n): ").strip().lower()
            if again != "y":
                return None


def handle_ask_question(df: pd.DataFrame) -> None:
    """Prompt for a question and print the AI answer, using df as context."""
    question = input("\nYour question: ").strip()
    if not question:
        print("No question entered.")
        return

    print("\nThinking...")
    answer = ask_ai(question, df)
    print(f"\nAnswer:\n{answer}")


def handle_filter(df: pd.DataFrame) -> None:
    """Run the filter workflow."""
    prompt_filter(df)


def handle_graph(df: pd.DataFrame) -> None:
    """Run the graph workflow, optionally applying a filter first."""
    chart_df = df

    apply_filter = input("\nApply a filter before drawing? (y/n): ").strip().lower()
    if apply_filter == "y":
        filtered = prompt_filter(df)
        if filtered is None:
            proceed = input("Continue without a filter? (y/n): ").strip().lower()
            if proceed != "y":
                return
        else:
            chart_df = filtered

    if chart_df.empty:
        print("No data to graph.")
        return

    print("\nChart type:")
    print("1. Bar chart")
    print("2. Pie chart")
    chart_choice = input("Enter choice (1-2): ").strip()
    if chart_choice not in {"1", "2"}:
        print("Invalid chart type.")
        return

    available = ", ".join(str(col) for col in chart_df.columns)
    print(f"\nAvailable columns: {available}")

    if chart_choice == "1":
        x_column = input("X-axis column (categories): ").strip()
        y_column = input("Y-axis column (numeric values): ").strip()
        title = input("Chart title (optional, press Enter to auto-generate): ").strip()
        save_path = make_bar_chart(
            chart_df,
            x_column,
            y_column,
            title=title or None,
        )
    else:
        label_column = input("Label column (slice names): ").strip()
        value_column = input("Value column (numeric): ").strip()
        title = input("Chart title (optional, press Enter to auto-generate): ").strip()
        save_path = make_pie_chart(
            chart_df,
            label_column,
            value_column,
            title=title or None,
        )

    print(f"\nChart saved to: {save_path}")


def handle_smart_request(df: pd.DataFrame) -> None:
    """Option 4 — Smart mode: one natural-language input, Gemini picks the action."""
    user_input = input("\nWhat would you like to do? ").strip()
    if not user_input:
        print("No input entered.")
        return

    print("\nThinking…")

    result = handle_request(user_input, df, charts_dir=None)
    action  = result.get("action")
    message = result.get("message", "")

    if action == "filter":
        filtered_df = result.get("result")
        print(f"\n{message}")
        if filtered_df is not None and not filtered_df.empty:
            print(filtered_df.to_string(index=False))
        else:
            print("(no matching rows)")

    elif action == "chart":
        chart_path = result.get("result", "")
        print(f"\n{message}")
        print(f"Chart saved to: {chart_path}")

    else:  # "answer"
        print(f"\nAnswer:\n{message}")


def main() -> None:
    """Run the CRIA interactive menu."""
    df = load_data()

    while True:
        print_menu()
        choice = read_menu_choice()
        if choice is None:
            continue
        if choice == "5":
            print("\nGoodbye!")
            break

        try:
            if choice == "1":
                handle_ask_question(df)
            elif choice == "2":
                handle_filter(df)
            elif choice == "3":
                handle_graph(df)
            elif choice == "4":
                handle_smart_request(df)
        except Exception as exc:
            print(f"\nSomething went wrong: {exc}")


if __name__ == "__main__":
    main()
