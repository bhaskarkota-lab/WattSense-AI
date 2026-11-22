from typing import Optional
from sqlalchemy.orm import Session
from backend.app.db.models import Customer
from backend.app.schemas.customer import CustomerProfileResponse
from backend.app.core.security import mask_consumer_number, mask_meter_number

class CustomerService:
    """Customer retrieval and sanitized profile presentation."""

    @staticmethod
    def get_customer_by_number(db: Session, consumer_number: str) -> Optional[Customer]:
        """Queries customer by consumer number."""
        clean_num = consumer_number.strip().upper()
        return db.query(Customer).filter(Customer.consumer_number == clean_num).first()

    @classmethod
    def lookup_customer(cls, db: Session, consumer_number: str) -> Optional[CustomerProfileResponse]:
        """
        Retrieves sanitized customer profile.
        CRITICAL: Never exposes internal ML model names, raw anomaly scores, or theft labels.
        Customer and meter identifiers are masked in customer-facing responses.
        """
        cust = cls.get_customer_by_number(db, consumer_number)
        if not cust:
            return None

        masked = mask_consumer_number(cust.consumer_number)
        masked_meter = mask_meter_number(cust.meter_number)

        return CustomerProfileResponse(
            consumer_number=cust.consumer_number,
            masked_consumer_number=masked,
            customer_type=cust.customer_type,
            region=cust.region,
            meter_number=masked_meter,
            masked_meter_number=masked_meter,
            is_demo=cust.is_demo,
            account_status="Active" if cust.is_active else "Inactive"
        )
