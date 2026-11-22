"""
WattSense AI™ — Machine Learning V2 Standardized Evaluation Metrics
Implements comprehensive deterministic metrics for point and probabilistic time-series forecasting.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class V2ForecastingMetrics:
    """Standardized metrics for time-series forecasting point and interval predictions."""

    @staticmethod
    def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-5) -> float:
        """Symmetric Mean Absolute Percentage Error (sMAPE) bounded between 0% and 200%."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        denom = np.abs(y_true) + np.abs(y_pred) + eps
        return float(np.mean(200.0 * np.abs(y_true - y_pred) / denom))

    @staticmethod
    def wape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-5) -> float:
        """Weighted Absolute Percentage Error (WAPE = sum(|y - y_hat|) / sum(y))."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        total_actual = float(np.sum(np.abs(y_true))) + eps
        total_abs_err = float(np.sum(np.abs(y_true - y_pred)))
        return float((total_abs_err / total_actual) * 100.0)

    @staticmethod
    def forecast_bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Mean Forecast Error (Bias = mean(y_hat - y)). Positive means over-predicting."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        return float(np.mean(y_pred - y_true))

    @classmethod
    def calculate_point_metrics(cls, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculates MAE, RMSE, R², sMAPE, WAPE, and Forecast Bias."""
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        mae = float(mean_absolute_error(y_true, y_pred))
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_true, y_pred))
        s_mape = cls.smape(y_true, y_pred)
        c_wape = cls.wape(y_true, y_pred)
        bias = cls.forecast_bias(y_true, y_pred)

        return {
            "MAE_Wh": round(mae, 2),
            "RMSE_Wh": round(rmse, 2),
            "R2": round(r2, 4),
            "sMAPE_pct": round(s_mape, 2),
            "WAPE_pct": round(c_wape, 2),
            "forecast_bias_Wh": round(bias, 2),
        }

    @staticmethod
    def evaluate_prediction_intervals(
        y_true: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray
    ) -> Dict[str, float]:
        """
        Evaluates probabilistic forecasting prediction intervals:
        - PICP: Prediction Interval Coverage Probability (fraction of y in [lower, upper]).
        - MPIW: Mean Prediction Interval Width (mean(upper - lower)).
        """
        y_true = np.asarray(y_true, dtype=float)
        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)

        covered = ((y_true >= lower) & (y_true <= upper)).astype(float)
        picp = float(np.mean(covered) * 100.0)
        mpiw = float(np.mean(np.maximum(0.0, upper - lower)))

        return {
            "coverage_pct": round(picp, 2),
            "mean_interval_width_Wh": round(mpiw, 2),
        }
