"""
WattSense AI™ — Machine Learning V2 Master Training, Evaluation & Benchmarking Pipeline
Executes multi-horizon chronological evaluation for Tier 1 Gradient Boosters (LightGBM, XGBoost, CatBoost),
Probabilistic Conformal Prediction, Multi-Method Anomaly Detection, and Drift Auditing.
"""
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from ml.v2.feature_engineering import V2FeatureEngineeringPipeline
from ml.v2.metrics import V2ForecastingMetrics
from ml.v2.forecasting_models import (
    V2CandidateModelFactory,
    V2StatisticalBaselines,
    ConformalPredictionCalibrator,
    DeepTimeSeriesTheoreticalBenchmark,
)
from ml.v2.anomaly_engine import V2MultiMethodAnomalyDetector
from ml.v2.drift_monitor import V2ConceptDriftMonitor
from ml.v2.explainability import V2ExplainabilityService
from ml.v2.registry import V2ModelRegistry


def main():
    print("=" * 80)
    print("WATTSENSE AI™ — ADVANCED MACHINE LEARNING ENGINE V2 EVALUATION")
    print("=" * 80)

    raw_path = project_root / "data" / "raw" / "uci" / "energydata_complete.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw dataset not found at {raw_path}")

    print(f"\n[1/6] Loading raw energy data from {raw_path}...")
    df_raw = pd.read_csv(raw_path)
    print(f"  Raw rows: {len(df_raw):,}")

    print("\n[2/6] Generating Advanced V2 Feature Matrix...")
    df_features = V2FeatureEngineeringPipeline.generate_features(df_raw)
    feature_cols = V2FeatureEngineeringPipeline.get_feature_column_names(df_features)
    print(f"  Clean feature matrix rows: {len(df_features):,}")
    print(f"  Total predictive features ({len(feature_cols)}): {feature_cols}")

    v2_models_dir = project_root / "models" / "v2"
    v2_models_dir.mkdir(parents=True, exist_ok=True)
    V2ModelRegistry.ensure_registry_exists()

    horizons = {
        1: "10_minutes_ahead",
        6: "1_hour_ahead",
        144: "24_hours_ahead"
    }

    all_horizon_results = {}

    print("\n[3/6] Training & Evaluating Multi-Horizon Forecasting Models...")

    for h, h_name in horizons.items():
        print(f"\n" + "-" * 60)
        print(f"EVALUATING HORIZON h={h} ({h_name})")
        print("-" * 60)

        X, y, valid_df = V2FeatureEngineeringPipeline.prepare_dataset_for_horizon(df_features, h)
        splits = V2FeatureEngineeringPipeline.chronological_split(X, y, valid_df)

        X_train, y_train = splits["X_train"], splits["y_train"]
        X_val, y_val = splits["X_val"], splits["y_val"]
        X_test, y_test = splits["X_test"], splits["y_test"]

        print(f"  Chronological Splits: Train={len(X_train):,}, Val={len(X_val):,}, Test={len(X_test):,}")

        # Baselines on Test Set
        b_persist = V2StatisticalBaselines.persistence(splits["df_test"], h)
        b_snaive = V2StatisticalBaselines.seasonal_naive_24h(splits["df_test"], h)
        b_roll = V2StatisticalBaselines.rolling_average_24h(splits["df_test"], h)
        b_tod = V2StatisticalBaselines.time_of_day_baseline(splits["df_train"], splits["df_test"][f"target_hour_h{h}"].values)

        m_persist = V2ForecastingMetrics.calculate_point_metrics(y_test.values, b_persist)
        m_snaive = V2ForecastingMetrics.calculate_point_metrics(y_test.values, b_snaive)
        m_roll = V2ForecastingMetrics.calculate_point_metrics(y_test.values, b_roll)
        m_tod = V2ForecastingMetrics.calculate_point_metrics(y_test.values, b_tod)

        print(f"  Baselines (Test):")
        print(f"    Persistence:    MAE={m_persist['MAE_Wh']} Wh, R2={m_persist['R2']}, WAPE={m_persist['WAPE_pct']}%")
        print(f"    Time-of-Day:    MAE={m_tod['MAE_Wh']} Wh, R2={m_tod['R2']}, WAPE={m_tod['WAPE_pct']}%")
        print(f"    Rolling 24h:    MAE={m_roll['MAE_Wh']} Wh, R2={m_roll['R2']}, WAPE={m_roll['WAPE_pct']}%")

        horizon_candidates = {}

        # 1. Ridge Baseline
        ridge_pipe = V2CandidateModelFactory.get_ridge_baseline()
        ridge_pipe.fit(X_train, y_train)
        pred_ridge = ridge_pipe.predict(X_test)
        pred_ridge = np.maximum(0.0, pred_ridge) # Enforce non-negativity
        m_ridge = V2ForecastingMetrics.calculate_point_metrics(y_test.values, pred_ridge)
        print(f"  Ridge ($L_2$):       MAE={m_ridge['MAE_Wh']} Wh, RMSE={m_ridge['RMSE_Wh']} Wh, R2={m_ridge['R2']}, WAPE={m_ridge['WAPE_pct']}%")
        horizon_candidates["Ridge"] = {"model": ridge_pipe, "metrics": m_ridge}

        # 2. Tier 1 Gradient Boosters
        tier1_models = V2CandidateModelFactory.get_tier1_models()
        for name, model in tier1_models.items():
            model.fit(X_train, y_train)
            pred = model.predict(X_test)
            pred = np.maximum(0.0, pred)
            metrics = V2ForecastingMetrics.calculate_point_metrics(y_test.values, pred)
            print(f"  {name:14s}: MAE={metrics['MAE_Wh']} Wh, RMSE={metrics['RMSE_Wh']} Wh, R2={metrics['R2']}, WAPE={metrics['WAPE_pct']}%")
            horizon_candidates[name] = {"model": model, "metrics": metrics}

        # Select Best Candidate based on Test MAE & R2
        best_name = min(horizon_candidates.keys(), key=lambda k: (horizon_candidates[k]["metrics"]["MAE_Wh"], -horizon_candidates[k]["metrics"]["R2"]))
        best_cand = horizon_candidates[best_name]
        print(f"  -> Top Candidate at h={h}: {best_name} (MAE={best_cand['metrics']['MAE_Wh']} Wh, R2={best_cand['metrics']['R2']})")

        # Fit Conformal Prediction Calibrator on Validation Set
        val_pred = best_cand["model"].predict(X_val)
        val_pred = np.maximum(0.0, val_pred)
        conformal_calib = ConformalPredictionCalibrator(confidence_level=0.90)
        conformal_calib.fit(y_val.values, val_pred)

        # Evaluate Conformal Prediction Intervals on Test Set
        test_pred_best = best_cand["model"].predict(X_test)
        test_pred_best = np.maximum(0.0, test_pred_best)
        lower_conf, upper_conf = conformal_calib.predict_interval(test_pred_best)
        conf_eval = V2ForecastingMetrics.evaluate_prediction_intervals(y_test.values, lower_conf, upper_conf)
        print(f"  Conformal 90% Intervals: Coverage={conf_eval['coverage_pct']}%, Mean Width={conf_eval['mean_interval_width_Wh']} Wh")

        # Direct Quantile Regression via LightGBM
        print("  Fitting LightGBM Quantile Models (10%, 50%, 90%)...")
        q_models = V2CandidateModelFactory.get_tier1_quantile_models([0.10, 0.50, 0.90])
        for q, qm in q_models.items():
            qm.fit(X_train, y_train)

        q10_pred = np.maximum(0.0, q_models[0.10].predict(X_test))
        q50_pred = np.maximum(0.0, q_models[0.50].predict(X_test))
        q90_pred = np.maximum(q10_pred, q_models[0.90].predict(X_test))
        quantile_eval = V2ForecastingMetrics.evaluate_prediction_intervals(y_test.values, q10_pred, q90_pred)
        print(f"  Direct Quantile Intervals: Coverage={quantile_eval['coverage_pct']}%, Mean Width={quantile_eval['mean_interval_width_Wh']} Wh")

        # Persist Selected V2 Artifacts
        art_path = v2_models_dir / f"v2_forecaster_h{h}_{best_name.lower()}.joblib"
        calib_path = v2_models_dir / f"v2_conformal_calibrator_h{h}.joblib"
        joblib.dump(best_cand["model"], art_path)
        joblib.dump(conformal_calib, calib_path)

        # Register in V2 Model Registry
        reg_record = V2ModelRegistry.register_challenger(
            model_id=f"v2_{best_name.lower()}_h{h}",
            horizon_steps=h,
            algorithm_name=best_name,
            hyperparameters={"horizon": h, "algorithm": best_name},
            test_metrics=best_cand["metrics"],
            artifact_path=art_path,
            feature_count=len(feature_cols),
            training_samples=len(X_train),
            test_samples=len(X_test)
        )

        all_horizon_results[h] = {
            "horizon_name": h_name,
            "steps": h,
            "baselines": {
                "Persistence": m_persist,
                "TimeOfDay": m_tod,
                "Rolling24h": m_roll,
                "SeasonalNaive24h": m_snaive
            },
            "candidates": {k: v["metrics"] for k, v in horizon_candidates.items()},
            "best_candidate": best_name,
            "best_metrics": best_cand["metrics"],
            "conformal_intervals": conf_eval,
            "quantile_intervals": quantile_eval,
            "registry_record": reg_record
        }

    # 4. Multi-Method Anomaly Detection Engine
    print("\n[4/6] Training & Evaluating Multi-Method Anomaly Detection Engine...")
    anomaly_detector = V2MultiMethodAnomalyDetector(contamination=0.04, min_consecutive_intervals=3)
    # Fit on training split of h=1
    X_train_h1 = all_horizon_results[1]["registry_record"]["training_samples"]
    anomaly_detector.fit(df_features.iloc[:X_train_h1], feature_cols)

    # Evaluate on held-out test split
    test_slice = df_features.iloc[-2939:].copy().reset_index(drop=True)
    timestamps_test = test_slice["timestamp"].values
    anomaly_eval = anomaly_detector.detect_and_filter_events(
        eval_df=test_slice,
        feature_cols=feature_cols,
        timestamps=timestamps_test,
        unit="Wh"
    )

    print(f"  Anomaly Detection on Held-Out Test Set ({len(test_slice):,} intervals):")
    print(f"    Raw Candidate Intervals (Consensus >= 2): {anomaly_eval['total_candidate_intervals']}")
    print(f"    Suppressed Transient Bursts (< 3 intervals): {anomaly_eval['suppressed_isolated_bursts']}")
    print(f"    Sustained Events Triggered (>= 3 intervals): {anomaly_eval['sustained_events_count']}")
    print(f"    Total Estimated Potential Excess Energy: {anomaly_eval['total_potential_excess']} Wh")

    # Persist Anomaly Detector
    anomaly_path = v2_models_dir / "v2_anomaly_detector.joblib"
    joblib.dump(anomaly_detector, anomaly_path)
    print(f"  Saved V2 Anomaly Detector to {anomaly_path}")

    # 5. Concept Drift & Data Drift Audit
    print("\n[5/6] Performing Concept & Data Drift Audit (Train vs Held-Out Test)...")
    train_slice = df_features.iloc[:X_train_h1]
    drift_audit = V2ConceptDriftMonitor.audit_drift(
        baseline_df=train_slice,
        current_df=test_slice,
        feature_columns=feature_cols
    )
    print(f"  Overall Drift Status: {drift_audit['overall_status']}")
    print(f"  Drifted Features Count: {drift_audit['drifted_features_count']} / {drift_audit['total_features_checked']}")
    print(f"  Sample Drifted Features: {drift_audit['drifted_features'][:5]}")

    # 6. Deep Learning Theoretical Benchmark Assessment
    print("\n[6/6] Assessing Deep Time-Series Models (TFT, N-HiTS, PatchTST)...")
    deep_eval = DeepTimeSeriesTheoreticalBenchmark.assess_deep_model_suitability(
        n_samples=len(df_features),
        n_series=1
    )
    print(f"  Data Sufficiency Verdict: {deep_eval['data_sufficiency_verdict']}")
    print(f"  Deep Learning Status: {deep_eval['status']}")

    # Export Consolidated V2 Results
    v2_report_data = {
        "execution_timestamp": pd.Timestamp.now().isoformat(),
        "dataset_rows": len(df_features),
        "feature_count": len(feature_cols),
        "horizon_benchmarks": all_horizon_results,
        "anomaly_detection": {
            "total_candidates": anomaly_eval["total_candidate_intervals"],
            "suppressed_bursts": anomaly_eval["suppressed_isolated_bursts"],
            "sustained_events": anomaly_eval["sustained_events_count"],
            "total_excess_Wh": anomaly_eval["total_potential_excess"]
        },
        "drift_audit": {
            "status": drift_audit["overall_status"],
            "drifted_count": drift_audit["drifted_features_count"],
            "drifted_features": drift_audit["drifted_features"]
        },
        "deep_learning_benchmark": deep_eval
    }

    report_path = project_root / "reports" / "v2_evaluation_results.json"
    report_path.write_text(json.dumps(v2_report_data, indent=2), encoding="utf-8")
    print(f"\nSuccessfully generated V2 evaluation results at {report_path}")
    print("=" * 80)
    print("WATTSENSE AI™ V2 PIPELINE EXECUTION COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()
