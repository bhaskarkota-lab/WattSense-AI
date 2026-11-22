import re
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

root = Path(__file__).resolve().parent.parent.parent
env_example = root / ".env.example"
env_file = root / ".env"

print("=" * 70)
print("CREATING POSTGRESQL DATABASE & SYNCING CREDENTIALS")
print("=" * 70)

# 1. Read DATABASE_URL from .env.example
target_url = None
with open(env_example, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("DATABASE_URL="):
            target_url = line.strip().split("=", 1)[1]
            break

if not target_url:
    print("FATAL: DATABASE_URL not found in .env.example")
    sys.exit(1)

def mask_url(url: str) -> str:
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)

print(f"Extracted DATABASE_URL: {mask_url(target_url)}")

# 2. Update .env with target_url
env_content = ""
with open(env_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("DATABASE_URL="):
            env_content += f"DATABASE_URL={target_url}\n"
        else:
            env_content += line

with open(env_file, "w", encoding="utf-8") as f:
    f.write(env_content)
print("Updated Smart_Electricity_Wastage_Real_Data/.env with verified DATABASE_URL.")

# 3. Restore .env.example placeholder
example_content = ""
with open(env_example, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("DATABASE_URL="):
            example_content += "DATABASE_URL=postgresql+psycopg2://postgres:your_secure_password@localhost:5432/electricity_wastage_db\n"
        else:
            example_content += line

with open(env_example, "w", encoding="utf-8") as f:
    f.write(example_content)
print("Restored Smart_Electricity_Wastage_Real_Data/.env.example with secure placeholder.")

# 4. Parse credentials to connect to 'postgres' maintenance DB
match = re.search(r"://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", target_url)
user, password, host, port, db_name = match.groups()
port = int(port or 5432)

print(f"Connecting to maintenance database 'postgres' to create '{db_name}'...")
conn = psycopg2.connect(
    dbname="postgres",
    user=user,
    password=password,
    host=host,
    port=port
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

# Check if db exists
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
exists = cur.fetchone()
if not exists:
    cur.execute(f'CREATE DATABASE "{db_name}" ENCODING "UTF8";')
    print(f"SUCCESS: Created database '{db_name}' with UTF8 encoding!")
else:
    print(f"Database '{db_name}' already exists.")

cur.close()
conn.close()

# 5. Verify direct connection to electricity_wastage_db via SQLAlchemy
print(f"Verifying SQLAlchemy connection to '{db_name}'...")
engine = create_engine(target_url, connect_args={"connect_timeout": 5})
with engine.connect() as test_conn:
    ver = test_conn.execute(text("SELECT version();")).scalar()
    curr_db = test_conn.execute(text("SELECT current_database();")).scalar()
    print(f"SUCCESS: Connected directly to '{curr_db}'!")
    print(f"PostgreSQL Version: {ver}")

print("\nPostgreSQL Database Setup Completed Successfully.")
