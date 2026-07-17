"""CRIA CLI — interactive menu for data questions, filtering, and charts."""

from pathlib import Path

import pandas as pd

from app.cria.ai_client import ask_ai
from app.cria.data_loader import load_csv
from app.cria.filter import filter_data, parse_filter_request
from app.cria.graph_maker import make_bar_chart, make_pie_chart


SAMPLE_CSV = Path(__file__).with_name("sample.csv")


def load_data() -> pd.DataFrame:
    """Load the sample CSV and print a short confirmation."""
    df = load_csv(str(SAMPLE_CSV))
    columns = ", ".join(str(name) for name in df.columns)
    print(f"Loaded {len(df)} rows with columns: {columns}\n")
    return df


def print_menu() -> None:
    """Display the main menu."""
    print("CRIA — What would you like to do?")
    print("1. Ask a question about the data (AI)")
    print("2. Filter the data")
    print("3. Draw a graph")
    print("4. Exit")


def read_menu_choice() -> str | None:
    """Read and validate a menu choice, or None if invalid."""
    choice = input("\nEnter choice (1-4): ").strip()
    if choice in {"1", "2", "3", "4"}:
        return choice
    print("Invalid choice. Please enter a number from 1 to 4.")
    return None


def prompt_filter(df: pd.DataFrame) -> pd.DataFrame | None:
    """Prompt for a filter request and return the filtered DataFrame, or None to cancel."""
    while True:
        request = input(
            "\nEnter a filter request (e.g. 'salary above 50000'), "
            "or press Enter to cancel: "
        ).strip()
        if not request:
            print("Cancelled.")
            return None

        try:
            parsed = parse_filter_request(request)
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

    available = ", ".join(str(name) for name in chart_df.columns)
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


def main() -> None:
    """Run the CRIA interactive menu."""
    df = load_data()

    while True:
        print_menu()
        choice = read_menu_choice()
        if choice is None:
            continue
        if choice == "4":
            print("\nGoodbye!")
            break

        try:
            if choice == "1":
                handle_ask_question(df)
            elif choice == "2":
                handle_filter(df)
            elif choice == "3":
                handle_graph(df)
        except Exception as exc:
            print(f"\nSomething went wrong: {exc}")


if __name__ == "__main__":
    main()