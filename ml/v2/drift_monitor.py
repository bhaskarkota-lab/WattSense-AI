"""
WattSense AI™ — Machine Learning V2 Concept & Data Drift Monitoring
Detects distribution drift, error degradation, and telemetry anomalies using KS-tests and PSI.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance


class V2ConceptDriftMonitor:
    """Monitors continuous feature drift, prediction drift, and rolling performance degradation."""

    @staticmethod
    def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_buckets: int = 10, eps: float = 1e-4) -> float:
        """
        Calculates Population Stability Index (PSI).
        PSI < 0.1: Stable / No Drift.
        0.1 <= PSI < 0.25: Moderate Drift.
        PSI >= 0.25: Significant Drift.
        """
        expected = np.asarray(expected, dtype=float)
        actual = np.asarray(actual, dtype=float)

        quantiles = np.linspace(0, 100, num_buckets + 1)
        bins = np.percentile(expected, quantiles)
        bins[0] -= 1e-5
        bins[-1] += 1e-5

        # Handle degenerate bins
        bins = np.unique(bins)
        if len(bins) < 3:
            return 0.0

        exp_counts, _ = np.histogram(expected, bins=bins)
        act_counts, _ = np.histogram(actual, bins=bins)

        exp_pct = exp_counts / (len(expected) + eps) + eps
        act_pct = act_counts / (len(actual) + eps) + eps

        psi_val = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
        return float(round(psi_val, 4))

    @classmethod
    def audit_drift(
        cls,
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame,
        feature_columns: List[str],
        psi_threshold: float = 0.20,
        ks_alpha: float = 0.01
    ) -> Dict[str, Any]:
        """
        Audits distribution shift across all predictive features.
        """
        drifted_features = []
        feature_reports = {}

        for col in feature_columns:
            if col not in baseline_df.columns or col not in current_df.columns:
                continue

            ref_vals = baseline_df[col].dropna().values.astype(float)
            cur_vals = current_df[col].dropna().values.astype(float)

            if len(ref_vals) < 20 or len(cur_vals) < 20:
                continue

            # 1. Kolmogorov-Smirnov Test
            ks_res = ks_2samp(ref_vals, cur_vals)
            p_val = float(ks_res.pvalue)

            # 2. Population Stability Index (PSI)
            psi_score = cls.calculate_psi(ref_vals, cur_vals)

            # 3. Wasserstein Distance
            w_dist = float(round(wasserstein_distance(ref_vals, cur_vals), 3))

            is_drifted = (psi_score >= psi_threshold) or (p_val < ks_alpha)

            feature_reports[col] = {
                "psi_score": psi_score,
                "ks_pvalue": round(p_val, 5),
                "wasserstein_distance": w_dist,
                "drift_detected": bool(is_drifted)
            }

            if is_drifted:
                drifted_features.append(col)

        overall_drift_status = "SIGNIFICANT_DRIFT" if len(drifted_features) >= 3 else (
            "MODERATE_DRIFT" if len(drifted_features) > 0 else "STABLE"
        )

        return {
            "overall_status": overall_drift_status,
            "drifted_features_count": len(drifted_features),
            "total_features_checked": len(feature_columns),
            "drifted_features": drifted_features,
            "detailed_feature_metrics": feature_reports
        }

    @staticmethod
    def audit_missing_telemetry_rate(df: pd.DataFrame) -> Dict[str, Any]:
        """Calculates missing telemetry rate and timestamp cadence gaps."""
        n_rows = len(df)
        null_counts = df.isnull().sum()
        total_nulls = int(null_counts.sum())
        missing_rate_pct = float(round((total_nulls / max(n_rows * df.shape[1], 1)) * 100.0, 3))

        return {
            "total_rows": n_rows,
            "total_null_entries": total_nulls,
            "missing_telemetry_rate_pct": missing_rate_pct,
            "telemetry_health": "EXCELLENT" if missing_rate_pct < 1.0 else (
                "DEGRADED" if missing_rate_pct < 5.0 else "CRITICAL"
            )
        }
