"""
WattSense AI™ — Machine Learning V2 Advanced Feature Engineering Pipeline
Constructs multivariate, leakage-free temporal, rolling, lag, and environmental features.
"""
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd


class V2FeatureEngineeringPipeline:
    """Advanced feature engineering for multi-horizon electricity consumption forecasting."""

    EXCLUDED_COLS = {
        "date", "timestamp", "rv1", "rv2", "is_outlier_high", "Appliances"
    }

    @classmethod
    def generate_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms raw energy time series into feature-engineered representation.
        Ensures strict chronological causality: all rolling/lag operations use .shift(1).
        """
        df = df.copy()

        # 1. Timestamps
        if "timestamp" not in df.columns:
            date_str = df["date"].astype(str).str.replace(r"(\d{4}-\d{2}-\d{2})(\d{2}:)", r"\1 \2", regex=True)
            df["timestamp"] = pd.to_datetime(date_str, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        target = pd.to_numeric(df["Appliances"], errors="coerce")
        df["Appliances"] = target

        # 2. Temporal & Cyclical Features
        df["hour"] = df["timestamp"].dt.hour
        df["dayofweek"] = df["timestamp"].dt.dayofweek
        df["month"] = df["timestamp"].dt.month
        df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
        df["dayofweek_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7.0)
        df["dayofweek_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7.0)
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)

        # 3. Lag Features (Strictly past values)
        # 1 step = 10 min, 6 steps = 1 hr, 12 steps = 2 hr, 24 steps = 4 hr, 144 steps = 24 hr
        lags = [1, 2, 3, 6, 12, 24, 144]
        for lag in lags:
            df[f"appliances_lag_{lag}"] = target.shift(lag)

        # 4. Rolling Statistics (Shifted by 1 interval to eliminate lookahead leakage)
        past_target = target.shift(1)

        # Rolling Means
        df["appliances_roll_mean_6"] = past_target.rolling(window=6, min_periods=1).mean()
        df["appliances_roll_mean_12"] = past_target.rolling(window=12, min_periods=1).mean()
        df["appliances_roll_mean_144"] = past_target.rolling(window=144, min_periods=6).mean()

        # Rolling Medians
        df["appliances_roll_median_6"] = past_target.rolling(window=6, min_periods=1).median()
        df["appliances_roll_median_144"] = past_target.rolling(window=144, min_periods=6).median()

        # Rolling Standard Deviations
        df["appliances_roll_std_6"] = past_target.rolling(window=6, min_periods=1).std().fillna(0.0)
        df["appliances_roll_std_144"] = past_target.rolling(window=144, min_periods=6).std().fillna(15.0)

        # Rolling Quantiles (10th and 90th percentiles over past 24 hours)
        df["appliances_roll_p10_144"] = past_target.rolling(window=144, min_periods=6).quantile(0.10)
        df["appliances_roll_p90_144"] = past_target.rolling(window=144, min_periods=6).quantile(0.90)

        # Exponentially Weighted Moving Average (EWMA, span=12 -> half-life of 2 hours)
        df["appliances_ewma_12"] = past_target.ewm(span=12, adjust=False).mean()

        # 5. Environmental Delta Features
        if "T1" in df.columns and "T_out" in df.columns:
            df["temp_diff_indoor_outdoor"] = df["T1"] - df["T_out"]
        if "RH_1" in df.columns and "RH_out" in df.columns:
            df["humidity_diff_indoor_outdoor"] = df["RH_1"] - df["RH_out"]

        # Drop rows where the 144-step lag is NaN
        clean_df = df.dropna().reset_index(drop=True)
        return clean_df

    @classmethod
    def get_feature_column_names(cls, df: pd.DataFrame) -> List[str]:
        """Returns sorted list of predictive feature column names."""
        cols = [c for c in df.select_dtypes(include="number").columns if c not in cls.EXCLUDED_COLS]
        if "Appliances" not in cols:
            cols.append("Appliances")
        return sorted(cols)

    @classmethod
    def prepare_dataset_for_horizon(
        cls,
        df: pd.DataFrame,
        h: int
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """
        Creates feature matrix X, future target y_{t+h}, and aligned DataFrame.
        """
        feature_cols = cls.get_feature_column_names(df)
        df_work = df.copy()
        df_work[f"target_h{h}"] = df_work["Appliances"].shift(-h)
        df_work[f"target_hour_h{h}"] = df_work["hour"].shift(-h)

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
        """Chronological 70% Train / 15% Validation / 15% Test separation."""
        n = len(X)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        n_test = n - n_train - n_val

        return {
            "X_train": X.iloc[:n_train].copy(),
            "y_train": y.iloc[:n_train].copy(),
            "df_train": valid_df.iloc[:n_train].copy(),

            "X_val": X.iloc[n_train : n_train + n_val].copy(),
            "y_val": y.iloc[n_train : n_train + n_val].copy(),
            "df_val": valid_df.iloc[n_train : n_train + n_val].copy(),

            "X_test": X.iloc[n_train + n_val :].copy(),
            "y_test": y.iloc[n_train + n_val :].copy(),
            "df_test": valid_df.iloc[n_train + n_val :].copy(),

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
