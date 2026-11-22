def test_customer_lookup_success(client):
    """Verifies consumer number lookup without requiring OTP and returns masked ID."""
    response = client.post("/api/v1/customer/lookup", json={"consumer_number": "TEST-CONS-101"})
    assert response.status_code == 200
    data = response.json()
    assert data["consumer_number"] == "TEST-CONS-101"
    assert "masked_consumer_number" in data
    assert "•••" in data["masked_consumer_number"]
    assert data["customer_type"] == "Residential"
    assert data["is_demo"] is True

def test_customer_lookup_invalid_format(client):
    """Verifies rejection of invalid consumer number format (prevents injection)."""
    response = client.post("/api/v1/customer/lookup", json={"consumer_number": "DROP TABLE customers;--"})
    assert response.status_code == 400
    assert "invalid consumer number format" in response.json()["detail"].lower()

def test_customer_lookup_not_found(client):
    """Verifies 404 response for non-existent consumer number."""
    response = client.post("/api/v1/customer/lookup", json={"consumer_number": "NON-EXISTENT-999"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_customer_consumption_summary(client):
    """Verifies customer consumption summary endpoint with KPIs and friendly narratives."""
    response = client.get("/api/v1/customer/TEST-CONS-101/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["consumer_number"] == "TEST-CONS-101"
    assert "masked_consumer_number" in data
    assert data["total_consumption"] > 0
    assert data["expected_consumption"] >= 0
    assert data["potential_excess"] >= 0
    assert "change_vs_previous_period_pct" in data
    assert "alert_level" in data
    assert len(data["narrative_observations"]) > 0

def test_customer_consumption_history(client):
    """Verifies retrieval of time-series consumption and daily summaries."""
    response = client.get("/api/v1/customer/TEST-CONS-101/consumption")
    assert response.status_code == 200
    data = response.json()
    assert data["consumer_number"] == "TEST-CONS-101"
    assert data["total_readings"] == 24
    assert len(data["data_points"]) == 24
    assert len(data["daily_summaries"]) > 0

def test_customer_wastage_report_sanitization(client):
    """
    CRITICAL TEST: Verifies that customer wastage report NEVER exposes
    internal ML terms, theft labels, or raw anomaly scores.
    """
    response = client.get("/api/v1/customer/TEST-CONS-101/wastage-report")
    assert response.status_code == 200
    data = response.json()
    assert data["consumer_number"] == "TEST-CONS-101"
    assert data["total_excess_identified"] > 0
    assert len(data["events"]) == 1
    
    event = data["events"][0]
    assert event["actual_usage"] == 1.85
    assert event["expected_usage"] == 0.50
    assert event["excess_usage"] == 1.35
    assert event["severity"] == "HIGH"

    # Strict content check: No internal ML or theft terminology in customer response payload
    raw_text = response.text.lower()
    forbidden_terms = [
        "theft",
        "isolation forest",
        "random forest",
        "kmeans",
        "roc_auc",
        "anomaly_score",
        "contamination",
        "train_rows",
        "test_rows"
    ]
    for term in forbidden_terms:
        assert term not in raw_text, f"Forbidden technical/theft term '{term}' exposed in customer response!"

def test_customer_recommendations(client):
    """Verifies actionable recommendations endpoint."""
    response = client.get("/api/v1/customer/TEST-CONS-101/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert data["consumer_number"] == "TEST-CONS-101"
    assert len(data["recommendations"]) >= 1
    assert data["recommendations"][0]["category"] == "STANDBY_LEAKAGE"
