"""
WattSense AI™ — Machine Learning V2 API Router
Exposes versioned endpoints for multi-horizon probabilistic forecasting,
multi-method anomaly detection, explainability, and model registry status.
"""
from fastapi import APIRouter, HTTPException, status
from backend.app.schemas.v2_ml import (
    V2ForecastRequest,
    V2ForecastResponse,
    V2AnomalyRequest,
    V2AnomalyResponse,
    V2ExplanationRequest,
    V2ExplanationResponse,
    V2ModelStatusResponse,
)
from backend.app.services.v2_ml_service import V2MLInferenceService
from ml.v2.explainability import V2ExplainabilityService

router = APIRouter(prefix="/ml", tags=["V2 Advanced Machine Learning Engine"])


@router.post("/forecast", response_model=V2ForecastResponse, summary="Generate Probabilistic Forecast")
def generate_v2_forecast(request: V2ForecastRequest):
    """
    Generates multi-horizon consumption forecast with conformal prediction intervals.
    Supported horizons: 1 (10m), 6 (1h), and 144 (24h).
    """
    try:
        return V2MLInferenceService.generate_forecast(request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Inference error: {exc}")


@router.post("/anomalies", response_model=V2AnomalyResponse, summary="Multi-Method Anomaly Detection")
def detect_v2_anomalies(request: V2AnomalyRequest):
    """
    Executes multi-method consensus anomaly detection (Isolation Forest + LOF + Robust Z + Diurnal)
    with 30-minute persistence filtering.
    """
    try:
        return V2MLInferenceService.detect_anomalies(request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Anomaly detection error: {exc}")


@router.post("/explanations", response_model=V2ExplanationResponse, summary="Explain Forecast or Consumption Pattern")
def explain_v2_prediction(request: V2ExplanationRequest):
    """
    Generates customer-friendly explanatory drivers comparing predicted/observed consumption against baselines.
    """
    try:
        sample_row = {
            "Appliances": request.forecast_Wh,
            "hour": request.hour,
            "is_weekend": int(request.is_weekend)
        }
        res = V2ExplainabilityService.explain_prediction(
            sample_row=sample_row,
            forecast_value=request.forecast_Wh,
            horizon_name=request.horizon_name,
            baseline_value=request.baseline_Wh
        )
        return V2ExplanationResponse(
            forecast_Wh=res["forecast_Wh"],
            baseline_Wh=res["baseline_Wh"],
            percentage_difference=res["percentage_difference"],
            primary_drivers=res["primary_drivers"],
            customer_friendly_summary=res["customer_friendly_summary"]
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Explanation error: {exc}")


@router.get("/model-status", response_model=V2ModelStatusResponse, summary="V2 Model Registry & Drift Telemetry")
def get_v2_model_status():
    """
    Returns champion-challenger model registry index, concept drift status, and deep learning benchmark assessment.
    """
    try:
        return V2MLInferenceService.get_model_status()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Status retrieval error: {exc}")
