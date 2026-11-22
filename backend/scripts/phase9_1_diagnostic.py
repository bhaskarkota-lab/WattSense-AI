import os
import sys
import hashlib
import sqlite3
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
env_file = root / ".env"
live_db = root / "electricity_wastage_dev.db"
backup_db = root / "backups" / "sqlite_backups" / "electricity_wastage_dev_backup_20261121_161948.db"

print("=" * 70)
print("PHASE 9.1 AUDIT & DIAGNOSTIC INSPECTION")
print("=" * 70)

print("\n--- TASK 1: ENV & POSTGRES CONFIGURATION ---")
db_url_configured = None
is_placeholder = False

if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url_configured = line.split("DATABASE_URL=", 1)[1]
                masked = re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", db_url_configured)
                print(f"DATABASE_URL (Masked) : {masked}")
                is_placeholder = ("postgres:postgres" in db_url_configured or 
                                  "your_secure_password" in db_url_configured or 
                                  "<" in db_url_configured)
                print(f"Is Placeholder Password : {is_placeholder}")
            elif line.startswith("ENVIRONMENT="):
                print(f"ENVIRONMENT             : {line.split('=', 1)[1]}")
            elif line.startswith("ALLOW_SQLITE_FALLBACK="):
                print(f"ALLOW_SQLITE_FALLBACK   : {line.split('=', 1)[1]}")
else:
    print("ERROR: .env file does not exist!")

# Driver availability
try:
    import psycopg2
    print(f"psycopg2 Driver Version : {psycopg2.__version__}")
except ImportError as e:
    print(f"psycopg2 Driver Error   : {e}")

# Test connection to port 5432
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect(("localhost", 5432))
    print("Port 5432 Socket Check  : OPEN (PostgreSQL is listening)")
    s.close()
except Exception as e:
    print(f"Port 5432 Socket Check  : FAILED ({e})")

# If URL is configured and not a known placeholder, test connecting with sqlalchemy/psycopg2
if db_url_configured:
    print("\nAttempting PostgreSQL connection test...")
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url_configured, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version();")).scalar()
            current_db = conn.execute(text("SELECT current_database();")).scalar()
            current_user = conn.execute(text("SELECT current_user;")).scalar()
            print("PostgreSQL Connect Status : SUCCESS!")
            print(f"PostgreSQL Version        : {res}")
            print(f"Current Database          : {current_db}")
            print(f"Current User              : {current_user}")
    except Exception as exc:
        # Mask any possible credentials from error message
        err_str = str(exc)
        masked_err = re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", err_str)
        print(f"PostgreSQL Connect Status : FAILED")
        print(f"Error Details (Masked)    : {masked_err}")

print("\n--- TASK 2: SQLITE SOURCE & BACKUP INTEGRITY ---")
def get_file_info(p):
    if not p.exists():
        return None, None
    size = p.stat().st_size
    with open(p, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    return size, sha256

live_size, live_sha = get_file_info(live_db)
backup_size, backup_sha = get_file_info(backup_db)
print(f"Live DB File   : {live_db.name} | Size: {live_size:,} bytes | SHA256: {live_sha}")
print(f"Backup DB File : {backup_db.name} | Size: {backup_size:,} bytes | SHA256: {backup_sha}")

def audit_db(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    table_stats = {}
    for t in tables:
        cur.execute(f'SELECT count(*) FROM "{t}"')
        count = cur.fetchone()[0]
        # Check null primary keys
        cur.execute(f'PRAGMA table_info("{t}")')
        cols = cur.fetchall()
        pk_cols = [c[1] for c in cols if c[5] > 0]
        table_stats[t] = {
            "count": count,
            "pk_cols": pk_cols
        }
    conn.close()
    return table_stats

live_stats = audit_db(live_db)
backup_stats = audit_db(backup_db)

print("\nLive DB Tables & Counts:")
for t, st in live_stats.items():
    print(f"  • {t:<24}: {st['count']:,} records (PK: {st['pk_cols']})")

print("\nBackup DB Tables & Counts:")
for t, st in backup_stats.items():
    print(f"  • {t:<24}: {st['count']:,} records (PK: {st['pk_cols']})")

# Check table difference
live_tables = set(live_stats.keys())
backup_tables = set(backup_stats.keys())
if live_tables != backup_tables:
    diff = live_tables.symmetric_difference(backup_tables)
    print(f"\nTable schema difference detected: {diff}")
else:
    print("\nTable schema structure is identical.")

# Compare record counts
print("\nData Count Comparison across core tables:")
core_tables = ["customers", "consumption_records", "wastage_alerts", "recommendations", "admin_model_metrics"]
all_counts_match = True
for ct in core_tables:
    lc = live_stats.get(ct, {}).get("count", 0)
    bc = backup_stats.get(ct, {}).get("count", 0)
    match_status = "IDENTICAL" if lc == bc else "DIFF"
    if lc != bc:
        all_counts_match = False
    print(f"  • {ct:<22}: Live={lc:<5} | Backup={bc:<5} | [{match_status}]")

print(f"All 5 core table counts identical: {all_counts_match}")

# Check foreign key integrity & null values in Live DB
print("\nChecking foreign key integrity in Live DB...")
conn = sqlite3.connect(live_db)
cur = conn.cursor()
cur.execute("PRAGMA foreign_key_check;")
fk_violations = cur.fetchall()
print(f"Foreign Key Violations: {len(fk_violations)}")

# Check duplicate consumer numbers
cur.execute("SELECT consumer_number, COUNT(*) FROM customers GROUP BY consumer_number HAVING COUNT(*) > 1;")
dup_customers = cur.fetchall()
print(f"Duplicate Customers: {len(dup_customers)}")

# Check duplicate consumption records (customer_id, timestamp)
cur.execute("SELECT customer_id, timestamp, COUNT(*) FROM consumption_records GROUP BY customer_id, timestamp HAVING COUNT(*) > 1;")
dup_consumption = cur.fetchall()
print(f"Duplicate Consumption Records: {len(dup_consumption)}")

# Check nulls in non-nullable columns
for ct in core_tables:
    cur.execute(f"PRAGMA table_info({ct})")
    cols = cur.fetchall()
    notnull_cols = [c[1] for c in cols if c[3] == 1]
    for c in notnull_cols:
        cur.execute(f"SELECT COUNT(*) FROM {ct} WHERE \"{c}\" IS NULL")
        null_count = cur.fetchone()[0]
        if null_count > 0:
            print(f"WARNING: Nulls detected in {ct}.{c}: {null_count}")
conn.close()
print("Integrity check completed successfully.")
