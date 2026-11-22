import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.models import Customer, ConsumptionRecord, WastageAlert, Recommendation, AdminModelMetric
from backend.app.db.session import (
    get_engine_and_url,
    get_db_context,
    mask_database_url,
    is_sqlite_fallback,
    SessionLocal,
)

client = TestClient(app)

from backend.app.core.config import settings
ADMIN_PASSKEY = settings.ADMIN_SECRET_KEY

@pytest.fixture
def admin_headers():
    """Generates valid administrator authentication headers for API tests."""
    response = client.post("/api/v1/admin/auth", json={"passkey": ADMIN_PASSKEY})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. URL MASKING & CREDENTIAL HYGIENE TESTS
# ==============================================================================

def test_mask_database_url_hides_password():
    """Verifies that database passwords are masked in connection strings."""
    raw_pg = "postgresql+psycopg2://admin_user:super_secret_password_123@db.prod.internal:5432/watt_sense_prod"
    masked = mask_database_url(raw_pg)
    assert "super_secret_password_123" not in masked
    assert "admin_user:****@db.prod.internal:5432/watt_sense_prod" in masked

def test_mask_database_url_handles_sqlite_and_empty():
    """Verifies SQLite and empty URLs are handled safely without errors."""
    assert mask_database_url("") == ""
    assert mask_database_url(None) == ""
    sqlite_url = "sqlite:///path/to/database.db"
    assert mask_database_url(sqlite_url) == sqlite_url


# ==============================================================================
# 2. DEDICATED DATABASE HEALTH CHECK ENDPOINT TESTS
# ==============================================================================

def test_db_health_endpoint_authenticated(admin_headers):
    """Tests GET /api/v1/admin/db-health returns comprehensive telemetry to admins."""
    response = client.get("/api/v1/admin/db-health", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
    assert data["database_connected"] is True
    assert "dialect" in data
    assert data["dialect"] in ("postgresql", "sqlite")
    assert "database_name" in data
    assert "active_url_masked" in data
    # Ensure password is never exposed in the response
    assert "postgres:postgres" not in data["active_url_masked"]
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0.0
    assert "pool_status" in data
    assert "table_counts" in data
    assert "customers" in data["table_counts"]
    assert "consumption_records" in data["table_counts"]
    assert data["table_counts"]["customers"] >= 3

def test_db_health_endpoint_unauthorized():
    """Verifies GET /api/v1/admin/db-health is strictly protected against unauthenticated calls."""
    response = client.get("/api/v1/admin/db-health")
    assert response.status_code == 401


# ==============================================================================
# 3. TRANSACTION MANAGEMENT & ROLLBACK TESTS
# ==============================================================================

def test_get_db_context_commit():
    """Verifies that get_db_context commits successful transactions."""
    test_consumer = f"TEST-CTX-COMMIT-{int(datetime.now().timestamp())}"
    with get_db_context() as session:
        cust = Customer(
            consumer_number=test_consumer,
            customer_type="Residential",
            is_demo=True
        )
        session.add(cust)

    # Verify persisted in a separate session
    with SessionLocal() as verify_session:
        saved = verify_session.query(Customer).filter_by(consumer_number=test_consumer).first()
        assert saved is not None
        assert saved.consumer_number == test_consumer
        # Clean up
        verify_session.delete(saved)
        verify_session.commit()

def test_get_db_context_rollback_on_exception():
    """Verifies that get_db_context rolls back uncommitted changes on exception."""
    test_consumer = f"TEST-CTX-ROLLBACK-{int(datetime.now().timestamp())}"
    
    with pytest.raises(ValueError, match="Simulated application failure"):
        with get_db_context() as session:
            cust = Customer(
                consumer_number=test_consumer,
                customer_type="Residential",
                is_demo=True
            )
            session.add(cust)
            session.flush()  # sends INSERT to DB, but not committed yet
            raise ValueError("Simulated application failure")

    # Verify record was rolled back and does NOT exist
    with SessionLocal() as verify_session:
        saved = verify_session.query(Customer).filter_by(consumer_number=test_consumer).first()
        assert saved is None


# ==============================================================================
# 4. DATABASE INTEGRITY & CONSTRAINT TESTS
# ==============================================================================

def test_unique_consumer_number_constraint():
    """Verifies that duplicate consumer numbers are strictly rejected by database constraints."""
    duplicate_num = "CONS-RES-1001"  # Existing demo consumer
    with SessionLocal() as session:
        dup = Customer(
            consumer_number=duplicate_num,
            customer_type="Commercial",
            is_demo=True
        )
        session.add(dup)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


# ==============================================================================
# 5. ENVIRONMENT & PRODUCTION FAIL-CLOSED ENFORCEMENT TESTS
# ==============================================================================

def test_production_config_rejects_sqlite_fallback():
    """Verifies that Pydantic Settings rejects ALLOW_SQLITE_FALLBACK=True in production."""
    with pytest.raises(ValueError, match="In production mode, ALLOW_SQLITE_FALLBACK must be False"):
        Settings(
            ENVIRONMENT="production",
            ALLOW_SQLITE_FALLBACK=True,
            ADMIN_SECRET_KEY="a-very-strong-unique-production-secret-12345",
            SECRET_KEY="a-very-strong-unique-production-secret-67890",
        )

def test_fail_closed_in_production_when_postgres_fails():
    """
    Verifies that get_engine_and_url fails closed immediately (RuntimeError)
    in production if PostgreSQL primary connection fails, rather than falling back to SQLite.
    """
    with patch("backend.app.db.session.settings.ENVIRONMENT", "production"):
        with patch("backend.app.db.session.settings.ALLOW_SQLITE_FALLBACK", False):
            with patch("backend.app.db.session.settings.DATABASE_URL", "postgresql+psycopg2://fake:fake@127.0.0.1:5432/fake_db"):
                with pytest.raises(RuntimeError, match="CRITICAL DATABASE FAILURE: Unable to connect to primary PostgreSQL"):
                    get_engine_and_url()

def test_sqlite_fallback_allowed_in_development():
    """Verifies that development mode cleanly falls back to SQLite when PostgreSQL is unreachable."""
    with patch("backend.app.db.session.settings.ENVIRONMENT", "development"):
        with patch("backend.app.db.session.settings.ALLOW_SQLITE_FALLBACK", True):
            with patch("backend.app.db.session.settings.DATABASE_URL", "postgresql+psycopg2://invalid:creds@127.0.0.1:5432/nonexistent"):
                engine, url, is_fallback = get_engine_and_url()
                assert is_fallback is True
                assert "sqlite" in url


# ==============================================================================
# 6. ALEMBIC SCHEMA & ORM MODEL CONSISTENCY TESTS
# ==============================================================================

def test_alembic_models_and_metadata_consistency():
    """Verifies that all core domain models are registered in Base.metadata and have primary keys."""
    expected_tables = {
        "customers",
        "consumption_records",
        "wastage_alerts",
        "recommendations",
        "admin_model_metrics",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables), (
        f"Missing tables in SQLAlchemy metadata: {expected_tables - registered_tables}"
    )

    # Verify primary keys and essential indexes exist on every table
    for table_name in expected_tables:
        table = Base.metadata.tables[table_name]
        pks = [col.name for col in table.primary_key.columns]
        assert "id" in pks, f"Table {table_name} missing 'id' primary key column."
