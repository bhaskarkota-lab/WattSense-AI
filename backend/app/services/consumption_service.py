from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from backend.app.db.models import Customer, ConsumptionRecord, WastageAlert
from backend.app.schemas.consumption import (
    ConsumptionDataPoint,
    DailyConsumptionSummary,
    CustomerConsumptionResponse,
)
from backend.app.schemas.customer import CustomerSummaryResponse

class ConsumptionService:
    """Handles time-series consumption retrieval, aggregation, and KPI summaries for customers."""

    @classmethod
    def get_customer_consumption_summary(
        cls,
        db: Session,
        consumer_number: str
    ) -> Optional[CustomerSummaryResponse]:
        """
        Computes customer-friendly electricity consumption KPIs:
        - Total electricity consumed
        - Expected baseline consumption
        - Potential excess consumption
        - Number of sustained unusual periods
        - Consumption change compared with previous period
        - Customer-friendly narrative observations
        """
        clean_num = consumer_number.strip().upper()
        cust = db.query(Customer).filter(Customer.consumer_number == clean_num).first()
        if not cust:
            return None

        records = (
            db.query(ConsumptionRecord)
            .filter(ConsumptionRecord.customer_id == cust.id)
            .order_by(ConsumptionRecord.timestamp.asc())
            .all()
        )

        masked_num = (
            f"{clean_num[:-4]}•••{clean_num[-1]}"
            if len(clean_num) > 6
            else f"{clean_num[:2]}•••{clean_num[-1]}"
        )

        if not records:
            return CustomerSummaryResponse(
                consumer_number=cust.consumer_number,
                masked_consumer_number=masked_num,
                total_consumption=0.0,
                expected_consumption=0.0,
                potential_excess=0.0,
                potential_excess_percentage=0.0,
                sustained_unusual_periods_count=0,
                change_vs_previous_period_pct=0.0,
                unit="kWh",
                alert_level="NORMAL",
                status_headline="No Monitored Consumption Data",
                narrative_observations=[
                    "We could not reliably assess this account because no historical readings are currently recorded in the registry."
                ],
                period_start=None,
                period_end=None
            )

        unit = records[0].unit
        total_val = sum(r.consumption_value for r in records)

        # Retrieve alerts
        alerts = (
            db.query(WastageAlert)
            .filter(WastageAlert.customer_id == cust.id)
            .order_by(WastageAlert.timestamp.desc())
            .all()
        )

        potential_excess_val = sum(a.potential_excess_consumption for a in alerts)
        expected_val = max(0.0, total_val - potential_excess_val)
        excess_pct = round((potential_excess_val / total_val * 100.0), 1) if total_val > 0 else 0.0

        # Change compared with previous period (split chronological records into halves)
        half = len(records) // 2
        first_half_sum = sum(r.consumption_value for r in records[:half]) if half > 0 else 0.0
        second_half_sum = sum(r.consumption_value for r in records[half:]) if half > 0 else 0.0
        
        if first_half_sum > 0:
            change_pct = round(((second_half_sum - first_half_sum) / first_half_sum) * 100.0, 1)
        else:
            change_pct = 0.0

        # Construct narrative observations adhering to required customer-friendly explanations
        observations = []
        if len(alerts) > 0:
            observations.append("Your electricity usage was higher than your usual pattern during certain periods.")
            has_overnight = any(a.timestamp.hour in [0, 1, 2, 3, 4, 5] for a in alerts)
            if has_overnight:
                observations.append("Your overnight consumption remained elevated on some days.")
            observations.append("Some short consumption increases did not persist beyond brief appliance cycles.")
            
            # Check if recent readings trended normal
            recent_alert = alerts[0].timestamp
            latest_record = records[-1].timestamp
            if (latest_record - recent_alert).total_seconds() > 86400:
                observations.append("Your consumption returned closer to its usual pattern in recent days.")
            
            alert_level = "HIGH" if any(a.severity == "HIGH" for a in alerts) else "ATTENTION"
            headline = f"Potential Unnecessary Consumption Identified ({len(alerts)} Periods)"
        else:
            observations.append("Your electricity consumption closely followed your typical historical baseline.")
            observations.append("Some short consumption increases did not persist and were within normal appliance activity.")
            observations.append("Your daily baseload remained consistent across low-demand hours.")
            alert_level = "NORMAL"
            headline = "Electricity Usage Within Expected Parameters"

        if len(records) < 24:
            observations.append("We could not reliably assess some periods because readings were unavailable.")

        return CustomerSummaryResponse(
            consumer_number=cust.consumer_number,
            masked_consumer_number=masked_num,
            total_consumption=round(total_val, 2),
            expected_consumption=round(expected_val, 2),
            potential_excess=round(potential_excess_val, 2),
            potential_excess_percentage=excess_pct,
            sustained_unusual_periods_count=len(alerts),
            change_vs_previous_period_pct=change_pct,
            unit=unit,
            alert_level=alert_level,
            status_headline=headline,
            narrative_observations=observations,
            period_start=records[0].timestamp,
            period_end=records[-1].timestamp
        )

    @staticmethod
    def get_customer_consumption(
        db: Session,
        consumer_number: str,
        limit: int = 500
    ) -> Optional[CustomerConsumptionResponse]:
        """
        Retrieves chronological electricity consumption records and daily aggregates.
        """
        clean_num = consumer_number.strip().upper()
        cust = db.query(Customer).filter(Customer.consumer_number == clean_num).first()
        if not cust:
            return None

        records = (
            db.query(ConsumptionRecord)
            .filter(ConsumptionRecord.customer_id == cust.id)
            .order_by(ConsumptionRecord.timestamp.asc())
            .limit(limit)
            .all()
        )

        if not records:
            return CustomerConsumptionResponse(
                consumer_number=cust.consumer_number,
                unit="kWh",
                total_readings=0,
                data_points=[],
                daily_summaries=[]
            )

        unit = records[0].unit
        data_points = [
            ConsumptionDataPoint(
                timestamp=r.timestamp,
                consumption_value=round(r.consumption_value, 3),
                unit=r.unit
            )
            for r in records
        ]

        # Aggregate by calendar date
        daily_map: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            d_str = r.timestamp.strftime("%Y-%m-%d")
            daily_map[d_str].append(r.consumption_value)

        daily_summaries = [
            DailyConsumptionSummary(
                date=d,
                total_consumption=round(sum(vals), 3),
                average_consumption=round(sum(vals) / len(vals), 3),
                peak_consumption=round(max(vals), 3),
                unit=unit
            )
            for d, vals in sorted(daily_map.items())
        ]

        return CustomerConsumptionResponse(
            consumer_number=cust.consumer_number,
            unit=unit,
            total_readings=len(records),
            data_points=data_points,
            daily_summaries=daily_summaries
        )
