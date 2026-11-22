"""
Unit and integration tests for Phase 5 Electricity Wastage Detection Engine.

Validates:
1. Baseline computation algorithms (Global Median, Rolling Median, Rolling Mean/Std, Hour of Day, Day & Hour, Forecast-Assisted).
2. Pure historical baseline enforcement (shifted rolling windows to eliminate lookahead bias).
3. Persistence filtering logic (transient burst suppression vs sustained periods).
4. Potential excess calculation in verified physical units (Wh / kWh).
5. Customer findings sanitization (zero ML jargon, no theft labels, clear actionable phrasing).
6. End-to-end wastage detection backtest workflow via WastageService.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from backend.app.services.baseline_service import BaselineCalculationService
from backend.app.services.persistence_filter import PersistenceFilteringService
from backend.app.services.customer_findings_service import CustomerFindingsService
from backend.app.services.wastage_service import WastageService


@pytest.fixture
def sample_timeseries_df():
    """Create a 7-day 10-minute synthetic consumption series for testing."""
    np.random.seed(42)
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    intervals = 7 * 24 * 6  # 1008 steps
    
    dates = [start_time + timedelta(minutes=10 * i) for i in range(intervals)]
    
    # Base diurnal profile + noise
    consumption = []
    for dt in dates:
        hour = dt.hour
        base = 50.0 + 80.0 * np.exp(-((hour - 19) ** 2) / 10.0)
        noise = np.random.normal(0, 5.0)
        consumption.append(max(10.0, base + noise))
        
    df = pd.DataFrame({
        "timestamp": dates,
        "Appliances": consumption,
        "hour": [dt.hour for dt in dates],
        "dayofweek": [dt.weekday() for dt in dates],
    })
    
    # Inject a 1-interval spike (transient, e.g. kettle at step 100)
    df.loc[100, "Appliances"] = 450.0
    
    # Inject a 4-interval sustained high consumption (e.g. forgotten oven at steps 200-203)
    df.loc[200:203, "Appliances"] = 380.0
    
    # Inject an overnight high consumption (steps 300 to 304, 02:00 AM)
    df.loc[300:304, "Appliances"] = 280.0
    
    return df


def test_baseline_calculation_methods(sample_timeseries_df):
    """Test all historical baseline methods produce valid upper bounds."""
    series = sample_timeseries_df["Appliances"]
    
    # 1. Global median
    exp_gm, up_gm = BaselineCalculationService.historical_global_median(series, series)
    assert len(exp_gm) == len(series)
    assert (up_gm >= exp_gm).all()
    assert float(up_gm[0]) > float(exp_gm[0])
    
    # 2. Rolling median
    exp_rm, up_rm = BaselineCalculationService.rolling_historical_median(series, window=72)
    assert len(exp_rm) == len(series)
    assert not np.isnan(exp_rm).any()
    assert not np.isnan(up_rm).any()
    
    # 3. Rolling mean + std
    exp_rms, up_rms = BaselineCalculationService.rolling_historical_mean_std(series, window=72)
    assert len(exp_rms) == len(series)
    assert not np.isnan(exp_rms).any()
    assert not np.isnan(up_rms).any()
    
    # 4. Hour of day conditional
    train_df = sample_timeseries_df.iloc[:500]
    eval_df = sample_timeseries_df.iloc[500:]
    exp_hod, up_hod = BaselineCalculationService.hour_of_day_conditional(train_df, eval_df)
    assert len(exp_hod) == len(eval_df)
    assert (up_hod >= exp_hod).all()
    
    # 5. Day and hour conditional
    exp_dh, up_dh = BaselineCalculationService.day_and_hour_conditional(train_df, eval_df)
    assert len(exp_dh) == len(eval_df)
    assert (up_dh >= exp_dh).all()
    
    # 6. Forecast assisted
    exp_fa, up_fa = BaselineCalculationService.forecast_assisted_baseline(
        ridge_predictions=exp_dh + 5.0,
        diurnal_expected=exp_dh,
        diurnal_upper=up_dh
    )
    assert len(exp_fa) == len(eval_df)
    assert (up_fa >= exp_fa).all()


def test_no_future_leakage_in_rolling_baselines():
    """Verify rolling baselines shift by 1 to strictly exclude current observation."""
    # Construct a series with an extreme spike at index 10
    vals = [50.0] * 20
    vals[10] = 5000.0
    series = pd.Series(vals)
    
    exp_rm, up_rm = BaselineCalculationService.rolling_historical_median(series, window=5)
    
    # At index 10, the expected value must NOT be influenced by the 5000.0 spike at index 10
    assert exp_rm[10] == 50.0, "Expected baseline at index 10 leaked current observation!"


def test_persistence_filter_suppresses_transient_spikes(sample_timeseries_df):
    """
    Verify that an N=3 (30-minute) persistence filter suppresses a single isolated
    10-minute spike but captures sustained multi-interval events.
    """
    train_df = sample_timeseries_df.iloc[:500]
    eval_df = sample_timeseries_df.iloc[500:].copy().reset_index(drop=True)
    
    # Inject isolated spike at index 50 of eval_df
    eval_df.loc[50, "Appliances"] = 600.0
    # Inject 4 consecutive intervals at index 80-83
    eval_df.loc[80:83, "Appliances"] = 400.0
    
    exp_dh, up_dh = BaselineCalculationService.day_and_hour_conditional(train_df, eval_df)
    actual = eval_df["Appliances"].values
    ts = eval_df["timestamp"].astype(str).values
    
    # Evaluate with N=3
    res_n3 = PersistenceFilteringService.detect_and_filter(
        actual=actual,
        expected=exp_dh,
        upper_bound=up_dh,
        timestamps=ts,
        min_consecutive_intervals=3
    )
    
    # Evaluate with N=1 (unfiltered)
    res_n1 = PersistenceFilteringService.detect_and_filter(
        actual=actual,
        expected=exp_dh,
        upper_bound=up_dh,
        timestamps=ts,
        min_consecutive_intervals=1
    )
    
    # N=3 must have fewer events than N=1 due to suppression of isolated bursts
    assert res_n3["sustained_alert_events_count"] <= res_n1["sustained_alert_events_count"]
    assert res_n3["suppressed_isolated_spikes"] > 0
    assert res_n3["total_potential_excess"] >= 0.0


def test_persistence_sweep_monotonicity(sample_timeseries_df):
    """Verify that increasing N monotonically reduces or maintains the event count."""
    train_df = sample_timeseries_df.iloc[:500]
    eval_df = sample_timeseries_df.iloc[500:]
    
    exp_dh, up_dh = BaselineCalculationService.day_and_hour_conditional(train_df, eval_df)
    actual = eval_df["Appliances"].values
    ts = eval_df["timestamp"].astype(str).values
    
    counts = []
    for n in [1, 2, 3, 4, 6]:
        res = PersistenceFilteringService.detect_and_filter(
            actual=actual,
            expected=exp_dh,
            upper_bound=up_dh,
            timestamps=ts,
            min_consecutive_intervals=n
        )
        counts.append(res["sustained_alert_events_count"])
        
    for i in range(len(counts) - 1):
        assert counts[i] >= counts[i + 1], f"Event count at N={i} ({counts[i]}) was less than N={i+1} ({counts[i+1]})"


def test_customer_findings_sanitization():
    """
    Verify customer-facing findings strictly omit technical ML jargon,
    theft indicators, and internal anomaly scores.
    """
    mock_events = [
        {
            "start_time": "2026-01-05 02:10:00",
            "end_time": "2026-01-05 03:50:00",
            "duration_hours": 1.67,
            "duration_minutes": 100,
            "persistence_intervals": 10,
            "actual_peak": 420.0,
            "peak_consumption": 420.0,
            "mean_consumption": 280.0,
            "expected_avg": 55.0,
            "expected_baseline": 55.0,
            "potential_excess": 1.25,
            "potential_excess_kwh": 1.25,
            "severity": "HIGH",
        }
    ]
    
    findings = CustomerFindingsService.generate_findings(
        events=mock_events,
        unit="kWh",
        total_excess=1.25,
        period_description="January 2026"
    )
    
    assert findings["alert_level"] == "ELEVATED"
    assert findings["events_count"] == 1
    assert findings["total_potential_excess"] == 1.25
    assert len(findings["key_findings"]) >= 2
    
    # Convert whole dict to lowercase string to check for forbidden jargon
    full_text = str(findings).lower()
    forbidden_terms = [
        "ridge", "extratrees", "rmse", "mae", "theft", "roc_auc", 
        "isolationforest", "r2_score", "ground_truth", "dataset"
    ]
    for term in forbidden_terms:
        assert term not in full_text, f"Forbidden technical term '{term}' leaked into customer findings!"


def test_wastage_service_end_to_end(sample_timeseries_df):
    """Test full pipeline run using WastageService.evaluate_consumption_series."""
    train_df = sample_timeseries_df.iloc[:500]
    eval_df = sample_timeseries_df.iloc[500:]
    
    result = WastageService.evaluate_consumption_series(
        series=eval_df["Appliances"],
        timestamps=eval_df["timestamp"],
        baseline_method="day_and_hour",
        train_df=train_df,
        eval_df=eval_df,
        min_persistence=3,
        interval_minutes=10,
        unit="Wh"
    )
    
    assert "detection_results" in result
    assert "customer_findings" in result
    assert "expected_baseline" in result
    assert "upper_bound" in result
    assert result["detection_results"]["total_potential_excess"] >= 0.0
    assert result["customer_findings"]["alert_level"] in ["NORMAL", "ATTENTION_REQUIRED"]
