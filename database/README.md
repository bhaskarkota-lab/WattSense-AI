# WattSense AI™ — Relational Database Architecture & Backups Guide

## 1. Overview & Active Databases

WattSense AI™ utilizes an enterprise-grade relational database architecture managed through SQLAlchemy 2.0 and Alembic schema migrations:

1. **Primary Production Database**:
   - **Engine**: PostgreSQL 18.4 (UTF-8)
   - **Database Name**: `electricity_wastage_db`
   - **Schema Migration**: Alembic Revision `207fa595bbc0`
   - **Record Inventory**: **1,024 verified records** across all 5 relational tables.
2. **Development / Local Fallback Database**:
   - **Engine**: SQLite 3 (WAL mode)
   - **File Location**: `electricity_wastage_dev.db` (282,624 bytes at repository root)
   - **Safety Boundary**: SQLite fallback is strictly prohibited in production mode (`ALLOW_SQLITE_FALLBACK=False`).

---

## 2. Table Inventory & Verified Record Counts

| Relational Table | Record Count | Primary Key & Constraints | Description |
| :--- | :---: | :--- | :--- |
| **`customers`** | **3** | `id` (PK), `consumer_number` (UK), `meter_number` (UK) | Demonstration consumer profiles (`CONS-RES-1001`, `CONS-RES-2002`, `CONS-COM-3003`). No personal names stored. |
| **`consumption_records`** | **1,008** | `id` (PK), `customer_id` (FK) | Hourly consumption readings (336 readings per customer across 14 days). |
| **`wastage_alerts`** | **5** | `id` (PK), `customer_id` (FK) | Persistent excess draw alerts (`persistence_count = 6`, 1.22 kWh excess each, 6.10 kWh total excess). |
| **`recommendations`** | **4** | `id` (PK), `customer_id` (FK) | Tailored efficiency recommendations linked to customer alert categories. |
| **`admin_model_metrics`** | **4** | `id` (PK) | Audited ML model evaluation benchmarks ($h=1, 6, 144$) and metadata. |
| **Total Persisted Records** | **1,024** | **100% Verified** | **Zero Data Loss Across Migrations & Restores** |

---

## 3. Backups & Disaster Recovery Directory Layout

All physical, logical, and baseline database snapshots are authoritatively housed in the `database/backups/` directory:

```text
database/
├── README.md                          <- This database architecture & schema guide
└── backups/
    ├── postgres_backups/
    │   └── electricity_wastage_db_backup_20261121_171824.sql  <- Logical PostgreSQL SQL dump (1,024 records, 111 KB)
    ├── sqlite_backups/
    │   └── electricity_wastage_dev_backup_20261121_161948.db  <- Baseline SQLite binary snapshot (1,024 records, 282 KB)
    └── phase8_pre_remediation/                                <- Historical pre-remediation state
```

> [!NOTE]
> For container initialization and deterministic deployment, `docker-compose.yml` mounts directly from:
> `./database/backups/postgres_backups/electricity_wastage_db_backup_20261121_171824.sql` into `/docker-entrypoint-initdb.d/01_init.sql:ro`.
> This guarantees that fresh Docker database instances boot pre-populated with all 1,024 verified records.

### Tested Disaster Recovery Performance:
- **Restoration Method**: Automated logical SQL backup restoration (`psql`/`pg_restore`).
- **Target**: Isolated sandbox database (`watt_restore_verify_db`).
- **Verified Recovery Time Objective (RTO)**: **0.2918 seconds (~291.8 ms)**.
- **Data Integrity**: 100% row match across all 5 tables (1,024 / 1,024 records verified).
- **Automated Backup Scripts**:
  - `backend/scripts/backup_postgres.py` -> writes to `backups/postgres_backups/`
  - `backend/scripts/backup_sqlite.py` -> writes to `backups/sqlite_backups/`
  - `backend/scripts/restore_postgres.py` -> restores snapshots to PostgreSQL
