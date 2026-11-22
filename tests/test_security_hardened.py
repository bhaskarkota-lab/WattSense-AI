import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import create_application, MAX_REQUEST_SIZE_BYTES
from backend.app.core.config import settings
from backend.app.core.security import create_customer_verification_token
from backend.app.db.models import Customer

@pytest.fixture
def test_app_client():
    app = create_application()
    return TestClient(app)

# ==============================================================================
# 1. PUBLIC HEALTH & LIVENESS PROBE TESTS
# ==============================================================================

def test_public_health_probe_accessible_without_auth(test_app_client):
    """Verifies that /health is public, unauthenticated, and returns 200 OK."""
    response = test_app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["database"] == "CONNECTED"
    assert "service" in data
    assert "timestamp" in data
    # Ensure no internal credentials or sensitive URLs leak
    assert "postgres:" not in str(data)

# ==============================================================================
# 2. SECURITY HEADERS & REQUEST CORRELATION TESTS
# ==============================================================================

def test_security_headers_present_on_responses(test_app_client):
    """Verifies that essential HTTP security headers are injected on all responses."""
    response = test_app_client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in headers
    assert len(headers["X-Request-ID"]) > 10

def test_request_id_propagation_if_provided(test_app_client):
    """Verifies that an incoming X-Request-ID is preserved and propagated."""
    custom_id = "trace-req-abc-12345"
    response = test_app_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id

# ==============================================================================
# 3. REQUEST PAYLOAD SIZE LIMIT TESTS (DoS PREVENTION)
# ==============================================================================

def test_oversized_payload_rejected_with_413(test_app_client):
    """Verifies that request bodies exceeding MAX_REQUEST_SIZE_BYTES return HTTP 413."""
    oversized_length = str(MAX_REQUEST_SIZE_BYTES + 1024)
    response = test_app_client.post(
        "/api/v1/customer/lookup",
        headers={"Content-Length": oversized_length, "Content-Type": "application/json"},
        content=b"x" * 100
    )
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["detail"]

# ==============================================================================
# 4. SQL INJECTION & INPUT SANITIZATION TESTS
# ==============================================================================

def test_sql_injection_attempt_in_consumer_number_rejected(test_app_client):
    """Verifies that SQL injection payloads in consumer numbers are strictly rejected."""
    sqli_payloads = [
        "CONS-RES-1001' OR '1'='1",
        "CONS-RES-1001; DROP TABLE customers;--",
        "CONS-RES-1001' UNION SELECT NULL, NULL--",
        "../../etc/passwd",
        "<script>alert(1)</script>"
    ]
    for payload in sqli_payloads:
        # GET route regex validation
        resp_get = test_app_client.get(f"/api/v1/customer/{payload}/summary")
        assert resp_get.status_code in (400, 404), f"Failed for payload: {payload}"
        
        # POST lookup validation
        resp_post = test_app_client.post("/api/v1/customer/lookup", json={"consumer_number": payload})
        assert resp_post.status_code in (400, 404), f"Failed for payload: {payload}"

# ==============================================================================
# 5. IDOR & CROSS-CUSTOMER TENANT ISOLATION TESTS
# ==============================================================================

def test_idor_cross_customer_access_forbidden(client, seeded_db):
    """Verifies that a valid token for Customer A cannot access Customer B's records."""
    cust_a = Customer(
        consumer_number="REAL-CONS-9999",
        customer_type="Residential",
        region="North Zone",
        meter_number="MTR-9999",
        is_active=True,
        is_demo=False
    )
    cust_b = Customer(
        consumer_number="REAL-CONS-8888",
        customer_type="Residential",
        region="South Zone",
        meter_number="MTR-8888",
        is_active=True,
        is_demo=False
    )
    seeded_db.add_all([cust_a, cust_b])
    seeded_db.commit()

    token_cust_a = create_customer_verification_token("REAL-CONS-9999", expires_minutes=60)
    
    # Attempt to access another customer's data using Customer A's token
    headers = {"Authorization": f"Bearer {token_cust_a}"}
    response = client.get("/api/v1/customer/REAL-CONS-8888/summary", headers=headers)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]

# ==============================================================================
# 6. PRODUCTION DOCS SUPPRESSION TESTS
# ==============================================================================

def test_production_environment_suppresses_swagger_docs():
    """Verifies that OpenAPI Swagger UI is suppressed in production environment."""
    with patch("backend.app.main.settings.ENVIRONMENT", "production"):
        prod_app = create_application()
        prod_client = TestClient(prod_app)
        docs_resp = prod_client.get("/docs")
        assert docs_resp.status_code == 404
        redoc_resp = prod_client.get("/redoc")
        assert redoc_resp.status_code == 404
