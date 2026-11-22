import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.app.db.models import (
    Customer,
    ConsumptionRecord,
    WastageAlert,
    Recommendation,
    AdminModelMetric,
)

def test_customer_creation_and_uniqueness(db_session):
    """Verifies that customers can be created and consumer_number is strictly unique."""
    cust1 = Customer(
        consumer_number="CONS-TEST-001",
        customer_type="Residential",
        region="North Grid",
        meter_number="MTR-001",
        is_demo=True
    )
    db_session.add(cust1)
    db_session.commit()

    assert cust1.id is not None
    assert cust1.consumer_number == "CONS-TEST-001"
    assert cust1.is_demo is True

    # Duplicate consumer number must raise IntegrityError
    cust_dup = Customer(
        consumer_number="CONS-TEST-001",
        customer_type="Commercial"
    )
    db_session.add(cust_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_consumption_record_relationship(db_session):
    """Verifies consumption record foreign key and cascade relationship."""
    cust = Customer(consumer_number="CONS-TEST-002", is_demo=True)
    db_session.add(cust)
    db_session.commit()

    now = datetime.now(timezone.utc)
    rec = ConsumptionRecord(
        customer_id=cust.id,
        timestamp=now,
        consumption_value=1.45,
        unit="kWh",
        interval_minutes=60,
        source_dataset="TEST_SUITE"
    )
    db_session.add(rec)
    db_session.commit()

    assert len(cust.consumption_records) == 1
    assert cust.consumption_records[0].consumption_value == 1.45
    assert cust.consumption_records[0].unit == "kWh"

def test_wastage_alert_creation(db_session):
    """Verifies wastage alert attributes, severity, and calculations."""
    cust = Customer(consumer_number="CONS-TEST-003", is_demo=True)
    db_session.add(cust)
    db_session.commit()

    alert = WastageAlert(
        customer_id=cust.id,
        timestamp=datetime.now(timezone.utc),
        actual_consumption=2.80,
        expected_consumption=0.75,
        potential_excess_consumption=2.05,
        unit="kWh",
        severity="HIGH",
        persistence_count=4
    )
    db_session.add(alert)
    db_session.commit()

    assert alert.id is not None
    assert alert.severity == "HIGH"
    assert alert.potential_excess_consumption == 2.05
    assert alert.persistence_count == 4

def test_recommendation_model(db_session):
    """Verifies recommendation model persistence and attributes."""
    cust = Customer(consumer_number="CONS-TEST-004", is_demo=True)
    db_session.add(cust)
    db_session.commit()

    rec = Recommendation(
        customer_id=cust.id,
        category="PEAK_HOURS",
        title="Shift Peak Laundry Loads",
        description="Run washing machines after 9 PM to reduce peak demand.",
        potential_savings_estimate="10-15% peak load reduction"
    )
    db_session.add(rec)
    db_session.commit()

    assert rec.id is not None
    assert rec.category == "PEAK_HOURS"
    assert rec.is_active is True

def test_admin_model_metric_persistence(db_session):
    """Verifies that AdminModelMetric accurately logs model validation statistics."""
    metric = AdminModelMetric(
        model_name="RandomForestClassifier",
        dataset_name="SGCC Electricity Theft Detection",
        task_type="THEFT_CLASSIFICATION",
        version_tag="v1.0-benchmark",
        metrics_payload='{"roc_auc": 0.88, "precision": 0.74, "recall": 0.69}',
        hyperparameters='{"n_estimators": 350, "class_weight": "balanced_subsample"}',
        train_rows=33897,
        test_rows=8475
    )
    db_session.add(metric)
    db_session.commit()

    assert metric.id is not None
    assert metric.task_type == "THEFT_CLASSIFICATION"
    assert "roc_auc" in metric.metrics_payload
