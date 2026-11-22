from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class ConsumptionDataPoint(BaseModel):
    """Individual electricity consumption reading."""
    timestamp: datetime
    consumption_value: float
    unit: str

    model_config = {"from_attributes": True}

class DailyConsumptionSummary(BaseModel):
    """Aggregated daily electricity usage."""
    date: str
    total_consumption: float
    average_consumption: float
    peak_consumption: float
    unit: str

class CustomerConsumptionResponse(BaseModel):
    """Customer-facing consumption history."""
    consumer_number: str
    unit: str
    total_readings: int
    data_points: List[ConsumptionDataPoint]
    daily_summaries: List[DailyConsumptionSummary]
