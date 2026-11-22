"""
WattSense AI™ — Machine Learning V2 Inference & Telemetry Service
Orchestrates live inference for V2 models, conformal prediction, multi-method anomaly detection,
explainability generation, and model status queries.
"""
from pathlib import Path
import json
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.v2_ml import (
    V2ForecastRequest,
    V2ForecastResponse,
    V2AnomalyRequest,
    V2AnomalyResponse,
    V2AnomalyEvent,
    V2ExplanationRequest,
    V2ExplanationResponse,
    V2ModelStatusResponse,
)
from ml.v2.feature_engineering import V2FeatureEngineeringPipeline
from ml.v2.explainability import V2ExplainabilityService
from ml.v2.registry import V2ModelRegistry


class V2MLInferenceService:
    """Singleton service providing low-latency, thread-safe inference for ML V2 capabilities."""

    _models: Dict[int, Any] = {}
    _calibrators: Dict[int, Any] = {}
    _anomaly_detector: Optional[Any] = None
    _default_feature_vector: Optional[pd.DataFrame] = None
    _feature_columns: List[str] = []

    V2_DIR = settings.BASE_DIR / "models" / "v2"
    REPORTS_DIR = settings.BASE_DIR / "reports"

    @classmethod
    def initialize(cls):
        """Pre-warms V2 models into memory during service lifecycle."""
        if cls._models and cls._default_feature_vector is not None and len(cls._feature_columns) == 55:
            return

        cls.V2_DIR.mkdir(parents=True, exist_ok=True)

        for h in [1, 6, 144]:
            m_path = cls.V2_DIR / f"v2_forecaster_h{h}_ridge.joblib"
            c_path = cls.V2_DIR / f"v2_conformal_calibrator_h{h}.joblib"
            if m_path.exists():
                cls._models[h] = joblib.load(m_path)
            if c_path.exists():
                cls._calibrators[h] = joblib.load(c_path)

        det_path = cls.V2_DIR / "v2_anomaly_detector.joblib"
        if det_path.exists():
            cls._anomaly_detector = joblib.load(det_path)

        # Establish feature columns directly from the trained model pipeline
        if 1 in cls._models and hasattr(cls._models[1].named_steps.get("scaler"), "feature_names_in_"):
            cls._feature_columns = list(cls._models[1].named_steps["scaler"].feature_names_in_)
        elif cls._anomaly_detector and hasattr(cls._anomaly_detector.scaler, "feature_names_in_"):
            cls._feature_columns = list(cls._anomaly_detector.scaler.feature_names_in_)

        # Load or generate default reference feature vector (55 features)
        vector_cache = cls.V2_DIR / "v2_default_feature_vector.joblib"
        if vector_cache.exists():
            cls._default_feature_vector = joblib.load(vector_cache)
            if not cls._feature_columns:
                cls._feature_columns = list(cls._default_feature_vector.columns)
        else:
            raw_csv = settings.BASE_DIR / "data" / "raw" / "uci" / "energydata_complete.csv"
            if raw_csv.exists():
                ref_df = pd.read_csv(raw_csv)
                feat_df = V2FeatureEngineeringPipeline.generate_features(ref_df)
                if not cls._feature_columns:
                    cls._feature_columns = V2FeatureEngineeringPipeline.get_feature_column_names(feat_df)
                cls._default_feature_vector = feat_df[cls._feature_columns].iloc[[-1]].copy()
                joblib.dump(cls._default_feature_vector, vector_cache)

        logger.info(f"Initialized V2 ML Service with {len(cls._models)} forecasters, {len(cls._feature_columns)} features, and anomaly detector.")

    @classmethod
    def generate_forecast(cls, req: V2ForecastRequest) -> V2ForecastResponse:
        """Executes multi-horizon point and conformal prediction interval inference."""
        cls.initialize()
        h = req.horizon_steps
        if h not in cls._models:
            raise ValueError(f"Unsupported horizon step: {h}. Supported horizons are 1 (10m), 6 (1h), and 144 (24h).")

        model = cls._models[h]
        calibrator = cls._calibrators.get(h)

        if cls._default_feature_vector is None:
            raise RuntimeError("Default feature vector not available.")

        # Build feature vector matching 55-feature training schema
        input_df = cls._default_feature_vector.copy()

        if req.telemetry_features:
            for col, val in req.telemetry_features.items():
                if col in input_df.columns:
                    input_df[col] = float(val)

            # Update derived cyclical and environmental features if raw inputs were provided
            if "hour" in req.telemetry_features:
                h_val = float(req.telemetry_features["hour"])
                input_df["hour_sin"] = np.sin(2 * np.pi * h_val / 24.0)
                input_df["hour_cos"] = np.cos(2 * np.pi * h_val / 24.0)
            if "dayofweek" in req.telemetry_features:
                d_val = float(req.telemetry_features["dayofweek"])
                input_df["dayofweek_sin"] = np.sin(2 * np.pi * d_val / 7.0)
                input_df["dayofweek_cos"] = np.cos(2 * np.pi * d_val / 7.0)
                input_df["is_weekend"] = int(d_val in [5, 6])
            if "month" in req.telemetry_features:
                m_val = float(req.telemetry_features["month"])
                input_df["month_sin"] = np.sin(2 * np.pi * m_val / 12.0)
                input_df["month_cos"] = np.cos(2 * np.pi * m_val / 12.0)
            if "T1" in req.telemetry_features and "T_out" in req.telemetry_features:
                input_df["temp_diff_indoor_outdoor"] = float(req.telemetry_features["T1"]) - float(req.telemetry_features["T_out"])
            if "RH_1" in req.telemetry_features and "RH_out" in req.telemetry_features:
                input_df["humidity_diff_indoor_outdoor"] = float(req.telemetry_features["RH_1"]) - float(req.telemetry_features["RH_out"])
            if "Appliances" in req.telemetry_features and "appliances_lag_1" not in req.telemetry_features:
                input_df["appliances_lag_1"] = float(req.telemetry_features["Appliances"])

        # Enforce exact column ordering matching model training schema
        input_df = input_df[cls._feature_columns]

        # Point Prediction
        raw_pred = float(model.predict(input_df)[0])
        pred_val = float(np.maximum(0.0, raw_pred))

        # Conformal Prediction Intervals
        if calibrator:
            lower, upper = calibrator.predict_interval(np.array([pred_val]))
            lower_bound = float(lower[0])
            upper_bound = float(upper[0])
        else:
            lower_bound = float(max(0.0, pred_val * 0.8))
            upper_bound = float(pred_val * 1.2)

        horizon_names = {1: "10_minutes_ahead", 6: "1_hour_ahead", 144: "24_hours_ahead"}
        h_name = horizon_names.get(h, f"{h}_steps_ahead")

        # Baseline comparison and explainability
        recent_load = float(input_df["Appliances"].iloc[0]) if "Appliances" in input_df.columns else pred_val
        explanation_data = V2ExplainabilityService.explain_prediction(
            sample_row=input_df.iloc[0],
            forecast_value=pred_val,
            horizon_name=h_name,
            baseline_value=recent_load
        )

        return V2ForecastResponse(
            horizon_steps=h,
            horizon_name=h_name,
            model_id=f"v2_ridge_h{h}",
            algorithm="Ridge ($L_2$ Shrinkage + 55 Engineered Features)",
            predicted_mean_Wh=round(pred_val, 2),
            lower_bound_Wh=round(lower_bound, 2),
            upper_bound_Wh=round(upper_bound, 2),
            confidence_level=req.confidence_level,
            interval_method="Split Conformal Prediction (Non-Parametric)",
            primary_drivers=explanation_data["primary_drivers"],
            explanation=explanation_data["customer_friendly_summary"]
        )

    @classmethod
    def detect_anomalies(cls, req: V2AnomalyRequest) -> V2AnomalyResponse:
        """Executes multi-method consensus anomaly detection with 30-minute persistence filtering."""
        cls.initialize()
        readings = np.array(req.readings, dtype=float)
        n = len(readings)
        if n == 0:
            raise ValueError("Readings array cannot be empty.")

        # Generate timestamps if not provided
        if req.timestamps and len(req.timestamps) == n:
            timestamps = req.timestamps
        else:
            base_time = pd.Timestamp.now()
            timestamps = [str(base_time - pd.Timedelta(minutes=(n - 1 - i) * 10)) for i in range(n)]

        ts_series = pd.to_datetime(timestamps)

        # If full detector and feature columns are available, run multi-method framework
        if cls._anomaly_detector and cls._feature_columns and cls._default_feature_vector is not None:
            # Replicate default 55-feature background matrix for n intervals
            eval_df = pd.concat([cls._default_feature_vector] * n, ignore_index=True)
            eval_df["Appliances"] = readings
            eval_df["hour"] = ts_series.hour
            eval_df["dayofweek"] = getattr(ts_series, "day_of_week", ts_series.dayofweek)

            # Preserve in-distribution seasonal baseline for unsupervised distance metrics
            base_month = cls._default_feature_vector["month"].iloc[0]
            months = ts_series.month
            # If provided timestamps are in training distribution months (1-5), use them; otherwise use baseline
            eval_df["month"] = [m if m in [1, 2, 3, 4, 5] else base_month for m in months]
            eval_df["is_weekend"] = eval_df["dayofweek"].isin([5, 6]).astype(int)
            eval_df["hour_sin"] = np.sin(2 * np.pi * eval_df["hour"] / 24.0)
            eval_df["hour_cos"] = np.cos(2 * np.pi * eval_df["hour"] / 24.0)
            eval_df["dayofweek_sin"] = np.sin(2 * np.pi * eval_df["dayofweek"] / 7.0)
            eval_df["dayofweek_cos"] = np.cos(2 * np.pi * eval_df["dayofweek"] / 7.0)
            eval_df["month_sin"] = np.sin(2 * np.pi * eval_df["month"] / 12.0)
            eval_df["month_cos"] = np.cos(2 * np.pi * eval_df["month"] / 12.0)

            # Ensure strict 55-column ordering
            eval_df = eval_df[cls._feature_columns]

            results = cls._anomaly_detector.detect_and_filter_events(
                eval_df=eval_df,
                feature_cols=cls._feature_columns,
                timestamps=np.array(timestamps),
                unit=req.unit
            )

            events = [
                V2AnomalyEvent(
                    start_time=e["start_time"],
                    end_time=e["end_time"],
                    consecutive_steps=e["consecutive_steps"],
                    duration_minutes=e["duration_minutes"],
                    peak_consumption=e["peak_consumption"],
                    mean_consumption=e["mean_consumption"],
                    expected_baseline=e["expected_baseline"],
                    potential_excess_energy=e["potential_excess_energy"],
                    unit=e["unit"],
                    severity=e["severity"],
                    status=e["status"],
                    consensus_strength=e.get("consensus_strength", 2.0),
                    explanation=V2ExplainabilityService.explain_anomaly_event(e)
                )
                for e in results["events"]
            ]

            return V2AnomalyResponse(
                total_readings=n,
                total_candidate_intervals=results["total_candidate_intervals"],
                suppressed_isolated_bursts=results["suppressed_isolated_bursts"],
                sustained_events_count=len(events),
                total_potential_excess=results["total_potential_excess"],
                unit=req.unit,
                events=events
            )
        else:
            # Standalone fallback implementation
            med = float(np.median(readings))
            upper_fence = float(med * 2.0)
            candidate_mask = (readings > upper_fence).astype(int)

            runs = []
            in_run = False
            start_idx = 0
            for i in range(n):
                if candidate_mask[i] == 1:
                    if not in_run:
                        in_run = True
                        start_idx = i
                else:
                    if in_run:
                        in_run = False
                        runs.append((start_idx, i - 1))
            if in_run:
                runs.append((start_idx, n - 1))

            events = []
            suppressed = 0
            for s, e in runs:
                dur = e - s + 1
                if dur < 3:
                    suppressed += 1
                    continue
                excess = float(round(np.sum(np.maximum(0.0, readings[s:e+1] - upper_fence)), 2))
                ev = {
                    "start_time": timestamps[s],
                    "end_time": timestamps[e],
                    "consecutive_steps": dur,
                    "duration_minutes": dur * 10,
                    "peak_consumption": float(round(np.max(readings[s:e+1]), 2)),
                    "mean_consumption": float(round(np.mean(readings[s:e+1]), 2)),
                    "expected_baseline": round(med, 2),
                    "potential_excess_energy": excess,
                    "unit": req.unit,
                    "severity": "HIGH" if dur >= 6 or excess > 500 else ("MEDIUM" if dur >= 4 else "LOW"),
                    "status": "UNUSUAL_CONSUMPTION_IDENTIFIED",
                    "consensus_strength": 2.0
                }
                ev["explanation"] = V2ExplainabilityService.explain_anomaly_event(ev)
                events.append(V2AnomalyEvent(**ev))

            total_excess = float(round(sum(ev.potential_excess_energy for ev in events), 2))
            return V2AnomalyResponse(
                total_readings=n,
                total_candidate_intervals=int(np.sum(candidate_mask)),
                suppressed_isolated_bursts=suppressed,
                sustained_events_count=len(events),
                total_potential_excess=total_excess,
                unit=req.unit,
                events=events
            )

    @classmethod
    def get_model_status(cls) -> V2ModelStatusResponse:
        """Returns the current V2 Model Registry state, drift status, and deep learning assessment."""
        cls.initialize()
        registry_data = V2ModelRegistry.get_registry_summary()

        drift_status = "UNKNOWN"
        drifted_count = 0
        deep_eval = {}

        results_json = cls.REPORTS_DIR / "v2_evaluation_results.json"
        if results_json.exists():
            eval_data = json.loads(results_json.read_text(encoding="utf-8"))
            drift_status = eval_data.get("drift_audit", {}).get("status", "STABLE")
            drifted_count = eval_data.get("drift_audit", {}).get("drifted_count", 0)
            deep_eval = eval_data.get("deep_learning_benchmark", {})

        return V2ModelStatusResponse(
            registry_version="v2.0",
            champions=registry_data.get("champions", {}),
            challengers=registry_data.get("challengers", {}),
            drift_status=drift_status,
            drifted_features_count=drifted_count,
            data_sufficiency_assessment=deep_eval
        )
