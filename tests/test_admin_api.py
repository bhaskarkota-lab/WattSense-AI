from backend.app.core.config import settings

def test_admin_health(client, admin_headers):
    """Verifies that admin health endpoint reports database and dataset status when authenticated."""
    # Unauthenticated request must be rejected
    res_unauth = client.get("/api/v1/admin/health")
    assert res_unauth.status_code == 401

    # Authenticated request succeeds
    response = client.get("/api/v1/admin/health", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["database_connected"] is True
    assert data["total_customers"] >= 2
    assert data["total_consumption_records"] >= 24

def test_admin_datasets_audit(client, admin_headers):
    """Verifies admin dataset audit endpoint returns research integrity metadata."""
    # Unauthenticated rejected
    assert client.get("/api/v1/admin/datasets").status_code == 401

    # Authenticated succeeds
    response = client.get("/api/v1/admin/datasets", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert "integrity_rules" in data
    assert "Wh (Watt-hours)" in data["integrity_rules"]["uci_units"]
    assert "theft benchmark" in data["integrity_rules"]["sgcc_labels"].lower()

def test_admin_metrics(client, admin_headers):
    """Verifies admin model metrics retrieval when authenticated."""
    assert client.get("/api/v1/admin/metrics").status_code == 401

    response = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    metric = data[0]
    assert metric["model_name"] == "RandomForestRegressor"
    assert metric["task_type"] == "FORECASTING"
    assert "MAE_Wh" in metric["metrics"]

def test_admin_customers_list(client, admin_headers):
    """Verifies retrieval of registered customers for admin registry when authenticated."""
    assert client.get("/api/v1/admin/customers").status_code == 401

    response = client.get("/api/v1/admin/customers", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    cons_nums = [c["consumer_number"] for c in data]
    assert "TEST-CONS-101" in cons_nums
    assert "TEST-CONS-202" in cons_nums

def test_admin_forecasting_benchmarks(client, admin_headers):
    """Verifies that multi-horizon forecasting benchmarks are accessible when authenticated."""
    assert client.get("/api/v1/admin/forecasting-benchmarks").status_code == 401

    response = client.get("/api/v1/admin/forecasting-benchmarks", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    if "status" not in data:
        assert "h1" in data

def test_admin_wastage_benchmarks(client, admin_headers):
    """Verifies that wastage detection engine benchmarks are accessible when authenticated."""
    assert client.get("/api/v1/admin/wastage-benchmarks").status_code == 401

    response = client.get("/api/v1/admin/wastage-benchmarks", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    if "status" not in data:
        assert "baseline_comparison_validation" in data

def test_root_frontend_serving(client):
    """Verifies that public root URL returns the web application HTML or info."""
    response = client.get("/")
    assert response.status_code == 200

def test_admin_auth_endpoint(client):
    """Verifies admin passkey authentication and signed session token issuance."""
    # Valid passkey from settings
    res_valid = client.post("/api/v1/admin/auth", json={"passkey": settings.ADMIN_SECRET_KEY})
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["authenticated"] is True
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] > 0
    # Token must be a valid 3-part JWT
    assert len(data["access_token"].split(".")) == 3

    # Invalid passkey must be rejected
    res_invalid = client.post("/api/v1/admin/auth", json={"passkey": "wrong_password_attempt"})
    assert res_invalid.status_code == 401
    assert "invalid administrator credentials" in res_invalid.json()["detail"].lower()

def test_admin_wastage_config_runtime_tuning(client, admin_headers):
    """
    CRITICAL TEST: Verifies that unauthenticated configuration updates are REJECTED (401),
    and authorized updates succeed (200).
    """
    update_payload = {
        "baseline_method": "hour_of_day",
        "min_persistence_intervals": 4,
        "interval_minutes": 10,
        "unit": "kWh"
    }

    # 1. Unauthenticated GET must be rejected
    res_unauth_get = client.get("/api/v1/admin/wastage-config")
    assert res_unauth_get.status_code == 401, "Security failure: Unauthenticated GET /wastage-config was not rejected!"

    # 2. Unauthenticated POST must be rejected (Security fix verified)
    res_unauth_post = client.post("/api/v1/admin/wastage-config", json=update_payload)
    assert res_unauth_post.status_code == 401, "Security failure: Unauthenticated POST /wastage-config was not rejected!"

    # 3. Authenticated GET succeeds
    res_auth_get = client.get("/api/v1/admin/wastage-config", headers=admin_headers)
    assert res_auth_get.status_code == 200
    cfg = res_auth_get.json()
    assert "min_persistence_intervals" in cfg
    assert "baseline_method" in cfg

    # 4. Authenticated POST succeeds
    res_auth_post = client.post("/api/v1/admin/wastage-config", json=update_payload, headers=admin_headers)
    assert res_auth_post.status_code == 200
    updated = res_auth_post.json()
    assert updated["min_persistence_intervals"] == 4
    assert updated["baseline_method"] == "hour_of_day"

def test_admin_test_status_endpoint(client, admin_headers):
    """Verifies automated test telemetry endpoint when authenticated."""
    assert client.get("/api/v1/admin/test-status").status_code == 401

    response = client.get("/api/v1/admin/test-status", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_tests_passed"] >= 40
    assert len(data["verified_modules"]) >= 8

def test_admin_authorization_protection(client, admin_headers):
    """Verifies strict protection across sensitive admin routes."""
    # Valid Bearer session token
    res_auth = client.get("/api/v1/admin/secure-telemetry", headers=admin_headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["authorized"] is True

    # Valid X-Admin-Key header
    res_key = client.get("/api/v1/admin/secure-telemetry", headers={"X-Admin-Key": settings.ADMIN_SECRET_KEY})
    assert res_key.status_code == 200
    assert res_key.json()["authorized"] is True

    # Invalid Bearer token
    res_unauth = client.get("/api/v1/admin/secure-telemetry", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res_unauth.status_code == 401

    # Invalid X-Admin-Key
    res_bad_key = client.get("/api/v1/admin/secure-telemetry", headers={"X-Admin-Key": "wrong_key"})
    assert res_bad_key.status_code == 401

    # Missing all credentials
    res_no_auth = client.get("/api/v1/admin/secure-telemetry")
    assert res_no_auth.status_code == 401
