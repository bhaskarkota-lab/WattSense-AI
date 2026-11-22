"""
Phase 2 Dataset Inspector and Profiler
Audits UCI Appliances, SGCC, and other available electricity datasets.
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np

def inspect_uci(base_dir: Path):
    uci_path = base_dir / "data" / "raw" / "uci" / "energydata_complete.csv"
    if not uci_path.exists():
        return {"status": "NOT_FOUND", "path": str(uci_path)}
    
    df = pd.read_csv(uci_path)
    total_records = len(df)
    features_count = len(df.columns)
    missing_series = df.isna().sum()
    missing_total = int(missing_series.sum())
    
    # Check date with robust format detection
    date_col = "date" if "date" in df.columns else None
    if date_col:
        # Standardize space separation between YYYY-MM-DD and HH:MM:SS
        date_clean = df[date_col].astype(str).str.replace(r"(\d{4}-\d{2}-\d{2})(\d{2}:)", r"\1 \2", regex=True)
        df["dt"] = pd.to_datetime(date_clean, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        dt_sorted = bool(df["dt"].is_monotonic_increasing)
        dt_start = str(df["dt"].min())
        dt_end = str(df["dt"].max())
        duplicates_count = int(df["dt"].duplicated().sum())
        deltas = df["dt"].diff().dropna().unique()
        delta_strings = [str(d) for d in deltas[:5]]
    else:
        dt_sorted = False
        dt_start = dt_end = None
        duplicates_count = 0
        delta_strings = []

    # Target: Appliances
    target_stats = {}
    if "Appliances" in df.columns:
        s = pd.to_numeric(df["Appliances"], errors="coerce")
        q25, q75 = s.quantile(0.25), s.quantile(0.75)
        iqr = q75 - q25
        upper_outlier_bound = q75 + 1.5 * iqr
        outliers_count = int((s > upper_outlier_bound).sum())
        target_stats = {
            "unit": "Wh (Watt-hours)",
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(round(s.mean(), 2)),
            "std": float(round(s.std(), 2)),
            "median": float(s.median()),
            "negative_values": int((s < 0).sum()),
            "zero_values": int((s == 0).sum()),
            "outliers_count_iqr": outliers_count,
            "outliers_fraction": float(round(outliers_count / total_records, 4)),
            "upper_fence_Wh": float(round(upper_outlier_bound, 2))
        }

    return {
        "dataset_name": "UCI Appliances Energy Prediction",
        "provenance": "Luis M. Candanedo et al. (2017), UCI Machine Learning Repository (ID 374), CC BY 4.0",
        "file_path": str(uci_path),
        "total_records": total_records,
        "features_count": features_count,
        "columns": list(df.columns),
        "sampling_interval": "10 minutes",
        "timestamp_coverage": {
            "start": dt_start,
            "end": dt_end,
            "is_sorted": dt_sorted,
            "duplicate_timestamps": duplicates_count,
            "observed_deltas": delta_strings
        },
        "missing_values": {
            "total_missing": missing_total,
            "columns_with_missing": {k: int(v) for k, v in missing_series.items() if v > 0}
        },
        "target_analysis": target_stats
    }

def inspect_other_dataset(other_path: Path):
    if not other_path.exists():
        return {"status": "NOT_FOUND", "path": str(other_path)}
    
    df = pd.read_csv(other_path)
    total_records = len(df)
    features_count = len(df.columns)
    missing_total = int(df.isna().sum().sum())
    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    negatives = int((numeric_df < 0).sum().sum())

    stats = {}
    for col in df.columns:
        s = numeric_df[col].dropna()
        stats[col] = {
            "min": float(s.min()) if not s.empty else None,
            "max": float(s.max()) if not s.empty else None,
            "mean": float(round(s.mean(), 2)) if not s.empty else None,
            "std": float(round(s.std(), 2)) if not s.empty else None
        }

    return {
        "dataset_name": "Ancillary Electricity Sub-metering Dataset",
        "provenance": "Local workspace downloads (HVAC sub-metering component reading sample)",
        "file_path": str(other_path),
        "total_records": total_records,
        "features_count": features_count,
        "columns": list(df.columns),
        "sampling_interval": "Unspecified (Snapshot / Synthetic HVAC readings)",
        "measurement_units": "kW or Watts (Unlabelled numeric sub-metering)",
        "missing_values": missing_total,
        "negative_values": negatives,
        "suitability": "Limited to sub-meter component demonstration (Lighting, Chiller, Cooling_Tower). Not suitable for time-series forecasting without timestamps.",
        "feature_stats": stats
    }

def inspect_sgcc(base_dir: Path):
    sgcc_folder = base_dir / "data" / "raw" / "sgcc"
    candidates = list(sgcc_folder.glob("*.csv")) + list(sgcc_folder.glob("*.CSV")) if sgcc_folder.exists() else []
    
    if not candidates:
        return {
            "dataset_name": "State Grid Corporation of China (SGCC) Electricity Theft Dataset",
            "provenance": "State Grid Corporation of China (SGCC), public research dataset hosted by henryRDlab/ElectricityTheftDetection and IEEE Dataport",
            "file_path": str(sgcc_folder),
            "status": "NOT_PRESENT_LOCALLY",
            "official_source": "https://github.com/henryRDlab/ElectricityTheftDetection (split archives: data.zip, data.z01, data.z02) or IEEE Dataport: 'Electricity Theft Detection in Smart Grids'",
            "target_nature": "Class 1: Meter tampering / electricity theft detection benchmark. NOT general household wastage.",
            "expected_structure": "42,372 customer daily consumption profiles across 1,035 days. Units require verification (kWh or normalized daily consumption)."
        }
    
    first = candidates[0]
    df = pd.read_csv(first, nrows=50)
    return {
        "dataset_name": "SGCC Electricity Theft Dataset",
        "status": "PRESENT",
        "file_path": str(first),
        "preview_columns": list(df.columns[:15]),
        "total_columns": len(df.columns)
    }

def main():
    base_dir = Path(__file__).resolve().parent.parent.parent
    uci_audit = inspect_uci(base_dir)
    other_path = Path("C:/Users/pavan/Downloads/electricity_dataset.csv")
    other_audit = inspect_other_dataset(other_path)
    sgcc_audit = inspect_sgcc(base_dir)

    report = {
        "uci_appliances": uci_audit,
        "ancillary_electricity": other_audit,
        "sgcc_theft": sgcc_audit
    }

    out_file = base_dir / "reports" / "data_quality" / "dataset_audit_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Dataset audit report generated at: {out_file}")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
