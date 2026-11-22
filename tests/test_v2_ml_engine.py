"""
WattSense AI™ — Machine Learning V2 Test Suite
Tests advanced multi-horizon forecasting, conformal intervals, multi-method anomaly detection,
explainability, drift monitoring, and V2 API endpoints.
"""
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from ml.v2.metrics import V2ForecastingMetrics
from ml.v2.feature_engineering import V2FeatureEngineeringPipeline
from ml.v2.forecasting_models import ConformalPredictionCalibrator, DeepTimeSeriesTheoreticalBenchmark
from ml.v2.anomaly_engine import V2MultiMethodAnomalyDetector
from ml.v2.drift_monitor import V2ConceptDriftMonitor
from ml.v2.explainability import V2ExplainabilityService
from ml.v2.registry import V2ModelRegistry


client = TestClient(app)


def test_v2_metrics_calculations():
    y_true = np.array([100.0, 150.0, 200.0, 250.0])
    y_pred = np.array([110.0, 140.0, 210.0, 240.0])

    metrics = V2ForecastingMetrics.calculate_point_metrics(y_true, y_pred)
    assert metrics["MAE_Wh"] == 10.0
    assert metrics["RMSE_Wh"] == 10.0
    assert metrics["R2"] > 0.90
    assert metrics["forecast_bias_Wh"] == 0.0  # (10 - 10 + 10 - 10) / 4 = 0

    lower = np.array([90.0, 130.0, 190.0, 230.0])
    upper = np.array([120.0, 160.0, 220.0, 260.0])
    int_eval = V2ForecastingMetrics.evaluate_prediction_intervals(y_true, lower, upper)
    assert int_eval["coverage_pct"] == 100.0
    assert int_eval["mean_interval_width_Wh"] == 30.0


def test_v2_conformal_calibrator():
    calib = ConformalPredictionCalibrator(confidence_level=0.90)
    y_calib = np.linspace(50, 200, 100)
    # Add random noise
    np.random.seed(42)
    noise = np.random.normal(0, 10, 100)
    y_pred = y_calib + noise

    calib.fit(y_calib, y_pred)
    assert calib.q_error > 0.0

    lower, upper = calib.predict_interval(y_pred[:10])
    assert len(lower) == 10
    assert len(upper) == 10
    assert (lower <= upper).all()
    assert (lower >= 0.0).all()


def test_v2_feature_engineering_pipeline():
    # Synthetic test DataFrame matching UCI schema
    n = 200
    dates = pd.date_range("2026-01-01", periods=n, freq="10min")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d %H:%M:%S"),
        "Appliances": np.random.uniform(20, 200, n),
        "T1": np.random.uniform(18, 22, n),
        "T_out": np.random.uniform(5, 12, n),
        "RH_1": np.random.uniform(35, 55, n),
        "RH_out": np.random.uniform(60, 90, n),
    })

    clean = V2FeatureEngineeringPipeline.generate_features(df)
    assert len(clean) == n - 144  # 144 lead rows dropped
    assert "appliances_lag_1" in clean.columns
    assert "appliances_roll_mean_6" in clean.columns
    assert "temp_diff_indoor_outdoor" in clean.columns
    assert clean.isnull().sum().sum() == 0


def test_v2_multi_method_anomaly_detector_persistence():
    detector = V2MultiMethodAnomalyDetector(contamination=0.05, min_consecutive_intervals=3)
    n = 200
    dates = pd.date_range("2026-01-01", periods=n, freq="10min")
    df = pd.DataFrame({
        "Appliances": np.full(n, 50.0),
        "hour": dates.hour,
        "dayofweek": dates.dayofweek,
        "T1": np.full(n, 20.0),
        "T_out": np.full(n, 10.0),
        "RH_1": np.full(n, 40.0),
        "RH_out": np.full(n, 70.0),
    })
    feature_cols = ["Appliances", "hour", "dayofweek", "T1", "T_out", "RH_1", "RH_out"]
    detector.fit(df, feature_cols)

    # 1. Test single isolated spike (should be suppressed by persistence filter)
    test_df_1 = df.iloc[:10].copy()
    test_df_1.loc[3, "Appliances"] = 500.0  # 1 spike
    ts = np.array([str(d) for d in dates[:10]])
    res_1 = detector.detect_and_filter_events(test_df_1, feature_cols, ts)
    assert res_1["sustained_events_count"] == 0
    assert res_1["suppressed_isolated_bursts"] >= 1

    # 2. Test 3 consecutive spikes (should trigger a sustained event)
    test_df_3 = df.iloc[:10].copy()
    test_df_3.loc[3:5, "Appliances"] = 500.0  # 3 spikes (30 min)
    res_3 = detector.detect_and_filter_events(test_df_3, feature_cols, ts)
    assert res_3["sustained_events_count"] == 1
    assert res_3["events"][0]["consecutive_steps"] == 3
    assert res_3["events"][0]["duration_minutes"] == 30


