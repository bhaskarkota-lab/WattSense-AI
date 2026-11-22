"""
Consumption Forecasting Service & Model Pipelines
Implements multi-horizon time-series regression for electricity consumption forecasting.

HORIZONS EVALUATED:
- h=1: 10 minutes ahead (1 step)
- h=6: 1 hour ahead (6 steps)
- h=144: 24 hours ahead (144 steps)

RESEARCH INTEGRITY & METHODOLOGICAL RIGOR:
- Chronological 70% Train / 15% Validation / 15% Test separation.
- Zero future lookahead: lag and rolling features shifted to exclude future data.
- Baselines evaluated first (Last-Observation, Seasonal Naive, Rolling Avg, Time-of-Day).
- Model selection strictly driven by Validation performance.
- Test set untouched until final evaluation.
- Dataset represents single household (UCI Appliances); not claimed as multi-customer.
"""
from pathlib import Path
import json
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import (
    RandomForestRegressor,
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.app.core.config import settings
from backend.app.core.logging import logger

class ForecastingMetrics:
    """Standardized time-series forecasting evaluation metrics."""

    @staticmethod
    def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-5) -> float:
        """Symmetric Mean Absolute Percentage Error (sMAPE) bounded between 0% and 200%."""
        denom = np.abs(y_true) + np.abs(y_pred) + eps
        return float(np.mean(200.0 * np.abs(y_true - y_pred) / denom))

    @staticmethod
    def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1.0) -> float:
        """Mean Absolute Percentage Error (MAPE) with epsilon thresholding to prevent zero division."""
        denom = np.maximum(np.abs(y_true), eps)
        return float(np.mean(100.0 * np.abs(y_true - y_pred) / denom))

    @classmethod
    def calculate_all(cls, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Computes MAE, RMSE, R², sMAPE, and MAPE."""
        mae = float(mean_absolute_error(y_true, y_pred))
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_true, y_pred))
        s_mape = cls.smape(y_true, y_pred)
        c_mape = cls.mape(y_true, y_pred)
        return {
            "MAE_Wh": round(mae, 2),
            "RMSE_Wh": round(rmse, 2),
            "R2": round(r2, 4),
            "sMAPE_pct": round(s_mape, 2),
            "MAPE_pct": round(c_mape, 2)
        }


class BaselineForecasters:
    """
    Mandatory baseline benchmarks:
    1. Last-observation (Persistence): y_{t+h} = y_t
    2. Seasonal Naive: y_{t+h} = y_{t+h-144} (same time previous day)
    3. Historical Rolling Average: y_{t+h} = mean(past 24h)
    4. Time-of-Day Average: y_{t+h} = mean_train(hour)
    """

    @staticmethod
    def persistence(df: pd.DataFrame, h: int) -> np.ndarray:
        """Predicts consumption at t+h using most recent reading at time t."""
        return df["Appliances"].values

    @staticmethod
    def seasonal_naive_24h(df: pd.DataFrame, h: int) -> np.ndarray:
        """
        Predicts consumption at t+h using same time from previous day (t+h-144).
        Since h <= 144, t+h-144 <= t, which is strictly known historical data.
        """
        shift_back = 144 - h
        return df["Appliances"].shift(shift_back).bfill().values

    @staticmethod
    def rolling_average_24h(df: pd.DataFrame, h: int) -> np.ndarray:
        """Predicts consumption at t+h using the 24-hour moving average at time t."""
        return df["Appliances"].rolling(window=144, min_periods=1).mean().values

    @staticmethod
    def time_of_day_baseline(
        train_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        target_hours: np.ndarray
    ) -> np.ndarray:
        """
        Predicts consumption using historical average by target hour of day,
        learned strictly from the training partition to prevent data leakage.
        """
        hourly_means = train_df.groupby("hour")["Appliances"].mean().to_dict()
        overall_mean = float(train_df["Appliances"].mean())
        return np.array([hourly_means.get(int(hr), overall_mean) for hr in target_hours])


class ForecastingService:
    """End-to-end forecasting pipeline: preparation, training, selection, and inference."""

    EXCLUDED_COLS = {
        "date", "timestamp", "rv1", "rv2", "is_outlier_high",
        "Appliances" # Target is constructed per horizon
    }

    @classmethod
    def get_feature_columns(cls, df: pd.DataFrame) -> List[str]:
        """Returns the list of valid predictive features."""
        # Include current consumption as an explicit predictor for future t+h
        cols = [c for c in df.select_dtypes(include="number").columns if c not in cls.EXCLUDED_COLS]
        if "Appliances" not in cols:
            cols.append("Appliances") # Known at forecast origin t
        return sorted(cols)

    @classmethod
    def prepare_horizon_data(
        cls,
        df: pd.DataFrame,
        h: int
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """
        Constructs the target y_{t+h} = Appliances_{t+h} shifted into the future.
        Returns (X, y, df_aligned).
        """
        feature_cols = cls.get_feature_columns(df)
        df_work = df.copy()
        df_work[f"target_h{h}"] = df_work["Appliances"].shift(-h)

        # Retain target hour for time-of-day baseline
        df_work[f"target_hour_h{h}"] = df_work["hour"].shift(-h)

        # Drop rows where future target is undefined (the final h rows)
        valid = df_work.dropna(subset=[f"target_h{h}", f"target_hour_h{h}"]).reset_index(drop=True)
        X = valid[feature_cols]
        y = valid[f"target_h{h}"]
        return X, y, valid

    @staticmethod
    def chronological_split(
        X: pd.DataFrame,
        y: pd.Series,
        valid_df: pd.DataFrame,
        train_frac: float = 0.70,
        val_frac: float = 0.15
    ) -> Dict[str, Any]:
        """
        Partitions time-series chronologically into:
        - Train: earliest 70%
        - Validation: next 15%
        - Test: final 15%
        """
        n = len(X)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        n_test = n - n_train - n_val

        splits = {
            "X_train": X.iloc[:n_train],
            "y_train": y.iloc[:n_train],
            "df_train": valid_df.iloc[:n_train],

            "X_val": X.iloc[n_train : n_train + n_val],
            "y_val": y.iloc[n_train : n_train + n_val],
            "df_val": valid_df.iloc[n_train : n_train + n_val],

            "X_test": X.iloc[n_train + n_val :],
            "y_test": y.iloc[n_train + n_val :],
            "df_test": valid_df.iloc[n_train + n_val :],

            "split_indices": {
                "train_range": (0, n_train - 1),
                "val_range": (n_train, n_train + n_val - 1),
                "test_range": (n_train + n_val, n - 1),
                "n_train": n_train,
                "n_val": n_val,
                "n_test": n_test,
                "total": n
            }
        }
        return splits

    @staticmethod
    def get_candidate_models() -> Dict[str, Any]:
        """Returns the dictionary of regression algorithms evaluated."""
        return {
            "LinearRegression": Pipeline([
                ("scaler", StandardScaler()),
                ("regressor", LinearRegression())
            ]),
            "RidgeRegression": Pipeline([
                ("scaler", StandardScaler()),
                ("regressor", Ridge(alpha=10.0, random_state=42))
            ]),
            "RandomForestRegressor": RandomForestRegressor(
                n_estimators=100, max_depth=12, min_samples_leaf=3,
                random_state=42, n_jobs=-1
            ),
            "ExtraTreesRegressor": ExtraTreesRegressor(
                n_estimators=100, max_depth=12, min_samples_leaf=3,
                random_state=42, n_jobs=-1
            ),
            "HistGradientBoostingRegressor": HistGradientBoostingRegressor(
                max_iter=150, learning_rate=0.08, max_depth=8,
                random_state=42
            )
        }
