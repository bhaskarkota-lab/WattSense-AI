"""
WattSense AI™ - State Grid Corporation of China (SGCC) Dataset Preprocessor
"""
from pathlib import Path
import pandas as pd

def locate_csv(folder: Path):
    candidates = list(folder.glob("*.csv")) + list(folder.glob("*.CSV"))
    if not candidates:
        raise FileNotFoundError(
            "No SGCC CSV found. Download the dataset from "
            "https://github.com/henryRDlab/ElectricityTheftDetection "
            "and place the extracted CSV file(s) in data/raw/sgcc/."
        )
    # Prefer the main training file if repository naming is preserved.
    candidates.sort(key=lambda p: ("train" not in p.name.lower(), p.name))
    return candidates[0]

def main():
    project_root = Path(__file__).resolve().parent
    if project_root.name == "scripts":
        project_root = project_root.parent
    SOURCE = project_root / "data" / "raw" / "sgcc"
    OUT = project_root / "data" / "processed" / "sgcc_clean.csv"

    source = locate_csv(SOURCE)
    print(f"Reading {source}")
    df = pd.read_csv(source, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    # Common SGCC files use a customer identifier, a FLAG label,
    # and one column per daily consumption reading.
    label_candidates = [c for c in df.columns if c.lower() in {"flag", "label", "target", "class"}]
    if not label_candidates:
        raise ValueError(
            f"Could not identify the label column. Columns found: {list(df.columns)[:12]}. "
            "Expected 'FLAG' or similar."
        )
    label_col = label_candidates[0]

    id_candidates = [c for c in df.columns if c.lower() in {"cons_no", "id", "customer_id", "meter_id"}]
    id_col = id_candidates[0] if id_candidates else df.columns[0]

    # Everything else is expected to be a date column (daily consumption)
    reserved = {label_col, id_col}
    date_cols = [c for c in df.columns if c not in reserved]
    print(f"Found {len(df):,} customers, label column '{label_col}', and {len(date_cols)} date columns.")

    # Clean the numeric matrix: replace NaNs with forward/backward fill per customer
    readings = df[date_cols].apply(pd.to_numeric, errors="coerce")
    readings = readings.interpolate(axis=1, limit_direction="both").fillna(0.0)

    clean = pd.DataFrame()
    clean["customer_id"] = df[id_col].astype(str)
    clean["is_fraud"] = df[label_col].astype(int)

    # Summary statistics engineered as initial quick-features
    clean["mean_consumption"] = readings.mean(axis=1)
    clean["std_consumption"] = readings.std(axis=1).fillna(0.0)
    clean["max_consumption"] = readings.max(axis=1)
    clean["zero_days"] = (readings == 0).sum(axis=1)

    # Attach cleaned raw daily matrix for downstream advanced modeling
    clean = pd.concat([clean, readings], axis=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(OUT, index=False)
    print(f"Saved processed dataset to {OUT} ({clean.shape[0]:,} rows x {clean.shape[1]:,} columns).")

if __name__ == "__main__":
    main()
