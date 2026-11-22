"""
Phase 8 Security Regression and Access Control Test Suite.
Verifies all 10 security remediation requirements:
1. Missing admin credentials rejection (401)
2. Invalid admin credentials rejection (401)
3. Valid admin credentials acceptance (200)
4. Unauthorized access prevention across all protected admin routes
5. Unauthorized runtime configuration update rejection (401)
6. Real customer data protection without verification (403)
7. Cross-customer tenant access prevention (403)
8. Consumer and meter identifier masking
9. CORS origin restrictions
10. Session token expiration and signature tampering detection
"""
import time
from datetime import timedelta
import pytest
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    create_customer_verification_token,
    mask_consumer_number,
    mask_meter_number,
)
from backend.app.db.models import Customer, ConsumptionRecord
from datetime import datetime, timezone

def test_missing_admin_credentials_rejected(client):
    """Scenario 1: Requests without credentials to protected admin routes return HTTP 401."""
    protected_endpoints = [
        "/api/v1/admin/health",
        "/api/v1/admin/datasets",
        "/api/v1/admin/metrics",
        "/api/v1/admin/customers",
        "/api/v1/admin/forecasting-benchmarks",
        "/api/v1/admin/wastage-benchmarks",
        "/api/v1/admin/test-status",
        "/api/v1/admin/wastage-config",
        "/api/v1/admin/secure-telemetry",
    ]
    for endpoint in protected_endpoints:
        res = client.get(endpoint)
        assert res.status_code == 401, f"Security failure: Missing credentials on {endpoint} did not return 401! Got {res.status_code}"
        assert "unauthorized" in res.json()["detail"].lower()

def test_invalid_admin_credentials_rejected(client):
    """Scenario 2: Requests with invalid Bearer token or invalid X-Admin-Key return HTTP 401."""
    # Invalid Bearer format
    res1 = client.get("/api/v1/admin/health", headers={"Authorization": "Bearer totally-fake-token"})
    assert res1.status_code == 401

    # Invalid X-Admin-Key
    res2 = client.get("/api/v1/admin/health", headers={"X-Admin-Key": "incorrect_admin_passkey"})
    assert res2.status_code == 401

