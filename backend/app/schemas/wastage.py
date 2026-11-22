from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class WastageEventResponse(BaseModel):
    """
    Customer-facing unusual consumption event.
    CRITICAL: Raw anomaly scores, ML models, and theft labels are strictly omitted.
    """
    timestamp: datetime
    actual_usage: float
    expected_usage: float
    excess_usage: float
    unit: str
    severity: str = Field(..., description="LOW, MEDIUM, or HIGH unusual consumption level")
    status: str
    description: str

class CustomerWastageReport(BaseModel):
    """
    Customer-friendly electricity wastage and excess consumption report.
    """
    consumer_number: str
    unit: str
    total_excess_identified: float
    active_alerts_count: int
    events: List[WastageEventResponse]
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    summary_message: str
