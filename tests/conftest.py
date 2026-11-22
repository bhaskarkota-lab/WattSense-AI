import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.db.models import (
    Customer,
    ConsumptionRecord,
    WastageAlert,
    Recommendation,
    AdminModelMetric,
)
from backend.app.main import create_application

# Use in-memory SQLite with StaticPool for fast, isolated, deterministic automated testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    """Provides a clean in-memory database session for each test function."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def seeded_db(db_session):
    """Seeds the in-memory database with test demonstration records."""
    cust1 = Customer(
        consumer_number="TEST-CONS-101",
        customer_type="Residential",
        region="Test North",
        meter_number="MTR-T101",
        is_active=True,
        is_demo=True
    )
    cust2 = Customer(
        consumer_number="TEST-CONS-202",
        customer_type="Residential",
        region="Test South",
        meter_number="MTR-T202",
        is_active=True,
        is_demo=True
    )
    db_session.add_all([cust1, cust2])
    db_session.commit()

    base_time = datetime.now(timezone.utc) - timedelta(days=2)
    for i in range(24):
        rec = ConsumptionRecord(
            customer_id=cust1.id,
            timestamp=base_time + timedelta(hours=i),
            consumption_value=0.5 + (0.1 if i % 2 == 0 else 0.0),
            unit="kWh",
            interval_minutes=60,
            source_dataset="TEST_FIXTURE",
            is_verified=True
        )
        db_session.add(rec)

    alert = WastageAlert(
        customer_id=cust1.id,
        timestamp=base_time + timedelta(hours=12),
        actual_consumption=1.85,
        expected_consumption=0.50,
        potential_excess_consumption=1.35,
        unit="kWh",
        severity="HIGH",
        alert_status="NEW",
        persistence_count=3
    )
    rec_item = Recommendation(
        customer_id=cust1.id,
        category="STANDBY_LEAKAGE",
        title="Excessive Base-Load Detected",
        description="Continuous power draw observed during low usage periods.",
        action_steps="Inspect always-on appliances.",
        potential_savings_estimate="15-20% estimated savings"
    )
    metric = AdminModelMetric(
        model_name="RandomForestRegressor",
        dataset_name="UCI Appliances Energy Prediction",
        task_type="FORECASTING",
        version_tag="v1.0-test",
        metrics_payload='{"MAE_Wh": 30.5, "RMSE_Wh": 65.2, "R2": 0.61}',
        train_rows=1000,
        test_rows=250
    )
    db_session.add_all([alert, rec_item, metric])
    db_session.commit()
    return db_session

@pytest.fixture(scope="function")
def client(seeded_db):
    """Provides a TestClient using the isolated in-memory test database."""
    app = create_application()
    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="function")
def admin_token():
    """Provides a valid signed administrator JWT session token for tests."""
    from backend.app.core.security import create_access_token
    return create_access_token(data={"sub": "admin", "role": "administrator"})

@pytest.fixture(scope="function")
def admin_headers(admin_token):
    """Provides Authorization header dict with valid Bearer token."""
    return {"Authorization": f"Bearer {admin_token}"}
