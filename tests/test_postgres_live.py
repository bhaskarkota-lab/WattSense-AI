import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.core.config import settings, Settings
from backend.app.db.session import engine, active_db_url, is_sqlite_fallback, get_db_context, SessionLocal
from backend.app.db.models import Customer, ConsumptionRecord, WastageAlert, Recommendation, AdminModelMetric

client = TestClient(app)
ADMIN_PASSKEY = settings.ADMIN_SECRET_KEY

@pytest.fixture
def admin_headers():
    response = client.post("/api/v1/admin/auth", json={"passkey": ADMIN_PASSKEY})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==============================================================================
# 1. LIVE POSTGRESQL ENGINE & DIALECT TESTS
# ==============================================================================

def test_live_postgres_dialect_and_connection():
    """Verifies that active database engine is PostgreSQL and is not in fallback mode."""
    assert engine.dialect.name == "postgresql"
    assert is_sqlite_fallback is False
    assert "postgresql" in active_db_url
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1;")).scalar()
        assert res == 1

def test_live_postgres_db_health_endpoint(admin_headers):
    """Verifies that /db-health returns status HEALTHY with PostgreSQL dialect."""
    response = client.get("/api/v1/admin/db-health", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["dialect"] == "postgresql"
    assert data["database_name"] == "electricity_wastage_db"
    assert data["is_fallback"] is False
    assert data["database_connected"] is True
    assert data["latency_ms"] >= 0.0
    assert data["table_counts"]["customers"] == 3
    assert data["table_counts"]["consumption_records"] == 1008
    assert data["table_counts"]["wastage_alerts"] == 5
    assert data["table_counts"]["recommendations"] == 4
    assert data["table_counts"]["admin_model_metrics"] == 4

# ==============================================================================
# 2. LIVE POSTGRESQL DATA QUERIES ACROSS ALL FIVE TABLES
# ==============================================================================

def test_live_postgres_customers_table():
    """Verifies all 3 demonstration customers exist in PostgreSQL."""
    with SessionLocal() as db:
        customers = db.query(Customer).order_by(Customer.consumer_number).all()
        assert len(customers) == 3
        c_nums = [c.consumer_number for c in customers]
        assert "CONS-RES-1001" in c_nums
        assert "CONS-RES-2002" in c_nums
        assert "CONS-COM-3003" in c_nums

def test_live_postgres_consumption_records_table():
    """Verifies 1,008 consumption records exist in PostgreSQL."""
    with SessionLocal() as db:
        count = db.query(ConsumptionRecord).count()
        assert count == 1008

def test_live_postgres_wastage_alerts_table():
    """Verifies 5 wastage alerts exist in PostgreSQL."""
    with SessionLocal() as db:
        count = db.query(WastageAlert).count()
        assert count == 5

def test_live_postgres_recommendations_table():
    """Verifies 4 recommendations exist in PostgreSQL."""
    with SessionLocal() as db:
        count = db.query(Recommendation).count()
        assert count == 4

def test_live_postgres_admin_model_metrics_table():
    """Verifies 4 admin model metrics exist in PostgreSQL."""
    with SessionLocal() as db:
        count = db.query(AdminModelMetric).count()
        assert count == 4

# ==============================================================================
# 3. LIVE POSTGRESQL TRANSACTION SAFETY & CONSTRAINTS
# ==============================================================================

def test_live_postgres_transaction_commit():
    """Verifies commit creates and persists record on PostgreSQL."""
    test_num = f"PG-LIVE-TEST-{int(time.time())}"
    with get_db_context() as session:
        session.add(Customer(consumer_number=test_num, customer_type="Residential", is_demo=True))

    with SessionLocal() as session:
        cust = session.query(Customer).filter_by(consumer_number=test_num).first()
        assert cust is not None
        session.delete(cust)
        session.commit()

def test_live_postgres_transaction_rollback():
    """Verifies exception rolls back uncommitted changes on PostgreSQL."""
    test_num = f"PG-LIVE-RB-{int(time.time())}"
    with pytest.raises(RuntimeError):
        with get_db_context() as session:
            session.add(Customer(consumer_number=test_num, customer_type="Residential", is_demo=True))
            session.flush()
            raise RuntimeError("Live simulated error")

    with SessionLocal() as session:
        cust = session.query(Customer).filter_by(consumer_number=test_num).first()
        assert cust is None

def test_live_postgres_unique_constraint_enforcement():
    """Verifies PostgreSQL unique constraint enforces unique consumer numbers."""
    with SessionLocal() as session:
        dup = Customer(consumer_number="CONS-RES-1001", customer_type="Commercial", is_demo=True)
        session.add(dup)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

# ==============================================================================
# 4. LIVE API ENDPOINTS POWERED BY POSTGRESQL
# ==============================================================================

def test_live_customer_lookup_via_postgres():
    """Verifies POST /api/v1/customer/lookup fetches data from PostgreSQL."""
    resp = client.post("/api/v1/customer/lookup", json={"consumer_number": "CONS-RES-1001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["masked_consumer_number"] == "CONS-RES-•••1"
    assert data["customer_type"] == "Residential"

def test_live_customer_summary_via_postgres():
    """Verifies GET /api/v1/customer/{consumer_number}/summary fetches from PostgreSQL."""
    resp = client.get("/api/v1/customer/CONS-RES-1001/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "status_headline" in data
    assert data["total_consumption"] > 0

def test_live_customer_wastage_report_via_postgres():
    """Verifies GET /api/v1/customer/{consumer_number}/wastage-report fetches from PostgreSQL."""
    resp = client.get("/api/v1/customer/CONS-RES-2002/wastage-report")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) > 0
    assert data["total_excess_identified"] > 0