def test_valid_admin_credentials_accepted(client, admin_headers):
    """Scenario 3: Requests with valid Bearer session token return HTTP 200."""
    res = client.get("/api/v1/admin/health", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "OPERATIONAL"

def test_unauthorized_runtime_config_update_rejected(client, admin_headers):
    """Scenario 5: Attempting to update wastage configuration without authorization is rejected."""
    payload = {
        "baseline_method": "hour_of_day",
        "min_persistence_intervals": 5,
        "interval_minutes": 10,
        "unit": "kWh"
    }
    # Unauthenticated POST must be rejected with 401
    res_unauth = client.post("/api/v1/admin/wastage-config", json=payload)
    assert res_unauth.status_code == 401
    assert "unauthorized" in res_unauth.json()["detail"].lower()

    # Authenticated POST succeeds
    res_auth = client.post("/api/v1/admin/wastage-config", json=payload, headers=admin_headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["min_persistence_intervals"] == 5

def test_real_customer_access_without_verification_rejected(client, db_session):
    """Scenario 6: Real utility customer data (is_demo=False) cannot be accessed without verification."""
    # Seed a real customer account
    real_cust = Customer(
        consumer_number="REAL-CONS-9901",
        customer_type="Residential",
        region="Metro Central",
        meter_number="MTR-REAL-9901",
        is_active=True,
        is_demo=False  # REAL utility customer
    )
    db_session.add(real_cust)
    db_session.commit()

    # Adding a consumption reading
    db_session.add(ConsumptionRecord(
        customer_id=real_cust.id,
        timestamp=datetime.now(timezone.utc),
        consumption_value=4.5,
        unit="kWh",
        interval_minutes=60,
        source_dataset="UTILITY_REAL",
        is_verified=True
    ))
    db_session.commit()

    # 1. Unverified lookup must be rejected with 403 Forbidden
    res_lookup = client.post("/api/v1/customer/lookup", json={"consumer_number": "REAL-CONS-9901"})
    assert res_lookup.status_code == 403
    assert "access denied" in res_lookup.json()["detail"].lower()

    # 2. Unverified consumption query must be rejected with 403 Forbidden
    res_cons = client.get("/api/v1/customer/REAL-CONS-9901/consumption")
    assert res_cons.status_code == 403
    assert "access denied" in res_cons.json()["detail"].lower()

    # 3. Unverified summary query must be rejected with 403 Forbidden
    res_sum = client.get("/api/v1/customer/REAL-CONS-9901/summary")
    assert res_sum.status_code == 403

def test_customer_verification_and_authenticated_access(client, db_session):
    """Verifies that real customers can authenticate via OTP challenge and access their records."""
    real_cust = Customer(
        consumer_number="REAL-CONS-7702",
        customer_type="Commercial",
        region="Industrial Sector",
        meter_number="MTR-REAL-7702",
        is_active=True,
        is_demo=False
    )
    db_session.add(real_cust)
    db_session.commit()

    db_session.add(ConsumptionRecord(
        customer_id=real_cust.id,
        timestamp=datetime.now(timezone.utc),
        consumption_value=12.5,
        unit="kWh",
        interval_minutes=60,
        source_dataset="UTILITY_REAL",
        is_verified=True
    ))
    db_session.commit()

    # 1. Verification with invalid OTP fails
    res_bad_otp = client.post("/api/v1/customer/verify", json={
        "consumer_number": "REAL-CONS-7702",
        "verification_code": "000000"
    })
    assert res_bad_otp.status_code == 401

    # 2. Verification with valid OTP succeeds and returns signed token
    res_good_otp = client.post("/api/v1/customer/verify", json={
        "consumer_number": "REAL-CONS-7702",
        "verification_code": "123456"
    })
    assert res_good_otp.status_code == 200
    token_data = res_good_otp.json()
    assert token_data["verified"] is True
    cust_token = token_data["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 3. Access with valid verification token succeeds
    res_cons = client.get("/api/v1/customer/REAL-CONS-7702/consumption", headers=cust_headers)
    assert res_cons.status_code == 200
    assert len(res_cons.json()["data_points"]) >= 1

def test_cross_customer_access_prevention(client, db_session):
    """Scenario 7: Token issued for Customer A CANNOT be used to access Customer B."""
    cust_a = Customer(consumer_number="REAL-CONS-AAA", is_demo=False)
    cust_b = Customer(consumer_number="REAL-CONS-BBB", is_demo=False)
    db_session.add_all([cust_a, cust_b])
    db_session.commit()

    # Issue token strictly for Customer A
    token_a = create_customer_verification_token("REAL-CONS-AAA")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Customer A queries Customer B's endpoint -> Must be rejected with 403 Forbidden
    res_cross = client.get("/api/v1/customer/REAL-CONS-BBB/consumption", headers=headers_a)
    assert res_cross.status_code == 403
    assert "forbidden" in res_cross.json()["detail"].lower()
    assert "cannot access another customer" in res_cross.json()["detail"].lower()

def test_consumer_and_meter_identifier_masking():
    """Scenario 8: Verifies masking utility functions for consumer and meter identifiers."""
    assert mask_consumer_number("CONS-RES-1001") == "CONS-RES-•••1"
    assert mask_consumer_number("TEST-CONS-101") == "TEST-CONS-•••1"
    assert mask_consumer_number("12345") == "123-••••-45"
    assert "•••" in mask_consumer_number("SHORT")

    assert mask_meter_number("MTR-1001-A") == "MTR-••••-A"
    assert mask_meter_number("MTR-T101") == "MTR-••••-T101"
    assert mask_meter_number(None) is None

def test_cors_origin_restrictions(client):
    """Scenario 9: Verifies that arbitrary origins are not permitted with credentials."""
    # Disallowed origin
    res_bad = client.options(
        "/api/v1/customer/lookup",
        headers={
            "Origin": "http://malicious-attacker-domain.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    # The response must not reflect the disallowed origin
    allowed_origin = res_bad.headers.get("access-control-allow-origin")
    assert allowed_origin != "http://malicious-attacker-domain.com"
    assert allowed_origin != "*"

    # Allowed origin
    res_good = client.options(
        "/api/v1/customer/lookup",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert res_good.headers.get("access-control-allow-origin") == "http://localhost:8000"

def test_session_token_expiration_and_tampering():
    """Scenario 10: Verifies that expired tokens and tampered signatures are rejected."""
    from backend.app.core.security import verify_access_token
    from fastapi import HTTPException

    # 1. Expired token (negative delta)
    expired_token = create_access_token(
        data={"sub": "admin", "role": "administrator"},
        expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()

    # 2. Tampered signature (altered payload)
    valid_token = create_access_token(data={"sub": "admin", "role": "administrator"})
    parts = valid_token.split(".")
    # Tamper with signature
    tampered_sig = parts[2][:-4] + "XXXX"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    
    with pytest.raises(HTTPException) as exc_tamper:
        verify_access_token(tampered_token)
    assert exc_tamper.value.status_code == 401
    assert "signature" in exc_tamper.value.detail.lower()
