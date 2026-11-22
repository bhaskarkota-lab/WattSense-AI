"""
Actionable Recommendation Service
Generates grounded, customer-friendly energy-saving advice tied directly to observed consumption patterns.

CRITICAL PRINCIPLES:
- Recommendations must connect directly to observed usage patterns.
- Avoid unverified appliance claims (e.g. do not claim a specific compressor or motor is faulty without sub-metering).
- Provide practical, no-cost or low-cost behavioral guidance.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.db.models import Customer, Recommendation
from backend.app.schemas.recommendation import (
    CustomerRecommendation,
    CustomerRecommendationsResponse,
)

class RecommendationService:
    """Delivers actionable, customer-friendly recommendations tied to observed consumption."""

    @staticmethod
    def get_customer_recommendations(
        db: Session,
        consumer_number: str
    ) -> Optional[CustomerRecommendationsResponse]:
        """
        Retrieves personalized energy efficiency recommendations from database.
        """
        clean_num = consumer_number.strip().upper()
        cust = db.query(Customer).filter(Customer.consumer_number == clean_num).first()
        if not cust:
            return None

        recs = (
            db.query(Recommendation)
            .filter(Recommendation.customer_id == cust.id, Recommendation.is_active == True)
            .order_by(Recommendation.id.asc())
            .all()
        )

        items = [
            CustomerRecommendation(
                id=r.id,
                category=r.category,
                title=r.title,
                description=r.description,
                action_steps=r.action_steps,
                estimated_impact=r.potential_savings_estimate
            )
            for r in recs
        ]

        return CustomerRecommendationsResponse(
            consumer_number=cust.consumer_number,
            recommendations=items
        )

    @staticmethod
    def generate_grounded_recommendations(
        events: List[Dict[str, Any]],
        unit: str = "kWh"
    ) -> List[Dict[str, Any]]:
        """
        Dynamically generates recommendations based on observed event patterns.
        """
        if not events:
            return [{
                "category": "MAINTAIN_EFFICIENCY",
                "title": "Consistent & Efficient Consumption Habits",
                "description": "Your electricity consumption pattern matches expected household benchmarks with no sustained excess periods.",
                "action_steps": "Continue maintaining regular thermostat schedules and switching off unused devices.",
                "potential_savings_estimate": "Operating within optimal efficiency range"
            }]

        recs = []
        has_overnight = any("00:" in e.get("start_time", "") or "01:" in e.get("start_time", "") or "02:" in e.get("start_time", "") or "03:" in e.get("start_time", "") or "04:" in e.get("start_time", "") for e in events)
        has_extended = any(e.get("duration_hours", 0) >= 2.0 for e in events)
        has_evening = any("17:" in e.get("start_time", "") or "18:" in e.get("start_time", "") or "19:" in e.get("start_time", "") or "20:" in e.get("start_time", "") for e in events)

        if has_overnight:
            recs.append({
                "category": "STANDBY_LEAKAGE",
                "title": "Audit Overnight Baseload & Continuous Power Draw",
                "description": "Sustained electricity usage was detected during midnight-to-dawn hours when household activity is minimal. This pattern frequently stems from continuous water heating, unmonitored ventilation, or electronic equipment left idling.",
                "action_steps": "1. Verify whether water heaters or circulation pumps have active timer controls.\n2. Enable night-setback schedules on cooling or heating thermostats.\n3. Utilize power boards with switches for audio-visual and home office clusters.",
                "potential_savings_estimate": "Estimated 25% to 35% reduction in overnight standby consumption"
            })

        if has_evening:
            recs.append({
                "category": "PEAK_OPTIMIZATION",
                "title": "Stagger Discretionary Evening Wash Cycles",
                "description": "Noticeable elevated consumption occurred during early evening hours (5 PM – 8 PM) when multiple appliances operate simultaneously.",
                "action_steps": "1. Schedule dishwashers or washing machines using delay-start timers to run after 9 PM.\n2. Avoid running washing machines and electric clothes dryers concurrently.",
                "potential_savings_estimate": "Estimated 10% to 15% reduction in peak-hour demand"
            })

        if has_extended:
            recs.append({
                "category": "EXTENDED_RUN_CHECK",
                "title": "Check Automated Timers on High-Consumption Equipment",
                "description": "Continuous high-draw periods lasting over 2 hours were detected. Equipment left operating unattended contributes significantly to accumulated electricity usage.",
                "action_steps": "1. Inspect heating and cooling temperature settings to avoid continuous compressor operation.\n2. Ensure room heaters and dehumidifiers are set to auto-cutoff rather than manual continuous run.",
                "potential_savings_estimate": "Estimated 15% to 20% potential savings during long-duration runs"
            })

        if not recs:
            recs.append({
                "category": "GENERAL_MONITORING",
                "title": "Periodic Consumption Monitoring",
                "description": "Moderate consumption elevations were observed during normal hours.",
                "action_steps": "Monitor your weekly consumption trends to ensure temporary high usage returns to typical baseline levels.",
                "potential_savings_estimate": "Estimated 5% to 10% awareness savings"
            })

        return recs
