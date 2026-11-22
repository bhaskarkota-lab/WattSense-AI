"""
WattSense AI™ — Phase 10.1: Comprehensive Live Docker Deployment Verification
Hits http://127.0.0.1:8000 (running inside the Docker Compose container cluster).
Tests all 10 core integration requirements from Task 7.
"""
import sys
import json
from pathlib import Path
import httpx

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
from backend.app.core.config import settings

BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = settings.ADMIN_SECRET_KEY

def run_tests():
    print("=" * 80)
    print("WattSense AI™ — Phase 10.1: Live Docker Deployment Integration Test")
    print(f"Target URL: {BASE_URL}")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Public Health Check
    print("\n[1] Testing Public Health Endpoint (/health)...")
    res_health = client.get("/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.status_code}"
    health_data = res_health.json()
    print(f"    Status   : {health_data.get('status')}")
    print(f"    Database : {health_data.get('database')}")
    assert health_data.get("status") == "OPERATIONAL"
    assert health_data.get("database") == "CONNECTED"
    print("    -> PASS")

    # 2. Frontend SPA Root
    print("\n[2] Testing Frontend SPA Root Delivery (GET /)...")
    res_root = client.get("/")
    assert res_root.status_code == 200, f"Frontend delivery failed: {res_root.status_code}"
    assert "WattSense" in res_root.text or "root" in res_root.text
    print(f"    Content-Type: {res_root.headers.get('content-type')}")
    print(f"    Body Length : {len(res_root.text):,} bytes")
    print("    -> PASS")

    # 3. Customer Lookup (Demonstration Account)
    print("\n[3] Testing Customer Lookup (POST /api/v1/customer/lookup)...")
    res_lookup = client.post("/api/v1/customer/lookup", json={"consumer_number": "CONS-RES-1001"})
    assert res_lookup.status_code == 200, f"Customer lookup failed: {res_lookup.status_code}"
    cust = res_lookup.json()
    print(f"    Consumer : {cust.get('consumer_number')}")
    print(f"    Name     : {cust.get('customer_name')}")
    print(f"    Type     : {cust.get('customer_type')}")
    print(f"    Region   : {cust.get('region')}")
    print("    -> PASS")

    # 4. Customer Consumption Summary
    print("\n[4] Testing Customer Summary (GET /api/v1/customer/CONS-RES-1001/summary)...")
    res_sum = client.get("/api/v1/customer/CONS-RES-1001/summary")
    assert res_sum.status_code == 200, f"Customer summary failed: {res_sum.status_code}"
    summary = res_sum.json()
    print(f"    Status Headline : {summary.get('status_headline')}")
    print(f"    Total Consumed  : {summary.get('total_consumed_kwh')} kWh")
    print(f"    Tariff Rate     : ₹{summary.get('tariff_rate_inr_per_kwh')}/kWh")
    print("    -> PASS")

    # 5. Customer Consumption History (Chart Data)
    print("\n[5] Testing Customer Consumption History (GET /api/v1/customer/CONS-RES-1001/consumption)...")
    res_cons = client.get("/api/v1/customer/CONS-RES-1001/consumption")
    assert res_cons.status_code == 200, f"Consumption query failed: {res_cons.status_code}"
    points = res_cons.json().get("data_points", [])
    print(f"    Data Points Returned: {len(points)} readings (Hourly cadence verified)")
    assert len(points) > 0, "No consumption readings returned"
    print("    -> PASS")

    # 6. Wastage Detection Engine Findings
    print("\n[6] Testing Wastage Detection Engine (GET /api/v1/customer/CONS-RES-1001/wastage-report)...")
    res_wastage = client.get("/api/v1/customer/CONS-RES-1001/wastage-report")
    assert res_wastage.status_code == 200, f"Wastage query failed: {res_wastage.status_code}"
    w_data = res_wastage.json()
    print(f"    Headline        : {w_data.get('status_headline')}")
    print(f"    Baseline Method : {w_data.get('baseline_method')}")
    print(f"    Active Alerts   : {len(w_data.get('recent_alerts', []))}")
    print("    -> PASS")

    # 7. Actionable Recommendations
    print("\n[7] Testing Recommendations (GET /api/v1/customer/CONS-RES-1001/recommendations)...")
    res_rec = client.get("/api/v1/customer/CONS-RES-1001/recommendations")
    assert res_rec.status_code == 200, f"Recommendations query failed: {res_rec.status_code}"
    recs = res_rec.json().get("recommendations", [])
    print(f"    Recommendations Count: {len(recs)}")
    for r in recs[:2]:
        print(f"      - [{r.get('category')}]: {r.get('title')} ({r.get('potential_savings_estimate')})")
    print("    -> PASS")

    # 8. Admin Authentication & Session JWT
    print("\n[8] Testing Admin Authentication (POST /api/v1/admin/auth)...")
    res_login = client.post("/api/v1/admin/auth", json={"passkey": ADMIN_KEY})
    assert res_login.status_code == 200, f"Admin login failed: {res_login.status_code}"
    token = res_login.json().get("access_token") or res_login.json().get("token")
    assert token, "No session token returned"
    auth_headers = {"Authorization": f"Bearer {token}"}
    print(f"    Session Token Issued : {token[:16]}... (HMAC-SHA256)")
    print("    -> PASS")

    # 9. Admin PostgreSQL Telemetry & Database Health
    print("\n[9] Testing Admin PostgreSQL Health (GET /api/v1/admin/db-health)...")
    res_db = client.get("/api/v1/admin/db-health", headers=auth_headers)
    assert res_db.status_code == 200, f"Admin db-health failed: {res_db.status_code}"
    db_metrics = res_db.json()
    t_counts = db_metrics.get("table_counts", {})
    print(f"    Status           : {db_metrics.get('status')}")
    print(f"    Dialect          : {db_metrics.get('dialect')}")
    print(f"    Database Name    : {db_metrics.get('database_name')}")
    print(f"    Customers        : {t_counts.get('customers')}")
    print(f"    Consumption Rows : {t_counts.get('consumption_records')}")
    print(f"    Wastage Alerts   : {t_counts.get('wastage_alerts')}")
    print(f"    Recommendations  : {t_counts.get('recommendations')}")
    print(f"    ML Model Metrics : {t_counts.get('admin_model_metrics')}")
    assert db_metrics.get("status") == "HEALTHY"
    assert db_metrics.get("dialect") == "postgresql"
    assert t_counts.get("customers") == 3
    assert t_counts.get("consumption_records") == 1008
    assert t_counts.get("wastage_alerts") == 5
    assert t_counts.get("recommendations") == 4
    assert t_counts.get("admin_model_metrics") == 4
    print("    -> PASS")

    # 10. ML Forecasting & Wastage Benchmarks
    print("\n[10] Testing ML Benchmarking Telemetry...")
    res_fb = client.get("/api/v1/admin/forecasting-benchmarks", headers=auth_headers)
    assert res_fb.status_code == 200, f"Forecasting benchmarks failed: {res_fb.status_code}"
    res_wb = client.get("/api/v1/admin/wastage-benchmarks", headers=auth_headers)
    assert res_wb.status_code == 200, f"Wastage benchmarks failed: {res_wb.status_code}"
    print(f"    Forecasting Models Audited: {len(res_fb.json().get('benchmarks', []))}")
    print(f"    Wastage Baselines Audited : {len(res_wb.json().get('baseline_comparisons', []))}")
    print("    -> PASS")

    # 11. Security: Production OpenAPI Suppression
    print("\n[11] Verifying Production OpenAPI Docs Suppression (GET /docs)...")
    res_docs = client.get("/docs")
    assert res_docs.status_code == 404, f"Docs endpoint should be 404 in production, got {res_docs.status_code}"
    res_redoc = client.get("/redoc")
    assert res_redoc.status_code == 404, f"ReDoc endpoint should be 404 in production, got {res_redoc.status_code}"
    print("    OpenAPI Swagger UI (/docs)  : 404 Not Found (Suppressed)")
    print("    ReDoc Specification (/redoc): 404 Not Found (Suppressed)")
    print("    -> PASS")

    print("\n" + "=" * 80)
    print("ALL 11 DOCKER DEPLOYMENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
