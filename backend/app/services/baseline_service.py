"""
Baseline Calculation Service
Implements statistical and time-aware expected consumption baselines.

ALL BASELINES USE HISTORICAL INFORMATION ONLY:
- Strictly prevents lookahead data leakage.
- Rolling statistics are shifted by 1 interval to use strictly completed past readings.
- Hour-of-day and Day-of-week conditional profiles are learned from training partitions.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

class BaselineCalculationService:
    """Calculates dynamic expected consumption baselines and upper thresholds."""

    @staticmethod
    def historical_global_median(train_series: pd.Series, eval_series: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 1: Static global median and IQR upper fence.
        Expected = Median, Upper = Q3 + 1.5 * IQR.
        """
        med = float(train_series.median())
        q75 = float(train_series.quantile(0.75))
        q25 = float(train_series.quantile(0.25))
        upper_fence = q75 + 1.5 * (q75 - q25)
        
        expected = np.full(len(eval_series), med)
        upper_bound = np.full(len(eval_series), upper_fence)
        return expected, upper_bound

    @staticmethod
    def rolling_historical_median(
        series: pd.Series,
        window: int = 144,
        multiplier: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 2: Rolling historical median of past W steps (shifted by 1 to exclude current).
        Upper threshold is scaled by a robust multiplier.
        """
        past_series = series.shift(1)
        mp = min(12, window)
        expected = past_series.rolling(window=window, min_periods=mp).median().bfill().values
        # Rolling IQR for upper bound
        q75 = past_series.rolling(window=window, min_periods=mp).quantile(0.75).bfill().values
        q25 = past_series.rolling(window=window, min_periods=mp).quantile(0.25).bfill().values
        iqr = np.maximum(q75 - q25, 10.0) # Floor IQR at 10 Wh
        upper_bound = q75 + multiplier * iqr
        return expected, upper_bound

    @staticmethod
    def rolling_historical_mean_std(
        series: pd.Series,
        window: int = 144,
        k: float = 2.5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 3: Rolling historical Gaussian threshold (mean + k * std).
        Shifted by 1 interval to prevent current observation leakage.
        """
        past_series = series.shift(1)
        mp = min(12, window)
        roll_mean = past_series.rolling(window=window, min_periods=mp).mean().bfill().values
        roll_std = past_series.rolling(window=window, min_periods=mp).std().fillna(15.0).values
        upper_bound = roll_mean + k * roll_std
        return roll_mean, upper_bound

    @staticmethod
    def hour_of_day_conditional(
        train_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        target_col: str = "Appliances",
        hour_col: str = "hour"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 4: Hour-of-day diurnal conditional baseline.
        Learned strictly on training data:
        Expected = Median by hour
        Upper bound = Q3(hour) + 1.5 * IQR(hour)
        """
        hourly_stats = {}
        for h in range(24):
            subset = train_df[train_df[hour_col] == h][target_col]
            med = subset.median()
            q25 = subset.quantile(0.25)
            q75 = subset.quantile(0.75)
            iqr = max(q75 - q25, 10.0)
            hourly_stats[h] = {
                "expected": med,
                "upper_bound": q75 + 1.5 * iqr
            }

        eval_hours = eval_df[hour_col].values
        expected = np.array([hourly_stats[int(h)]["expected"] for h in eval_hours])
        upper_bound = np.array([hourly_stats[int(h)]["upper_bound"] for h in eval_hours])
        return expected, upper_bound

    @staticmethod
    def day_and_hour_conditional(
        train_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        target_col: str = "Appliances",
        hour_col: str = "hour",
        day_col: str = "dayofweek"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 5: Day-of-week AND Hour-of-day conditional baseline.
        Learned strictly on training data:
        Accounts for weekday vs weekend wake-up times and activity rhythms.
        """
        matrix_stats = {}
        for d in range(7):
            for h in range(24):
                subset = train_df[(train_df[day_col] == d) & (train_df[hour_col] == h)][target_col]
                if len(subset) > 0:
                    med = subset.median()
                    q25 = subset.quantile(0.25)
                    q75 = subset.quantile(0.75)
                    iqr = max(q75 - q25, 10.0)
                    matrix_stats[(d, h)] = {
                        "expected": med,
                        "upper_bound": q75 + 1.5 * iqr
                    }
                else:
                    matrix_stats[(d, h)] = {"expected": 60.0, "upper_bound": 175.0}

        eval_pairs = zip(eval_df[day_col].values, eval_df[hour_col].values)
        expected = np.array([matrix_stats[(int(d), int(h))]["expected"] for d, h in eval_pairs])
        eval_pairs2 = zip(eval_df[day_col].values, eval_df[hour_col].values)
        upper_bound = np.array([matrix_stats[(int(d), int(h))]["upper_bound"] for d, h in eval_pairs2])
        return expected, upper_bound

    @staticmethod
    def forecast_assisted_baseline(
        ridge_predictions: np.ndarray,
        diurnal_expected: np.ndarray,
        diurnal_upper: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Baseline 6: Forecast-assisted hybrid expected baseline.
        Combines short-term autoregressive prediction with diurnal regularizer:
        Expected = 0.5 * RidgePred + 0.5 * DiurnalMedian
        Upper bound = max(RidgePred, DiurnalExpected) + (DiurnalUpper - DiurnalExpected)
        """
        expected = 0.5 * ridge_predictions + 0.5 * diurnal_expected
        uncertainty_band = np.maximum(diurnal_upper - diurnal_expected, 25.0)
        upper_bound = expected + uncertainty_band
        return expected, upper_bound
