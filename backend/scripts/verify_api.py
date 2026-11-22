"""Verification script for API endpoints and database operations."""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_verification():
    print("==================================================================")
    print("Running Full API & Database Integration Verification...")
    print("==================================================================")

    with TestClient(app) as client:
        # 1. Root & Health
        r_root = client.get("/")
        assert r_root.status_code == 200
        print(f"[PASS] GET / -> Web Application HTML served successfully (Content-Type: {r_root.headers.get('content-type')})")

        r_api = client.get("/api")
        if r_api.status_code == 200:
            print(f"[PASS] GET /api -> {r_api.json()['name']}")

        r_health = client.get("/api/v1/health")
        assert r_health.status_code == 200
        print(f"[PASS] GET /api/v1/health -> Status: {r_health.json()['status']}, Engine: {r_health.json()['engine']}")

        # 2. Customer Lookup
        r_lookup = client.post("/api/v1/customer/lookup", json={"consumer_number": "CONS-RES-2002"})
        assert r_lookup.status_code == 200
        profile = r_lookup.json()
        print(f"[PASS] POST /api/v1/customer/lookup -> Consumer: {profile['consumer_number']}, Region: {profile['region']}, Demo: {profile['is_demo']}")

        # 3. Customer Consumption
        r_cons = client.get("/api/v1/customer/CONS-RES-2002/consumption?limit=50")
        assert r_cons.status_code == 200
        cons_data = r_cons.json()
        print(f"[PASS] GET /api/v1/customer/CONS-RES-2002/consumption -> {cons_data['total_readings']} readings, {len(cons_data['daily_summaries'])} daily summaries")

        # 4. Customer Wastage Report
        r_waste = client.get("/api/v1/customer/CONS-RES-2002/wastage-report")
        assert r_waste.status_code == 200
        waste_data = r_waste.json()
        print(f"[PASS] GET /api/v1/customer/CONS-RES-2002/wastage-report -> Total Excess: {waste_data['total_excess_identified']} {waste_data['unit']}, Alerts: {waste_data['active_alerts_count']}")

        # 5. Customer Recommendations
        r_recs = client.get("/api/v1/customer/CONS-RES-2002/recommendations")
        assert r_recs.status_code == 200
        recs_data = r_recs.json()
        print(f"[PASS] GET /api/v1/customer/CONS-RES-2002/recommendations -> {len(recs_data['recommendations'])} personalized recommendations")
        for rec in recs_data['recommendations']:
            print(f"       * [{rec['category']}] {rec['title']}")

        # 6. Admin Diagnostics & Health
        r_adm_health = client.get("/api/v1/admin/health")
        assert r_adm_health.status_code == 200
        adm_health = r_adm_health.json()
        print(f"[PASS] GET /api/v1/admin/health -> Status: {adm_health['status']}, Customers: {adm_health['total_customers']}, Records: {adm_health['total_consumption_records']}")

        # 7. Admin Datasets Audit
        r_adm_data = client.get("/api/v1/admin/datasets")
        assert r_adm_data.status_code == 200
        adm_data = r_adm_data.json()
        print(f"[PASS] GET /api/v1/admin/datasets -> Audited {len(adm_data['datasets'])} datasets")
        for ds in adm_data['datasets']:
            print(f"       * {ds['dataset_name']}: Status={ds.get('data_quality_status', ds.get('status'))}")

        # 8. Admin Metrics
        r_adm_metrics = client.get("/api/v1/admin/metrics")
        assert r_adm_metrics.status_code == 200
        print(f"[PASS] GET /api/v1/admin/metrics -> {len(r_adm_metrics.json())} model metric records tracked")

    print("==================================================================")
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    run_verification()
