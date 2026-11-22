"""
WattSense AI™ — Machine Learning V2 Multi-Method Anomaly Detection Engine
Combines Isolation Forest, Local Outlier Factor (LOF), Robust Statistical Z-score/MAD,
Conditional Diurnal Quantiles, and Change Point Detection with 30-minute Persistence Filtering.
"""
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler


class V2MultiMethodAnomalyDetector:
    """Multi-method consensus anomaly detection engine with persistence filtering."""

    def __init__(self, contamination: float = 0.04, min_consecutive_intervals: int = 3, interval_minutes: int = 10):
        self.contamination = contamination
        self.min_consecutive_intervals = min_consecutive_intervals
        self.interval_minutes = interval_minutes

        self.iso_forest = IsolationForest(
            n_estimators=150,
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        self.lof = LocalOutlierFactor(
            n_neighbors=25,
            contamination=contamination,
            novelty=True,
            n_jobs=-1
        )
        self.scaler = RobustScaler()
        self.is_fitted = False

        # Diurnal conditional profile learned on training partition
        self.diurnal_stats: Dict[Tuple[int, int], Dict[str, float]] = {}

    def fit(self, train_df: pd.DataFrame, feature_cols: List[str]):
        """Fits unsupervised detectors and computes historical diurnal profiles."""
        X = train_df[feature_cols].copy().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        X_scaled = self.scaler.fit_transform(X)

        self.iso_forest.fit(X_scaled)
        self.lof.fit(X_scaled)

        # Diurnal Day x Hour conditional statistics
        for (day, hour), group in train_df.groupby(["dayofweek", "hour"]):
            vals = group["Appliances"].values
            med = float(np.median(vals))
            q75 = float(np.percentile(vals, 75))
            q25 = float(np.percentile(vals, 25))
            iqr = max(q75 - q25, 10.0)
            q95 = float(np.percentile(vals, 95))
            self.diurnal_stats[(int(day), int(hour))] = {
                "median": med,
                "q75": q75,
                "q25": q25,
                "iqr": iqr,
                "upper_fence": q75 + 1.5 * iqr,
                "q95": q95
            }
        self.is_fitted = True

    def detect_signals(self, eval_df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, np.ndarray]:
        """
        Computes 5 complementary detection signals:
        1. Isolation Forest signal (binary 0/1)
        2. Local Outlier Factor signal (binary 0/1)
        3. Robust Statistical Z-score/MAD signal (binary 0/1)
        4. Conditional Diurnal Upper Fence signal (binary 0/1)
        5. Change Point / Sudden Deviation signal (binary 0/1)
        """
        if not self.is_fitted:
            raise RuntimeError("Anomaly engine must be fitted before detecting signals.")

        X = eval_df[feature_cols].copy().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        X_scaled = self.scaler.transform(X)
        actuals = eval_df["Appliances"].values.astype(float)
        n = len(actuals)

        # Signal 1: Isolation Forest
        iso_pred = self.iso_forest.predict(X_scaled)
        sig_iso = (iso_pred == -1).astype(int)

        # Signal 2: Local Outlier Factor
        lof_pred = self.lof.predict(X_scaled)
        sig_lof = (lof_pred == -1).astype(int)

        # Signal 3: Robust Statistical Z-score via Median Absolute Deviation (MAD)
        med = np.median(actuals)
        mad = np.median(np.abs(actuals - med))
        mad = max(mad, 5.0)
        robust_z = 0.6745 * np.abs(actuals - med) / mad
        sig_robust_z = (robust_z > 3.0).astype(int)

        # Signal 4: Diurnal Conditional Upper Fence
        sig_diurnal = np.zeros(n, dtype=int)
        expected_baselines = np.zeros(n, dtype=float)
        upper_thresholds = np.zeros(n, dtype=float)

        days = eval_df["dayofweek"].values
        hours = eval_df["hour"].values

        global_fallback = {"median": med, "upper_fence": med + 2.0 * mad}

        for i in range(n):
            key = (int(days[i]), int(hours[i]))
            stats = self.diurnal_stats.get(key, global_fallback)
            expected_baselines[i] = stats["median"]
            upper_thresholds[i] = stats["upper_fence"]
            if actuals[i] > stats["upper_fence"]:
                sig_diurnal[i] = 1

        # Signal 5: Sequential Change Point / Moving Deviation
        sig_changepoint = np.zeros(n, dtype=int)
        roll_mean_past = pd.Series(actuals).shift(1).rolling(6, min_periods=1).mean().bfill().values
        roll_std_past = pd.Series(actuals).shift(1).rolling(6, min_periods=1).std().fillna(15.0).values
        sudden_dev = (actuals - roll_mean_past) / np.maximum(roll_std_past, 5.0)
        sig_changepoint = (sudden_dev > 2.5).astype(int)

        # Consensus Voting: interval flagged as candidate anomaly if >= 2 independent detectors agree
        consensus_score = sig_iso + sig_lof + sig_robust_z + sig_diurnal + sig_changepoint
        candidate_mask = (consensus_score >= 2).astype(int)

        return {
            "sig_isolation_forest": sig_iso,
            "sig_local_outlier_factor": sig_lof,
            "sig_robust_z": sig_robust_z,
            "sig_diurnal_fence": sig_diurnal,
            "sig_changepoint": sig_changepoint,
            "consensus_score": consensus_score,
            "candidate_mask": candidate_mask,
            "expected_baselines": expected_baselines,
            "upper_thresholds": upper_thresholds,
            "actuals": actuals
        }

    def detect_and_filter_events(
        self,
        eval_df: pd.DataFrame,
        feature_cols: List[str],
        timestamps: np.ndarray,
        unit: str = "Wh"
    ) -> Dict[str, Any]:
        """
        Executes multi-method anomaly detection followed by 30-minute persistence filtering.
        """
        signals = self.detect_signals(eval_df, feature_cols)
        candidate_mask = signals["candidate_mask"]
        actuals = signals["actuals"]
        expected = signals["expected_baselines"]
        upper_bound = signals["upper_thresholds"]

        n = len(actuals)
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

        sustained_mask = np.zeros(n, dtype=int)
        events = []
        suppressed_count = 0

        for start, end in runs:
            duration_steps = end - start + 1
            if duration_steps < self.min_consecutive_intervals:
                suppressed_count += 1
                continue

            # Sustained event meeting persistence criteria
            sustained_mask[start : end + 1] = 1
            run_actual = actuals[start : end + 1]
            run_upper = upper_bound[start : end + 1]
            run_expected = expected[start : end + 1]
            run_excess = np.maximum(0.0, run_actual - run_upper)

            total_excess = float(round(np.sum(run_excess), 2))
            peak_val = float(round(np.max(run_actual), 2))
            mean_val = float(round(np.mean(run_actual), 2))
            duration_min = duration_steps * self.interval_minutes

            if duration_steps >= 6 or total_excess > 500.0:
                severity = "HIGH"
            elif duration_steps >= 4 or total_excess > 250.0:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            events.append({
                "start_time": str(timestamps[start]),
                "end_time": str(timestamps[end]),
                "consecutive_steps": int(duration_steps),
                "duration_minutes": int(duration_min),
                "peak_consumption": peak_val,
                "mean_consumption": mean_val,
                "expected_baseline": float(round(np.mean(run_expected), 2)),
                "potential_excess_energy": total_excess,
                "unit": unit,
                "severity": severity,
                "status": "UNUSUAL_CONSUMPTION_IDENTIFIED",
                "consensus_strength": float(round(np.mean(signals["consensus_score"][start : end + 1]), 1))
            })

        total_potential_excess = float(round(sum(e["potential_excess_energy"] for e in events), 2))

        return {
            "total_candidate_intervals": int(np.sum(candidate_mask)),
            "suppressed_isolated_bursts": suppressed_count,
            "sustained_events_count": len(events),
            "total_potential_excess": total_potential_excess,
            "unit": unit,
            "events": events
        }
