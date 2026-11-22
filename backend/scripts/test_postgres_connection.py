import os
import sys
import re
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

root = Path(__file__).resolve().parent.parent.parent
env_file = root / ".env"

print("=" * 70)
print("TESTING POSTGRESQL CONNECTIVITY & TARGET DATABASE EXISTENCE")
print("=" * 70)

db_url = None
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url = line.split("DATABASE_URL=", 1)[1]
                break

if not db_url:
    print("FATAL: DATABASE_URL not found in .env!")
    sys.exit(1)

def mask_url(url: str) -> str:
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)

print(f"Configured Target Database URL: {mask_url(db_url)}")

# Extract target db name, user, host, port
# Pattern: postgresql+psycopg2://user:pass@host:port/dbname
match = re.search(r"://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", db_url)
if not match:
    print("FATAL: Could not parse DATABASE_URL structure!")
    sys.exit(1)

user, password, host, port, target_db = match.groups()
port = port or "5432"

print(f"Target Database Name: '{target_db}' on {host}:{port} as user '{user}'")

# First, test connecting to target_db directly
print(f"\n1. Attempting connection to target database '{target_db}'...")
target_exists = False
try:
    engine = create_engine(db_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version();")).scalar()
        current_db = conn.execute(text("SELECT current_database();")).scalar()
        print(f"SUCCESS: Connected to '{current_db}'!")
        print(f"PostgreSQL Version: {ver}")
        target_exists = True
except Exception as e:
    err_msg = str(e)
    masked_err = mask_url(err_msg)
    print(f"Connection to '{target_db}' failed: {masked_err}")
    if "does not exist" in err_msg.lower():
        print(f"Database '{target_db}' does not exist on the server.")
    else:
        print(f"Non-database-existence error: {masked_err}")

# Next, test connection to default 'postgres' database to check list of all databases on this server
print("\n2. Checking existing databases on PostgreSQL instance...")
admin_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/postgres"
try:
    admin_engine = create_engine(admin_url, connect_args={"connect_timeout": 5})
    with admin_engine.connect() as conn:
        databases = [row[0] for row in conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false;")).fetchall()]
        print(f"Existing databases on instance: {databases}")
        if target_db in databases:
            print(f"CONFIRMED: Target database '{target_db}' exists in catalog.")
            target_exists = True
        else:
            print(f"ALERT: Target database '{target_db}' NOT found in catalog.")
            target_exists = False
except Exception as e:
    masked_e = mask_url(str(e))
    print(f"Connection to 'postgres' maintenance database failed: {masked_e}")

print("\n" + "=" * 70)
if target_exists:
    print(f"RESULT: READY_TO_MIGRATE - Database '{target_db}' is available and credentials are valid.")
    sys.exit(0)
else:
    print(f"RESULT: DATABASE_NOT_FOUND - Database '{target_db}' does not exist.")
    sys.exit(2)
