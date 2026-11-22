from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

class AdminDatasetInfo(BaseModel):
    """Admin-only dataset metadata and data quality audit."""
    dataset_name: str
    file_path: str
    total_records: int
    features_count: int
    missing_values_count: int
    negative_values_count: int
    unit_verified: str
    sampling_interval: str
    is_theft_dataset: bool
    data_quality_status: str
    notes: str

class AdminModelMetricRecord(BaseModel):
    """Admin-only model performance tracking record."""
    id: int
    model_name: str
    dataset_name: str
    task_type: str
    version_tag: str
    metrics: Dict[str, Any]
    hyperparameters: Optional[Dict[str, Any]] = None
    train_rows: Optional[int] = None
    test_rows: Optional[int] = None
    evaluated_at: datetime

class AdminHealthStatus(BaseModel):
    """Backend system health and database diagnostic status."""
    status: str
    database_connected: bool
    database_type: str
    uci_data_available: bool
    sgcc_data_available: bool
    total_customers: int
    total_consumption_records: int
    active_wastage_alerts: int
    timestamp: datetime

class WastageEngineConfigSchema(BaseModel):
    """Admin configuration for the electricity wastage detection engine."""
    baseline_method: str = "day_and_hour"
    min_persistence_intervals: int = 3
    interval_minutes: int = 10
    unit: str = "kWh"
    last_updated: Optional[datetime] = None

class DatabaseHealthResponse(BaseModel):
    """Admin dedicated database health check and telemetry response."""
    status: str  # "HEALTHY", "DEGRADED", "UNAVAILABLE"
    database_connected: bool
    dialect: str  # "postgresql" or "sqlite"
    database_name: str
    active_url_masked: str
    is_fallback: bool
    fail_closed_enforced: bool
    environment: str
    latency_ms: float
    pool_status: Dict[str, Any]
    table_counts: Dict[str, int]
    timestamp: datetime
