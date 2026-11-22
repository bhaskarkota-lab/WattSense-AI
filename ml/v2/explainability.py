"""
WattSense AI™ — Machine Learning V2 Explainability Subsystem
Provides local feature attribution, global feature importances, and plain-language customer summaries.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


class V2ExplainabilityService:
    """Generates transparent, human-interpretable explanations for forecasts and detected anomalies."""

    @staticmethod
    def get_global_feature_importance(model: Any, feature_names: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
        """Extracts normalized global feature importances from tree-based or linear models."""
        importances = None
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "steps") and hasattr(model.steps[-1][1], "coef_"):
            importances = np.abs(model.steps[-1][1].coef_)

        if importances is None:
            return []

        importances = np.asarray(importances, dtype=float)
        total = np.sum(importances)
        if total > 0:
            norm_imp = (importances / total) * 100.0
        else:
            norm_imp = importances

        sorted_indices = np.argsort(norm_imp)[::-1][:top_n]
        return [
            {
                "feature": feature_names[i],
                "importance_pct": round(float(norm_imp[i]), 2)
            }
            for i in sorted_indices
        ]

    @staticmethod
    def explain_prediction(
        sample_row: pd.Series,
        forecast_value: float,
        horizon_name: str,
        baseline_value: float
    ) -> Dict[str, Any]:
        """
        Decomposes a forecast into key explanatory drivers and customer-friendly explanation.
        """
        recent_load = float(sample_row.get("Appliances", 0.0))
        hour = int(sample_row.get("hour", 12))
        is_weekend = bool(sample_row.get("is_weekend", 0))

        delta = forecast_value - baseline_value
        pct_diff = round((delta / max(baseline_value, 1.0)) * 100.0, 1)

        if abs(pct_diff) < 15.0:
            trend_desc = "in line with typical expectations"
        elif pct_diff > 0:
            trend_desc = f"{abs(pct_diff)}% above typical historical usage"
        else:
            trend_desc = f"{abs(pct_diff)}% below typical historical usage"

        customer_explanation = (
            f"The {horizon_name.replace('_', ' ')} forecast of {forecast_value:.1f} Wh is {trend_desc} "
            f"for this {'weekend' if is_weekend else 'weekday'} hour ({hour:02d}:00). "
            f"Recent immediate demand was {recent_load:.1f} Wh."
        )

        return {
            "forecast_Wh": round(forecast_value, 2),
            "baseline_Wh": round(baseline_value, 2),
            "percentage_difference": pct_diff,
            "primary_drivers": {
                "recent_consumption_Wh": recent_load,
                "hour_of_day": hour,
                "is_weekend": is_weekend
            },
            "customer_friendly_summary": customer_explanation
        }

    @staticmethod
    def explain_anomaly_event(event: Dict[str, Any], baseline_stats: Optional[Dict[str, Any]] = None) -> str:
        """
        Translates a multi-interval sustained anomaly event into clear, non-technical customer insight.
        """
        duration = event.get("duration_minutes", 30)
        peak = event.get("peak_consumption", 0.0)
        expected = event.get("expected_baseline", 0.0)
        excess = event.get("potential_excess_energy", 0.0)
        unit = event.get("unit", "Wh")

        return (
            f"Identified sustained unusual consumption over {duration} minutes (peak: {peak:.1f} {unit}, "
            f"expected: {expected:.1f} {unit}), accumulating approximately {excess:.1f} {unit} of potential excess energy. "
            f"This pattern suggests continuous appliance operation (e.g. climate control or water heating) "
            f"exceeding normal baseline levels."
        )
