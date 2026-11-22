from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class CustomerLookupRequest(BaseModel):
    """
    Consumer number prototype lookup.
    No OTP required as per design specification.
    """
    consumer_number: str = Field(..., min_length=3, max_length=64, description="Electricity consumer account number")

class CustomerProfileResponse(BaseModel):
    """
    Sanitized customer profile.
    CRITICAL: Never exposes internal ML names, theft labels, or sensitive PII.
    """
    consumer_number: str
    masked_consumer_number: str
    customer_type: str
    region: str
    meter_number: Optional[str] = None
    masked_meter_number: Optional[str] = None
    is_demo: bool = Field(False, description="Flag indicating demonstration account")
    account_status: str = "Active"

    model_config = {"from_attributes": True}

class CustomerVerificationRequest(BaseModel):
    """
    Secure customer verification request for utility deployment.
    Accepts consumer number and one-time passcode (OTP) or billing verification PIN.
    """
    consumer_number: str = Field(..., min_length=3, max_length=64, description="Electricity consumer account number")
    verification_code: str = Field(..., min_length=4, max_length=32, description="One-time passcode (OTP) or billing PIN")

class CustomerVerificationResponse(BaseModel):
    """
    Signed customer authorization token response upon successful verification.
    """
    verified: bool = True
    token_type: str = "Bearer"
    access_token: str
    expires_in: int
    masked_consumer_number: str
    message: str

class CustomerSummaryResponse(BaseModel):
    """
    Customer-facing high-level consumption and wastage KPI summary.
    Enforces verified units, no ML technical jargon, and friendly narrative guidance.
    """
    consumer_number: str
    masked_consumer_number: str
    total_consumption: float
    expected_consumption: float
    potential_excess: float
    potential_excess_percentage: float
    sustained_unusual_periods_count: int
    change_vs_previous_period_pct: float
    unit: str
    alert_level: str
    status_headline: str
    narrative_observations: List[str]
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
