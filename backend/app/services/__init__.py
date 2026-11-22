"""Business logic and analytics services."""
from backend.app.services.data_ingestion import DataIngestionService
from backend.app.services.customer_service import CustomerService
from backend.app.services.consumption_service import ConsumptionService
from backend.app.services.wastage_service import WastageService
from backend.app.services.recommendation_service import RecommendationService

__all__ = [
    "DataIngestionService",
    "CustomerService",
    "ConsumptionService",
    "WastageService",
    "RecommendationService",
]
