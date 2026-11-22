"""
Database Architecture & Diagnostics Tool for Phase 9.
Inspects existing SQLite database records, schema, and tests PostgreSQL connection.
Masks all credentials to comply with preservation rules.
"""
import os
import sys
import sqlite3
import socket
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.config import settings

def audit_sqlite():
    db_path = project_root / "electricity_wastage_dev.db"
    print("=" * 60)
    print(f"SQLITE SOURCE DATABASE AUDIT: {db_path}")
    print("=" * 60)
    if not db_path.exists():
        print(f"ERROR: SQLite database file not found at {db_path}")
        return {}

    size = os.path.getsize(db_path)
    print(f"File size: {size:,} bytes")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]
    
    counts = {}
    print("\nTables and Record Counts:")
    for t in sorted(tables):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        counts[t] = cnt
        print(f"  * {t:25s}: {cnt:6d} records")
        
    print("\nCustomer Breakdown:")
    cur.execute("SELECT id, consumer_number, customer_type, is_demo, meter_number FROM customers;")
    for r in cur.fetchall():
        print(f"  * ID: {r[0]}, Number: {r[1]}, Type: {r[2]}, is_demo: {bool(r[3])}, Meter: {r[4]}")
        
    conn.close()
    return counts

def check_postgres_port():
    print("\n" + "=" * 60)
    print("POSTGRESQL SERVICE NETWORK PROBE")
    print("=" * 60)
    host = "localhost"
    port = 5432
    print(f"Testing TCP connection to {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        res = sock.connect_ex((host, port))
        if res == 0:
            print(f"  * TCP socket connection to {host}:{port} SUCCEEDED. (PostgreSQL service is running and listening).")
            return True
        else:
            print(f"  * TCP socket connection to {host}:{port} FAILED (Error code {res}). Service may be stopped.")
            return False
    except Exception as e:
        print(f"  * Socket probe exception: {e}")
        return False
    finally:
        sock.close()

def check_postgres_sqlalchemy():
    print("\n" + "=" * 60)
    print("POSTGRESQL SQLALCHEMY AUTHENTICATION CHECK")
    print("=" * 60)
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
    
    url = settings.DATABASE_URL
    # Mask credentials for reporting
    if "@" in url:
        proto, rest = url.split("://", 1)
        userpass, hostdb = rest.split("@", 1)
        masked_url = f"{proto}://[REDACTED_USER_PASS]@{hostdb}"
    else:
        masked_url = url
        
    print(f"Configured URL: {masked_url}")
    print("Attempting SQLAlchemy connection with 3-second timeout...")
    
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            val = conn.execute(text("SELECT version();")).scalar()
            print("  * Authentication and Connection SUCCEEDED!")
            print(f"  * Server Version: {val[:80]}...")
            return True, "SUCCESS"
    except OperationalError as oe:
        err_msg = str(oe)
        print("  * Connection/Authentication FAILED:")
        # Sanitize error message to avoid printing passwords
        clean_err = err_msg.replace("password authentication failed", "[AUTH_FAILURE: Password authentication failed]")
        # Print first 250 characters of clean error
        lines = [line for line in clean_err.split("\n") if "password" not in line.lower() or "authentication failed" in line.lower()]
        print("    " + "\n    ".join(lines[:4]))
        return False, clean_err
    except Exception as e:
        print(f"  * Unexpected error: {type(e).__name__}: {e}")
        return False, str(e)

if __name__ == "__main__":
    audit_sqlite()
    check_postgres_port()
    check_postgres_sqlalchemy()
