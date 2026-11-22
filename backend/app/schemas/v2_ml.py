"""
WattSense AI™ — Machine Learning V2 Pydantic Schemas
Strict request and response schemas for multi-horizon probabilistic forecasting,
multi-method anomaly detection, explainability, and champion-challenger model registry.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class V2ForecastRequest(BaseModel):
    horizon_steps: int = Field(default=1, description="Forecast horizon steps: 1 (10m), 6 (1h), or 144 (24h)")
    telemetry_features: Optional[Dict[str, float]] = Field(default=None, description="Optional custom feature dict; uses latest baseline if omitted")
    confidence_level: float = Field(default=0.90, ge=0.50, le=0.99, description="Conformal prediction confidence level")


class V2ForecastResponse(BaseModel):
    horizon_steps: int
    horizon_name: str
    model_id: str
    algorithm: str
    predicted_mean_Wh: float
    lower_bound_Wh: float
    upper_bound_Wh: float
    confidence_level: float
    interval_method: str = "Split Conformal Prediction"
    primary_drivers: Dict[str, Any]
    explanation: str


class V2AnomalyRequest(BaseModel):
    readings: List[float] = Field(..., min_length=1, description="List of sequential 10-minute consumption values")
    timestamps: Optional[List[str]] = Field(default=None, description="Optional list of ISO timestamp strings")
    unit: str = Field(default="Wh", description="Measurement unit (Wh or kWh)")


class V2AnomalyEvent(BaseModel):
    start_time: str
    end_time: str
    consecutive_steps: int
    duration_minutes: int
    peak_consumption: float
    mean_consumption: float
    expected_baseline: float
    potential_excess_energy: float
    unit: str
    severity: str
    status: str
    consensus_strength: float
    explanation: str


class V2AnomalyResponse(BaseModel):
    total_readings: int
    total_candidate_intervals: int
    suppressed_isolated_bursts: int
    sustained_events_count: int
    total_potential_excess: float
    unit: str
    persistence_rule: str = "Minimum 3 consecutive 10-minute intervals (30 minutes)"
    events: List[V2AnomalyEvent]


class V2ExplanationRequest(BaseModel):
    forecast_Wh: float
    baseline_Wh: float
    hour: int = Field(ge=0, le=23)
    is_weekend: bool = False
    horizon_name: str = "10_minutes_ahead"


class V2ExplanationResponse(BaseModel):
    forecast_Wh: float
    baseline_Wh: float
    percentage_difference: float
    primary_drivers: Dict[str, Any]
    customer_friendly_summary: str


class V2ModelStatusResponse(BaseModel):
    registry_version: str
    champions: Dict[str, Any]
    challengers: Dict[str, Any]
    drift_status: str
    drifted_features_count: int
    data_sufficiency_assessment: Dict[str, Any]
