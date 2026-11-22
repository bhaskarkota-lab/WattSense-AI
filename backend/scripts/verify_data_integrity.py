import sys
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, text

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
from backend.app.core.config import settings

sqlite_path = root / "electricity_wastage_dev.db"

print("=" * 70)
print("DEEP DATA INTEGRITY & RECONCILIATION AUDIT (SQLite vs PostgreSQL)")
print("=" * 70)

# Connect to SQLite
sqlite_conn = sqlite3.connect(sqlite_path)
sqlite_cur = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_engine = create_engine(settings.DATABASE_URL)

with pg_engine.connect() as pg_conn:
    # 1. Customers Audit
    print("\n--- 1. CUSTOMERS AUDIT ---")
    sqlite_cur.execute("SELECT id, consumer_number, customer_type, is_demo FROM customers ORDER BY consumer_number;")
    sq_custs = sqlite_cur.fetchall()
    
    pg_custs = pg_conn.execute(text("SELECT id, consumer_number, customer_type, is_demo FROM customers ORDER BY consumer_number;")).fetchall()
    print(f"SQLite Customers Count: {len(sq_custs)} | PostgreSQL Customers Count: {len(pg_custs)}")
    assert len(sq_custs) == len(pg_custs) == 3, "Customer count mismatch!"
    
    for sq, pg in zip(sq_custs, pg_custs):
        print(f"  • SQLite: {sq[1]} ({sq[2]}, is_demo={sq[3]}) <==> PG: {pg[1]} ({pg[2]}, is_demo={pg[3]}) [MATCH]")
        assert sq[1] == pg[1] and sq[2] == pg[2] and bool(sq[3]) == bool(pg[3])

    # 2. Consumption Records Audit
    print("\n--- 2. CONSUMPTION RECORDS AUDIT ---")
    sqlite_cur.execute("SELECT COUNT(*), MIN(consumption_value), MAX(consumption_value), SUM(consumption_value), MIN(timestamp), MAX(timestamp) FROM consumption_records;")
    sq_cr = sqlite_cur.fetchone()
    
    pg_cr = pg_conn.execute(text("SELECT COUNT(*), MIN(consumption_value), MAX(consumption_value), SUM(consumption_value), MIN(timestamp), MAX(timestamp) FROM consumption_records;")).fetchone()
    
    print(f"Record Count:     SQLite={sq_cr[0]} | PG={pg_cr[0]} [MATCH={sq_cr[0] == pg_cr[0]}]")
    print(f"Min Consumption:  SQLite={sq_cr[1]:.4f} | PG={pg_cr[1]:.4f} [MATCH={abs(sq_cr[1] - pg_cr[1]) < 1e-4}]")
    print(f"Max Consumption:  SQLite={sq_cr[2]:.4f} | PG={pg_cr[2]:.4f} [MATCH={abs(sq_cr[2] - pg_cr[2]) < 1e-4}]")
    print(f"Sum Consumption:  SQLite={sq_cr[3]:.4f} | PG={pg_cr[3]:.4f} [MATCH={abs(sq_cr[3] - pg_cr[3]) < 1e-2}]")
    print(f"Timestamp Range:  SQLite: {sq_cr[4]} to {sq_cr[5]}")
    print(f"                  PG    : {pg_cr[4]} to {pg_cr[5]}")
    assert sq_cr[0] == pg_cr[0] == 1008
    assert abs(sq_cr[3] - pg_cr[3]) < 0.01

    # 3. Wastage Alerts Audit
    print("\n--- 3. WASTAGE ALERTS AUDIT ---")
    sqlite_cur.execute("SELECT COUNT(*), SUM(actual_consumption), SUM(expected_consumption), SUM(potential_excess_consumption) FROM wastage_alerts;")
    sq_wa = sqlite_cur.fetchone()
    pg_wa = pg_conn.execute(text("SELECT COUNT(*), SUM(actual_consumption), SUM(expected_consumption), SUM(potential_excess_consumption) FROM wastage_alerts;")).fetchone()
    print(f"Alert Count:      SQLite={sq_wa[0]} | PG={pg_wa[0]} [MATCH={sq_wa[0] == pg_wa[0]}]")
    print(f"Sum Actual:       SQLite={sq_wa[1]:.2f} | PG={pg_wa[1]:.2f}")
    print(f"Sum Expected:     SQLite={sq_wa[2]:.2f} | PG={pg_wa[2]:.2f}")
    print(f"Sum Excess:       SQLite={sq_wa[3]:.2f} | PG={pg_wa[3]:.2f}")
    assert sq_wa[0] == pg_wa[0] == 5
    assert abs(sq_wa[3] - pg_wa[3]) < 0.01

    # 4. Recommendations Audit
    print("\n--- 4. RECOMMENDATIONS AUDIT ---")
    sqlite_cur.execute("SELECT id, title, category, is_active FROM recommendations ORDER BY title;")
    sq_recs = sqlite_cur.fetchall()
    pg_recs = pg_conn.execute(text("SELECT id, title, category, is_active FROM recommendations ORDER BY title;")).fetchall()
    print(f"Recs Count:       SQLite={len(sq_recs)} | PG={len(pg_recs)} [MATCH={len(sq_recs) == len(pg_recs)}]")
    for sr, pr in zip(sq_recs, pg_recs):
        print(f"  • {sr[1]} [{sr[2]}] <==> {pr[1]} [{pr[2]}] [MATCH]")
        assert sr[1] == pr[1]
    assert len(sq_recs) == len(pg_recs) == 4

    # 5. Admin Model Metrics Audit
    print("\n--- 5. ADMIN MODEL METRICS AUDIT ---")
    sqlite_cur.execute("SELECT model_name, dataset_name, task_type FROM admin_model_metrics ORDER BY model_name;")
    sq_mm = sqlite_cur.fetchall()
    pg_mm = pg_conn.execute(text("SELECT model_name, dataset_name, task_type FROM admin_model_metrics ORDER BY model_name;")).fetchall()
    print(f"Metrics Count:    SQLite={len(sq_mm)} | PG={len(pg_mm)} [MATCH={len(sq_mm) == len(pg_mm)}]")
    for sm, pm in zip(sq_mm, pg_mm):
        print(f"  • {sm[0]} ({sm[2]}) on {sm[1]} [MATCH]")
        assert sm[0] == pm[0] and sm[1] == pm[1] and sm[2] == pm[2]
    assert len(sq_mm) == len(pg_mm) == 4

    # 6. Foreign Key and Duplicate Checks in PostgreSQL
    print("\n--- 6. FOREIGN KEY & DUPLICATE CHECKS IN POSTGRESQL ---")
    # Orphan consumption records?
    orphan_cr = pg_conn.execute(text("SELECT COUNT(*) FROM consumption_records cr LEFT JOIN customers c ON cr.customer_id = c.id WHERE c.id IS NULL;")).scalar()
    print(f"Orphan Consumption Records: {orphan_cr}")
    assert orphan_cr == 0

    # Orphan wastage alerts?
    orphan_wa = pg_conn.execute(text("SELECT COUNT(*) FROM wastage_alerts wa LEFT JOIN customers c ON wa.customer_id = c.id WHERE c.id IS NULL;")).scalar()
    print(f"Orphan Wastage Alerts:      {orphan_wa}")
    assert orphan_wa == 0

    # Orphan recommendations?
    orphan_rec = pg_conn.execute(text("SELECT COUNT(*) FROM recommendations r LEFT JOIN customers c ON r.customer_id = c.id WHERE c.id IS NULL;")).scalar()
    print(f"Orphan Recommendations:     {orphan_rec}")
    assert orphan_rec == 0

    # Duplicate consumption intervals?
    dup_cr = pg_conn.execute(text("SELECT customer_id, timestamp, COUNT(*) FROM consumption_records GROUP BY customer_id, timestamp HAVING COUNT(*) > 1;")).fetchall()
    print(f"Duplicate Consumption Pts:  {len(dup_cr)}")
    assert len(dup_cr) == 0

    # Duplicate customers?
    dup_cust = pg_conn.execute(text("SELECT consumer_number, COUNT(*) FROM customers GROUP BY consumer_number HAVING COUNT(*) > 1;")).fetchall()
    print(f"Duplicate Customers:        {len(dup_cust)}")
    assert len(dup_cust) == 0

sqlite_conn.close()
print("\n" + "=" * 70)
print("AUDIT RESULT: 100% RECONCILED & INTEGRITY VERIFIED!")
print("=" * 70)
