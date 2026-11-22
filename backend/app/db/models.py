from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.db.base import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Customer(Base):
    """
    Electricity customer profile.
    
    CRITICAL: is_demo clearly distinguishes synthetic demonstration accounts
    from real customer records so synthetic data is NEVER presented as real.
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    consumer_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    customer_type: Mapped[str] = mapped_column(String(32), default="Residential")  # Residential, Commercial, Industrial
    region: Mapped[str] = mapped_column(String(64), default="Default Grid Area")
    meter_number: Mapped[str] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)  # Must be True for synthetic test profiles
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    consumption_records: Mapped[List["ConsumptionRecord"]] = relationship(
        "ConsumptionRecord", back_populates="customer", cascade="all, delete-orphan"
    )
    wastage_alerts: Mapped[List["WastageAlert"]] = relationship(
        "WastageAlert", back_populates="customer", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="customer", cascade="all, delete-orphan"
    )


class ConsumptionRecord(Base):
    """
    Time-series electricity consumption records for a customer.
    
    Units and sampling intervals are explicitly tracked (e.g. Wh for UCI 10-min, kWh for daily).
    """
    __tablename__ = "consumption_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumption_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="kWh")  # "kWh" or "Wh"
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)  # 10 for UCI, 1440 for daily SGCC
    source_dataset: Mapped[str] = mapped_column(String(64), default="REAL")  # "UCI_APPLIANCES", "SGCC_BENCHMARK", "DEMO_SYNTHETIC"
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="consumption_records")

    __table_args__ = (
        Index("idx_customer_timestamp", "customer_id", "timestamp"),
    )


class WastageAlert(Base):
    """
    Identified unusual or potential excess electricity consumption.
    
    Includes expected baseline, actual usage, quantified excess, and persistence count.
    Customer view receives sanitized summaries; raw anomaly scores are never exposed.
    """
    __tablename__ = "wastage_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actual_consumption: Mapped[float] = mapped_column(Float, nullable=False)
    expected_consumption: Mapped[float] = mapped_column(Float, nullable=False)
    potential_excess_consumption: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="kWh")
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")  # "LOW", "MEDIUM", "HIGH"
    alert_status: Mapped[str] = mapped_column(String(16), default="NEW")  # "NEW", "ACKNOWLEDGED", "RESOLVED"
    persistence_count: Mapped[int] = mapped_column(Integer, default=1)  # Consecutive anomalous intervals
    potential_cost_excess: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Populated only if verified tariff exists
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="wastage_alerts")


class Recommendation(Base):
    """
    Customer-facing actionable energy-saving advice grounded in observed usage patterns.
    """
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), default="BASE_LOAD")  # BASE_LOAD, PEAK_HOURS, STANDBY_LEAKAGE, APPLIANCE_EFFICIENCY
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    potential_savings_estimate: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="recommendations")


class AdminModelMetric(Base):
    """
    Model performance tracking and validation metrics for Admin & Researcher views.
    
    Strictly separated by task type:
    - FORECASTING (chronological holdout: MAE, RMSE, R²)
    - WASTAGE_DETECTION (unsupervised baseline, contamination, thresholds)
    - THEFT_CLASSIFICATION (SGCC theft benchmark: ROC-AUC, Precision, Recall)
    """
    __tablename__ = "admin_model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # FORECASTING, WASTAGE_DETECTION, THEFT_CLASSIFICATION
    version_tag: Mapped[str] = mapped_column(String(32), default="v1.0")
    metrics_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded metrics
    hyperparameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-encoded parameters
    train_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    test_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
