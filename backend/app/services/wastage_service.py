"""
Electricity Wastage Detection Service
Integrates baseline calculations, persistence filtering, excess quantification,
and customer-friendly findings generation.
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.db.models import Customer, WastageAlert, ConsumptionRecord
from backend.app.schemas.wastage import WastageEventResponse, CustomerWastageReport
from backend.app.services.baseline_service import BaselineCalculationService
from backend.app.services.persistence_filter import PersistenceFilteringService
from backend.app.services.customer_findings_service import CustomerFindingsService

class WastageService:
    """Provides customer-friendly wastage reports, anomaly detection, and excess consumption summaries."""

    @staticmethod
    def get_customer_wastage_report(
        db: Session,
        consumer_number: str
    ) -> Optional[CustomerWastageReport]:
        """
        Retrieves identified unusual consumption events without internal ML jargon or theft labels.
        """
        clean_num = consumer_number.strip().upper()
        cust = db.query(Customer).filter(Customer.consumer_number == clean_num).first()
        if not cust:
            return None

        alerts = (
            db.query(WastageAlert)
            .filter(WastageAlert.customer_id == cust.id)
            .order_by(WastageAlert.timestamp.desc())
            .all()
        )

        if not alerts:
            return CustomerWastageReport(
                consumer_number=cust.consumer_number,
                unit="kWh",
                total_excess_identified=0.0,
                active_alerts_count=0,
                events=[],
                summary_message="No unusual electricity consumption or wastage patterns have been detected. Your consumption is within expected parameters."
            )

        unit = alerts[0].unit
        total_excess = sum(a.potential_excess_consumption for a in alerts)
        
        events = [
            WastageEventResponse(
                timestamp=a.timestamp,
                actual_usage=round(a.actual_consumption, 3),
                expected_usage=round(a.expected_consumption, 3),
                excess_usage=round(a.potential_excess_consumption, 3),
                unit=a.unit,
                severity=a.severity,
                status=a.alert_status,
                description=(
                    f"Consumption reached {a.actual_consumption:.2f} {a.unit}, exceeding expected usage of "
                    f"{a.expected_consumption:.2f} {a.unit} by {a.potential_excess_consumption:.2f} {a.unit}. "
                    f"This sustained pattern was observed across {a.persistence_count} consecutive measurement intervals."
                )
            )
            for a in alerts
        ]

        summary_msg = (
            f"Identified {len(events)} unusual consumption period(s) totaling an estimated "
            f"{total_excess:.2f} {unit} of potential excess usage. Check the personalized recommendations below for steps to reduce this consumption."
        )

        return CustomerWastageReport(
            consumer_number=cust.consumer_number,
            unit=unit,
            total_excess_identified=round(total_excess, 3),
            active_alerts_count=len(events),
            events=events,
            period_start=alerts[-1].timestamp if alerts else None,
            period_end=alerts[0].timestamp if alerts else None,
            summary_message=summary_msg
        )

    @classmethod
    def evaluate_consumption_series(
        cls,
        series: pd.Series,
        timestamps: pd.Series,
        baseline_method: str = "day_and_hour",
        train_df: Optional[pd.DataFrame] = None,
        eval_df: Optional[pd.DataFrame] = None,
        min_persistence: int = 3,
        interval_minutes: int = 10,
        unit: str = "Wh"
    ) -> Dict[str, Any]:
        """
        Executes end-to-end wastage detection on a consumption series.
        
        Methods supported:
        - 'global_median': Static historical median & IQR fence
        - 'rolling_median': 24h rolling median & rolling IQR
        - 'rolling_mean_std': 24h rolling mean + k*std
        - 'hour_of_day': 24-hour diurnal conditional baseline
        - 'day_and_hour': Day-of-week + Hour-of-day conditional baseline
        """
        if baseline_method == "global_median":
            expected, upper = BaselineCalculationService.historical_global_median(
                train_df["Appliances"] if train_df is not None else series,
                series
            )
        elif baseline_method == "rolling_median":
            expected, upper = BaselineCalculationService.rolling_historical_median(series, window=144, multiplier=1.5)
        elif baseline_method == "rolling_mean_std":
            expected, upper = BaselineCalculationService.rolling_historical_mean_std(series, window=144, k=2.5)
        elif baseline_method == "hour_of_day":
            assert train_df is not None and eval_df is not None
            expected, upper = BaselineCalculationService.hour_of_day_conditional(train_df, eval_df)
        elif baseline_method == "day_and_hour":
            assert train_df is not None and eval_df is not None
            expected, upper = BaselineCalculationService.day_and_hour_conditional(train_df, eval_df)
        else:
            raise ValueError(f"Unknown baseline method: {baseline_method}")

        detection_results = PersistenceFilteringService.detect_and_filter(
            actual=series.values,
            expected=expected,
            upper_bound=upper,
            timestamps=timestamps.values,
            min_consecutive_intervals=min_persistence,
            interval_minutes=interval_minutes,
            unit=unit
        )

        # Generate customer-friendly findings
        customer_findings = CustomerFindingsService.generate_findings(
            events=detection_results["events"],
            unit=unit,
            total_excess=detection_results["total_potential_excess"]
        )

        return {
            "baseline_method": baseline_method,
            "min_persistence_intervals": min_persistence,
            "detection_results": detection_results,
            "customer_findings": customer_findings,
            "expected_baseline": expected,
            "upper_bound": upper
        }
