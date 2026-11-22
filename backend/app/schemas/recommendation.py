from typing import List, Optional
from pydantic import BaseModel

class CustomerRecommendation(BaseModel):
    """
    Actionable energy-saving advice grounded in observed electricity consumption patterns.
    """
    id: int
    category: str
    title: str
    description: str
    action_steps: Optional[str] = None
    estimated_impact: Optional[str] = None

class CustomerRecommendationsResponse(BaseModel):
    """Customer personalized recommendations list."""
    consumer_number: str
    recommendations: List[CustomerRecommendation]
