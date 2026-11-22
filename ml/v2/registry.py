"""
WattSense AI™ — Machine Learning V2 Isolated Model Registry
Implements Champion-Challenger evaluation, artifact cryptographic hashing, and approval workflows.
"""
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class V2ModelRegistry:
    """Manages versioned V2 candidate models, metrics tracking, and champion-challenger comparisons."""

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    REGISTRY_DIR = BASE_DIR / "models" / "v2"
    REGISTRY_FILE = REGISTRY_DIR / "v2_model_registry.json"

    # Known V1 Production Champions for strict comparison
    V1_CHAMPIONS = {
        1: {
            "name": "RidgeRegression (V1)",
            "version": "v1.0-forecasting",
            "artifact": "models/consumption_forecasting/best_forecaster_h1.joblib",
            "test_metrics": {
                "MAE_Wh": 26.62,
                "RMSE_Wh": 60.53,
                "R2": 0.5573,
                "sMAPE_pct": 22.11,
                "WAPE_pct": 26.89,
                "forecast_bias_Wh": 1.63
            }
        },
        6: {
            "name": "ExtraTreesRegressor (V1)",
            "version": "v1.0-forecasting",
            "artifact": "models/consumption_forecasting/best_forecaster_h6.joblib",
            "test_metrics": {
                "MAE_Wh": 62.15,
                "RMSE_Wh": 90.68,
                "R2": 0.0064,
                "sMAPE_pct": 47.98,
                "WAPE_pct": 62.78,
                "forecast_bias_Wh": -35.94
            }
        },
        144: {
            "name": "TimeOfDayAverage (Baseline Champion)",
            "version": "v1.0-baseline",
            "artifact": "Non-Parametric Diurnal Profile",
            "test_metrics": {
                "MAE_Wh": 47.73,
                "RMSE_Wh": 85.73,
                "R2": 0.1105,
                "sMAPE_pct": 38.55,
                "WAPE_pct": 48.21,
                "forecast_bias_Wh": -0.89
            }
        }
    }

    @classmethod
    def ensure_registry_exists(cls):
        """Ensures the registry directory and index exist."""
        cls.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.REGISTRY_FILE.exists():
            initial_data = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "registry_version": "v2.0",
                "champions": cls.V1_CHAMPIONS,
                "challengers": {}
            }
            cls.REGISTRY_FILE.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

    @staticmethod
    def calculate_sha256(filepath: Path) -> str:
        """Computes SHA256 checksum for a file."""
        if not filepath.exists():
            return "FILE_NOT_FOUND"
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def register_challenger(
        cls,
        model_id: str,
        horizon_steps: int,
        algorithm_name: str,
        hyperparameters: Dict[str, Any],
        test_metrics: Dict[str, Any],
        artifact_path: Path,
        feature_count: int,
        training_samples: int,
        test_samples: int
    ) -> Dict[str, Any]:
        """Registers a new V2 candidate model and performs champion-challenger comparison."""
        cls.ensure_registry_exists()
        checksum = cls.calculate_sha256(artifact_path)

        # Champion comparison
        champion = cls.V1_CHAMPIONS.get(horizon_steps, {})
        champ_m = champion.get("test_metrics", {})

        challenger_mae = test_metrics.get("MAE_Wh", 999.0)
        champion_mae = champ_m.get("MAE_Wh", 999.0)
        challenger_r2 = test_metrics.get("R2", -99.0)
        champion_r2 = champ_m.get("R2", -99.0)

        # Criteria for meaningful improvement: MAE reduction AND R2 improvement
        improved_mae = challenger_mae < champion_mae
        improved_r2 = challenger_r2 > champion_r2

        if improved_mae and improved_r2:
            comparison_verdict = "CHALLENGER_OUTPERFORMS_CHAMPION"
            approval_status = "RECOMMENDED_FOR_APPROVAL"
        elif improved_mae:
            comparison_verdict = "MARGINAL_MAE_IMPROVEMENT"
            approval_status = "CANDIDATE_UNDER_REVIEW"
        else:
            comparison_verdict = "INSUFFICIENT_IMPROVEMENT"
            approval_status = "REJECTED_CHALLENGER"

        record = {
            "model_id": model_id,
            "horizon_steps": horizon_steps,
            "algorithm": algorithm_name,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "artifact_path": str(artifact_path),
            "sha256": checksum,
            "feature_count": feature_count,
            "training_samples": training_samples,
            "test_samples": test_samples,
            "hyperparameters": hyperparameters,
            "test_metrics": test_metrics,
            "champion_metrics": champ_m,
            "mae_delta_vs_champion": round(challenger_mae - champion_mae, 2),
            "r2_delta_vs_champion": round(challenger_r2 - champion_r2, 4),
            "comparison_verdict": comparison_verdict,
            "approval_status": approval_status,
            "promoted_to_production": False
        }

        # Update registry file
        data = json.loads(cls.REGISTRY_FILE.read_text(encoding="utf-8"))
        data["challengers"][model_id] = record
        cls.REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return record

    @classmethod
    def get_registry_summary(cls) -> Dict[str, Any]:
        """Returns the current registry index."""
        cls.ensure_registry_exists()
        return json.loads(cls.REGISTRY_FILE.read_text(encoding="utf-8"))
