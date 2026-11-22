"""
WattSense AI™ - UCI Appliances Energy Prediction Dataset Downloader
"""
from pathlib import Path
from ucimlrepo import fetch_ucirepo

def main():
    project_root = Path(__file__).resolve().parent
    if project_root.name == "scripts":
        project_root = project_root.parent
    OUT = project_root / "data" / "raw" / "uci" / "energydata_complete.csv"
    OUT.parent.mkdir(parents=True, exist_ok=True)

    print("Downloading UCI Appliances Energy Prediction dataset...")
    dataset = fetch_ucirepo(id=374)
    df = dataset.data.features.copy()

    # UCI returns date among features and Appliances as the target.
    if dataset.data.targets is not None and "Appliances" in dataset.data.targets.columns:
        df["Appliances"] = dataset.data.targets["Appliances"].values

    df.to_csv(OUT, index=False)
    print(f"Saved {len(df):,} rows to {OUT}")
    print("Columns:", ", ".join(df.columns))

if __name__ == "__main__":
    main()
