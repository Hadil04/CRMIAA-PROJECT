"""Manual smoke test for CRIA CSV loading."""

from pathlib import Path

from app.cria.data_loader import load_csv


if __name__ == "__main__":
    sample_path = Path(__file__).with_name("sample_data.csv")
    dataframe = load_csv(str(sample_path))

    print("CSV head:")
    print(dataframe.head())
    print("\nCSV info:")
    dataframe.info()

