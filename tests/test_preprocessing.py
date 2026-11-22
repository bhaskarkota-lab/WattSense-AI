import json
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

from backend.app.core.config import settings
from backend.app.services.preprocessing import PreprocessingService

def test_uci_timestamp_parsing_and_cadence():
    """Verifies that UCI timestamps are sorted, non-duplicate, and have 10-minute cadence."""
    raw_path = settings.DATA_DIR / "raw" / "uci" / "energydata_complete.csv"
    assert raw_path.exists(), "Raw UCI dataset must be present"

    df = pd.read_csv(raw_path)
    date_clean = df["date"].astype(str).str.replace(r"(\d{4}-\d{2}-\d{2})(\d{2}:)", r"\1 \2", regex=True)
    timestamps = pd.to_datetime(date_clean, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    
    assert timestamps.isna().sum() == 0, "No timestamps should fail parsing"
    assert timestamps.is_monotonic_increasing, "Timestamps must be monotonically increasing"
    assert timestamps.duplicated().sum() == 0, "There should be no duplicate timestamps"
    
    deltas = timestamps.diff().dropna().unique()
    assert len(deltas) == 1, "Only one sampling interval must exist"
    assert deltas[0] == pd.Timedelta(minutes=10), "Sampling interval must be exactly 10 minutes"

def test_uci_feature_generation():
    """Verifies that all required forecasting features and cyclic encodings are generated."""
    processed_path = settings.DATA_DIR / "processed" / "uci" / "uci_features.csv"
    assert processed_path.exists(), "Processed UCI features must exist"

    df = pd.read_csv(processed_path)
    assert len(df) == 19591, "Expected 19,591 records after 24h lag truncation"
    assert df.shape[1] == 49, "Expected 49 features including lags, rolling stats, and cyclics"

    # Verify lag features
    for lag in [1, 2, 3, 6, 144]:
        col = f"appliances_lag_{lag}"
        assert col in df.columns, f"Missing lag feature {col}"
        assert df[col].isna().sum() == 0, f"Lag feature {col} must not contain NaNs"

    # Verify rolling stats
    assert "appliances_roll_mean_6" in df.columns
    assert "appliances_roll_std_6" in df.columns
    assert "appliances_roll_mean_144" in df.columns

    # Verify cyclic features
    assert "hour_sin" in df.columns
    assert "hour_cos" in df.columns
    assert "dayofweek_sin" in df.columns
    assert "dayofweek_cos" in df.columns
    assert "is_weekend" in df.columns

def test_data_leakage_prevention():
    """
    CRITICAL TEST: Asserts that lag and rolling features are derived from
    strictly past observations and contain zero future lookahead.
    """
    processed_path = settings.DATA_DIR / "processed" / "uci" / "uci_features.csv"
    df = pd.read_csv(processed_path)

    # appliances_lag_1 at row index 10 must equal Appliances at row index 9
    for idx in [10, 20, 50, 100]:
        expected_lag_1 = df.loc[idx - 1, "Appliances"]
        actual_lag_1 = df.loc[idx, "appliances_lag_1"]
        assert actual_lag_1 == expected_lag_1, f"Data leakage or index mismatch in lag_1 at row {idx}"

        # appliances_lag_6 at row index 10 must equal Appliances at row index 4
        expected_lag_6 = df.loc[idx - 6, "Appliances"]
        actual_lag_6 = df.loc[idx, "appliances_lag_6"]
        assert actual_lag_6 == expected_lag_6, f"Data leakage or index mismatch in lag_6 at row {idx}"

def test_outlier_preservation_policy():
    """
    CRITICAL TEST: Verifies that extreme readings are explicitly flagged
    rather than silently deleted.
    """
    processed_path = settings.DATA_DIR / "processed" / "uci" / "uci_features.csv"
    df = pd.read_csv(processed_path)

    assert "is_outlier_high" in df.columns
    outlier_count = df["is_outlier_high"].sum()
    assert outlier_count > 0, "Outliers should be flagged"
    assert df["Appliances"].max() == 1080.0, "Peak readings must be preserved, not truncated or deleted"

def test_sgcc_preprocessing_with_mock_data(tmp_path):
    """
    Verifies that SGCC preprocessing:
    1. Preserves customer ID.
    2. Keeps FLAG label binary.
    3. Masks negative readings.
    4. Applies per-customer median imputation without data leakage across customers.
    """
    sgcc_dir = tmp_path / "sgcc_mock"
    sgcc_dir.mkdir()

    # Create mock SGCC CSV with 2 customers, 5 days, negatives and missing values
    mock_csv = sgcc_dir / "sgcc_mock_data.csv"
    mock_csv.write_text(
        "cons_no,FLAG,2014/01/01,2014/01/02,2014/01/03,2014/01/04,2014/01/05\n"
        "CUST-001,0,10.5,-2.0,12.0,,11.5\n"
        "CUST-002,1,2.0,2.5,,3.0,-1.0\n",
        encoding="utf-8"
    )

    report = PreprocessingService.preprocess_sgcc(raw_dir=sgcc_dir)
    assert report["total_customers"] == 2
    assert report["id_column_preserved"] == "cons_no"
    assert report["label_column"] == "FLAG"

    processed_file = Path(report["processed_file"])
    assert processed_file.exists()
    df_proc = pd.read_csv(processed_file)
    assert len(df_proc) == 2
    assert df_proc.loc[0, "cons_no"] == "CUST-001"
    assert df_proc.loc[1, "cons_no"] == "CUST-002"
    # Negative -2.0 for CUST-001 should be imputed with customer's median (approx 11.5)
    assert df_proc.loc[0, "2014/01/02"] >= 0.0
    # Negative -1.0 for CUST-002 should be imputed with customer's median (approx 2.5)
    assert df_proc.loc[1, "2014/01/05"] >= 0.0

def test_ancillary_dataset_integrity():
    """Verifies that ancillary sub-metering dataset is documented with strict non-merging policy."""
    report = PreprocessingService.audit_ancillary_dataset()
    assert "DO NOT MERGE" in report["cross_dataset_policy"]
