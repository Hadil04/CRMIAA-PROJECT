"""Manual smoke test for CRIA chart generation."""

from pathlib import Path

from app.cria.data_loader import load_csv
from app.cria.filter import filter_data
from app.cria.graph_maker import make_bar_chart, make_pie_chart


if __name__ == "__main__":
    sample_path = Path(__file__).with_name("sample.csv")
    df = load_csv(str(sample_path))

    bar_path = make_bar_chart(df, "name", "salary", title="Salary by Employee")
    print(f"Bar chart saved to: {bar_path}")

    pie_path = make_pie_chart(
        df,
        "department",
        "salary",
        title="Salary Distribution by Department",
    )
    print(f"Pie chart saved to: {pie_path}")

    filtered_df = filter_data(df, "salary", ">", 50000)
    print("\nFiltered (salary > 50000):")
    print(filtered_df)

    filtered_bar_path = make_bar_chart(
        filtered_df,
        "name",
        "salary",
        title="Salary by Employee (salary > 50000)",
        save_path="app/cria/output_chart_filtered.png",
    )
    print(f"\nFiltered bar chart saved to: {filtered_bar_path}")
