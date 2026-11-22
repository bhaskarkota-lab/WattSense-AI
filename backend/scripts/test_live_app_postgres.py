import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))

from backend.app.core.config import settings

print("=" * 70)
print("TESTING LIVE APPLICATION OPERATIONS ON POSTGRESQL")
print("=" * 70)

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", body=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

# 1. Admin Authentication
print("\n--- 1. ADMIN AUTHENTICATION ---")
status, auth_data = make_request("/api/v1/admin/auth", method="POST", body={"passkey": settings.ADMIN_SECRET_KEY})
print(f"Status: {status} | Authenticated: {auth_data.get('authenticated')}")
assert status == 200 and auth_data.get("authenticated") is True
admin_token = auth_data["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}

# 2. Admin Database Health Telemetry (Live PostgreSQL)
print("\n--- 2. ADMIN DATABASE HEALTH TELEMETRY ---")
status, health_data = make_request("/api/v1/admin/db-health", headers=admin_headers)
print(f"Status: {status}")
print(f"  • DB Health Status   : {health_data['status']}")
print(f"  • Database Dialect   : {health_data['dialect']}")
print(f"  • Database Name      : {health_data['database_name']}")
print(f"  • Active URL Masked  : {health_data['active_url_masked']}")
print(f"  • Is Fallback SQLite : {health_data['is_fallback']}")
print(f"  • Fail-Closed Active : {health_data['fail_closed_enforced']}")
print(f"  • Latency (ms)       : {health_data['latency_ms']}")
print(f"  • Table Counts       : {health_data['table_counts']}")
print(f"  • Pool Status        : {health_data['pool_status']}")

assert health_data["status"] == "HEALTHY", f"Expected HEALTHY, got {health_data['status']}"
assert health_data["dialect"] == "postgresql", f"Expected postgresql, got {health_data['dialect']}"
assert health_data["is_fallback"] is False, "Should not be on SQLite fallback!"
assert health_data["table_counts"]["customers"] == 3
assert health_data["table_counts"]["consumption_records"] == 1008
assert health_data["table_counts"]["wastage_alerts"] == 5
assert health_data["table_counts"]["recommendations"] == 4
assert health_data["table_counts"]["admin_model_metrics"] == 4

# 3. Customer Operations on PostgreSQL
print("\n--- 3. CUSTOMER OPERATIONS ---")
demo_consumers = ["CONS-RES-1001", "CONS-RES-2002", "CONS-COM-3003"]
for c_num in demo_consumers:
    status, cust_data = make_request("/api/v1/customer/lookup", method="POST", body={"consumer_number": c_num})
    print(f"Lookup {c_num}: Status={status} | Type={cust_data.get('customer_type')} | Masked Num={cust_data.get('masked_consumer_number')}")
    assert status == 200
    assert cust_data["customer_type"] in ("Residential", "Commercial", "Industrial")

    # Also test summary endpoint
    sum_status, sum_data = make_request(f"/api/v1/customer/{c_num}/summary")
    print(f"Summary {c_num}: Status={sum_status} | Headline={sum_data.get('status_headline', '')[:40]}...")
    assert sum_status == 200

# 4. Consumption History Retrieval from PostgreSQL
print("\n--- 4. CONSUMPTION HISTORY RETRIEVAL ---")
status, hist_data = make_request(f"/api/v1/customer/{demo_consumers[0]}/consumption?limit=10")
data_points = hist_data.get("data_points", [])
print(f"History Status: {status} | Data Points Returned: {len(data_points)} | Total Readings: {hist_data.get('total_readings')}")
assert status == 200
assert len(data_points) == 10
assert hist_data["total_readings"] > 0

# 5. Wastage Alert Retrieval from PostgreSQL
print("\n--- 5. WASTAGE ALERT RETRIEVAL ---")
status, wastage_data = make_request(f"/api/v1/customer/{demo_consumers[1]}/wastage-report")
events = wastage_data.get("events", [])
print(f"Wastage Report Status: {status} | Events Count={len(events)} | Total Excess Identified={wastage_data.get('total_excess_identified')}")
assert status == 200
assert len(events) > 0

# 6. Recommendation Retrieval from PostgreSQL
print("\n--- 6. RECOMMENDATION RETRIEVAL ---")
status, rec_data = make_request(f"/api/v1/customer/{demo_consumers[2]}/recommendations")
recs = rec_data.get("recommendations", [])
print(f"Recommendations Status: {status} | Recs Count: {len(recs)}")
assert status == 200
assert len(recs) > 0

# 7. Customer Verification (Token Issuance & Verification)
print("\n--- 7. CUSTOMER VERIFICATION & AUTH ---")
status, verify_resp = make_request("/api/v1/customer/verify", method="POST", body={
    "consumer_number": demo_consumers[0],
    "verification_code": "123456"
})
print(f"Customer Verify Status: {status} | Verified: {verify_resp.get('verified')}")
assert status == 200
cust_token = verify_resp.get("access_token")
assert cust_token is not None

# 8. Transaction Commit & Rollback on PostgreSQL
print("\n--- 8. TRANSACTION COMMIT & ROLLBACK ON POSTGRESQL ---")
from backend.app.db.session import get_db_context, SessionLocal
from backend.app.db.models import Customer
import time

test_consumer = f"TEST-PG-TX-{int(time.time())}"

# Test Commit
with get_db_context() as session:
    session.add(Customer(consumer_number=test_consumer, customer_type="Residential", is_demo=True))

with SessionLocal() as session:
    saved = session.query(Customer).filter_by(consumer_number=test_consumer).first()
    assert saved is not None
    print(f"Transaction Commit Verified: Created '{test_consumer}' on PostgreSQL")
    # Clean up test row
    session.delete(saved)
    session.commit()

# Test Rollback on Exception
rollback_consumer = f"TEST-PG-RB-{int(time.time())}"
try:
    with get_db_context() as session:
        session.add(Customer(consumer_number=rollback_consumer, customer_type="Residential", is_demo=True))
        session.flush()
        raise RuntimeError("Simulated transaction failure")
except RuntimeError:
    pass

with SessionLocal() as session:
    rb_check = session.query(Customer).filter_by(consumer_number=rollback_consumer).first()
    assert rb_check is None
    print(f"Transaction Rollback Verified: '{rollback_consumer}' cleanly rolled back on PostgreSQL")

print("\n" + "=" * 70)
print("ALL LIVE POSTGRESQL APPLICATION OPERATIONS COMPLETED SUCCESSFULLY!")
print("=" * 70)
