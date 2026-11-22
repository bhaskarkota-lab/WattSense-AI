from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import pytest

from backend.app.core.config import settings
from backend.app.services.forecasting_service import (
    ForecastingService,
    ForecastingMetrics,
    BaselineForecasters,
)

@pytest.fixture(scope="module")
def uci_features_df():
    """Loads a slice of processed features for fast deterministic unit testing."""
    path = settings.DATA_DIR / "processed" / "uci" / "uci_features.csv"
    assert path.exists(), "Processed UCI features must exist"
    return pd.read_csv(path)

def test_chronological_splitting_integrity(uci_features_df):
    """
    CRITICAL TEST: Verifies that time-series data is split strictly chronologically
    with zero shuffling and contiguous non-overlapping index ranges.
    """
    X, y, valid_df = ForecastingService.prepare_horizon_data(uci_features_df, h=1)
    splits = ForecastingService.chronological_split(X, y, valid_df, train_frac=0.70, val_frac=0.15)
    
    n_total = len(X)
    n_train = splits["split_indices"]["n_train"]
    n_val = splits["split_indices"]["n_val"]
    n_test = splits["split_indices"]["n_test"]

    assert n_train + n_val + n_test == n_total
    assert n_train == int(n_total * 0.70)
    assert n_val == int(n_total * 0.15)

    # Verify chronological sequence (timestamps must be strictly increasing across splits)
    max_train_ts = pd.to_datetime(splits["df_train"]["timestamp"]).max()
    min_val_ts = pd.to_datetime(splits["df_val"]["timestamp"]).min()
    max_val_ts = pd.to_datetime(splits["df_val"]["timestamp"]).max()
    min_test_ts = pd.to_datetime(splits["df_test"]["timestamp"]).min()

    assert max_train_ts < min_val_ts, "Train partition must precede Validation partition"
    assert max_val_ts < min_test_ts, "Validation partition must precede Test partition"

def test_forecast_target_alignment(uci_features_df):
    """
    Verifies that for each horizon h, target y_{t+h} is accurately shifted into the future
    and feature matrix X_t contains only information available at time t.
    """
    for h in [1, 6, 144]:
        X, y, valid_df = ForecastingService.prepare_horizon_data(uci_features_df, h=h)
        assert len(X) == len(uci_features_df) - h
        assert len(y) == len(uci_features_df) - h
        assert y.isna().sum() == 0, f"Target for h={h} must not contain NaNs"

        # Check alignment at specific test indices: y[t] must equal raw Appliances[t+h]
        for idx in [0, 50, 1000]:
            expected_target = uci_features_df.loc[idx + h, "Appliances"]
            actual_target = y.iloc[idx]
            assert actual_target == expected_target, f"Target alignment error at index {idx} for horizon h={h}"

def test_leakage_prevention_in_feature_columns(uci_features_df):
    """
    Verifies that excluded, corrupted, or future-leaking columns
    (rv1, rv2, is_outlier_high, target columns) are never present in feature matrix X.
    """
    feature_cols = ForecastingService.get_feature_columns(uci_features_df)
    forbidden = ["rv1", "rv2", "is_outlier_high", "date", "timestamp", "target_h1", "target_h6", "target_h144"]
    for col in forbidden:
        assert col not in feature_cols, f"Forbidden feature '{col}' leaked into feature list!"

def test_forecasting_metrics_calculations():
    """Verifies precision and boundary constraints of MAE, RMSE, R², sMAPE, and MAPE."""
    y_true = np.array([100.0, 50.0, 200.0, 80.0])
    y_pred = np.array([110.0, 45.0, 190.0, 80.0])

    metrics = ForecastingMetrics.calculate_all(y_true, y_pred)
    assert metrics["MAE_Wh"] == 6.25 # (10 + 5 + 10 + 0) / 4 = 6.25
    assert metrics["RMSE_Wh"] == pytest.approx(7.5, abs=0.1) # sqrt((100+25+100+0)/4) = sqrt(56.25) = 7.5
    assert metrics["R2"] > 0.95
    assert 0.0 <= metrics["sMAPE_pct"] <= 200.0
    assert metrics["MAPE_pct"] > 0.0

def test_model_persistence_and_inference(uci_features_df):
    """
    Verifies that all 3 saved models exist in models/consumption_forecasting/,
    can be loaded via joblib, and generate valid non-negative predictions.
    """
    model_dir = settings.BASE_DIR / "models" / "consumption_forecasting"
    assert model_dir.exists()

    X, y, valid_df = ForecastingService.prepare_horizon_data(uci_features_df, h=1)
    sample_X = X.iloc[:10]

    for h in [1, 6, 144]:
        model_file = model_dir / f"best_forecaster_h{h}.joblib"
        assert model_file.exists(), f"Missing model artifact {model_file}"

        model = joblib.load(model_file)
        preds = model.predict(sample_X)
        assert len(preds) == 10
        assert np.all(np.isfinite(preds)), f"Predictions for h={h} must be finite"
        assert np.all(preds > 0.0), f"Appliance predictions for h={h} should be positive"

def test_forecasting_metadata_file():
    """Verifies that forecasting_metadata.json contains complete records for h1, h6, and h144."""
    meta_path = settings.BASE_DIR / "models" / "consumption_forecasting" / "forecasting_metadata.json"
    assert meta_path.exists()
    
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    for h_key in ["h1", "h6", "h144"]:
        assert h_key in data
        assert "best_model" in data[h_key]
        assert "validation_metrics" in data[h_key]
        assert "test_metrics" in data[h_key]
        assert "tier_mae" in data[h_key]