def test_v2_drift_monitor_psi():
    np.random.seed(42)
    ref = np.random.normal(100, 15, 1000)
    same = np.random.normal(100, 15, 1000)
    drifted = np.random.normal(150, 30, 1000)

    psi_same = V2ConceptDriftMonitor.calculate_psi(ref, same)
    psi_drifted = V2ConceptDriftMonitor.calculate_psi(ref, drifted)

    assert psi_same < 0.10  # Stable
    assert psi_drifted > 0.25  # Significant drift


def test_v2_deep_learning_benchmark_assessment():
    eval_res = DeepTimeSeriesTheoreticalBenchmark.assess_deep_model_suitability(19735, 1)
    assert eval_res["data_sufficiency_verdict"] == "INSUFFICIENT_FOR_STABLE_DEEP_TRAINING"
    assert "single household" in eval_res["scientific_rationale"].lower()


def test_v2_model_registry_preservation():
    V2ModelRegistry.ensure_registry_exists()
    summary = V2ModelRegistry.get_registry_summary()
    assert "champions" in summary
    assert 1 in summary["champions"] or "1" in summary["champions"]
    assert summary["registry_version"] == "v2.0"


# -------------------------------------------------------------
# API ROUTE INTEGRATION TESTS (/api/v2/ml/...)
# -------------------------------------------------------------

def test_api_v2_ml_forecast_h1():
    resp = client.post("/api/v2/ml/forecast", json={"horizon_steps": 1, "confidence_level": 0.90})
    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon_steps"] == 1
    assert data["predicted_mean_Wh"] >= 0.0
    assert data["lower_bound_Wh"] <= data["upper_bound_Wh"]
    assert "explanation" in data


def test_api_v2_ml_forecast_h6():
    resp = client.post("/api/v2/ml/forecast", json={"horizon_steps": 6})
    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon_steps"] == 6
    assert data["predicted_mean_Wh"] >= 0.0


def test_api_v2_ml_forecast_invalid_horizon():
    resp = client.post("/api/v2/ml/forecast", json={"horizon_steps": 99})
    assert resp.status_code == 400


def test_api_v2_ml_anomalies_suppresses_spike():
    # 1 isolated spike in 10 intervals
    readings = [50.0, 50.0, 50.0, 500.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
    resp = client.post("/api/v2/ml/anomalies", json={"readings": readings, "unit": "Wh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sustained_events_count"] == 0
    assert data["suppressed_isolated_bursts"] >= 1


def test_api_v2_ml_anomalies_triggers_3_intervals():
    # 3 consecutive spikes in 10 intervals (30 minutes)
    readings = [50.0, 50.0, 50.0, 500.0, 500.0, 500.0, 50.0, 50.0, 50.0, 50.0]
    resp = client.post("/api/v2/ml/anomalies", json={"readings": readings, "unit": "Wh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sustained_events_count"] == 1
    assert data["events"][0]["duration_minutes"] == 30
    assert data["events"][0]["consecutive_steps"] == 3


def test_api_v2_ml_explanations():
    resp = client.post("/api/v2/ml/explanations", json={
        "forecast_Wh": 250.0,
        "baseline_Wh": 150.0,
        "hour": 19,
        "is_weekend": False,
        "horizon_name": "1_hour_ahead"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["percentage_difference"] > 0
    assert "weekday" in data["customer_friendly_summary"].lower()


def test_api_v2_ml_model_status():
    resp = client.get("/api/v2/ml/model-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["registry_version"] == "v2.0"
    assert "champions" in data
    assert "challengers" in data
    assert "drift_status" in data
