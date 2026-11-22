# WattSense AI™ — Backend Architecture & Service Reference

## 1. Overview

The WattSense AI™ backend is an enterprise-grade RESTful API service engineered using **FastAPI** and **SQLAlchemy 2.0**. It powers the core consumption analytics, machine learning multi-horizon forecasting, statistical wastage detection, customer portal interactions, and administrator telemetry.

The backend is built with strict security hardening complying with OWASP ASVS Level 2, production database management via PostgreSQL 18.4, and reproducible automated testing.

---

## 2. Directory Layout

```text
backend/
├── alembic/                       <- Alembic database migration environment and version revisions
│   ├── versions/                  <- Schema migration scripts (Revision 207fa595bbc0)
│   └── env.py                     <- SQLAlchemy model metadata binding & migration runner
├── app/                           <- Core application package
│   ├── api/                       <- REST API route controllers
│   │   ├── routes/
│   │   │   ├── customer.py        <- Customer portal lookup, consumption history & wastage reports
│   │   │   └── admin.py           <- Admin auth, DB health, ML benchmarks & customer inventory
│   │   └── deps.py                <- FastAPI dependency injection (DB sessions, auth guards)
│   ├── core/                      <- Application configuration, logging & security middleware
│   │   ├── config.py              <- Pydantic Settings management (reads .env)
│   │   ├── security.py            <- Timing-safe HMAC passkey verification & JWT session tokens
│   │   └── logging.py             <- Structured audit and application logging
│   ├── db/                        <- Relational persistence layer
│   │   ├── session.py             <- SQLAlchemy engine, sessionmaker, and fail-closed logic
│   │   └── base.py                <- Declarative ORM base and table metadata
│   ├── models/                    <- SQLAlchemy ORM database models
│   │   ├── customer.py            <- Customer profile entity (CONS-RES-1001, etc.)
│   │   ├── consumption.py         <- Hourly consumption readings (336 per customer)
│   │   ├── wastage_alert.py       <- Persistent excess draw alerts
│   │   ├── recommendation.py      <- Actionable efficiency recommendations
│   │   └── admin_metric.py        <- Audited ML evaluation benchmark metrics
│   ├── schemas/                   <- Pydantic request/response validation schemas
│   │   ├── customer.py            <- Masked customer response models (sanitized identifiers)
│   │   ├── wastage.py             <- Wastage detection payloads and baseline configurations
│   │   └── admin.py               <- Admin telemetry, metrics, and auth schemas
│   ├── services/                  <- Domain business logic
│   │   ├── forecasting_service.py <- Multi-horizon ML inference (Ridge h=1, ExtraTrees h=6)
│   │   ├── wastage_service.py     <- 3-interval persistence filter and dynamic baselines
│   │   └── data_ingestion.py      <- UCI and SGCC telemetry ingestion and verification
│   └── main.py                    <- FastAPI application factory, middleware & SPA static mounting
└── scripts/                       <- Operational diagnostic, migration, and verification tools
    ├── backup_postgres.py         <- Logical database snapshot generator
    ├── restore_postgres.py        <- Tested disaster recovery restore runner
    ├── migrate_sqlite_to_postgres.py <- Automated database migration script
    ├── verify_data_integrity.py   <- SQLite vs PostgreSQL row-level reconciliation
    └── test_live_docker_deployment.py <- End-to-end container integration test
```

---

## 3. Core Architectural Principles

1. **Dual-Engine Persistence with Production Isolation**:
   - **PostgreSQL 18.4** is the primary production relational database (`electricity_wastage_db`), holding 1,024 verified records.
   - **SQLite 3** (`electricity_wastage_dev.db`) is supported exclusively in local development.
   - In production mode (`ENVIRONMENT=production`), SQLite fallback is strictly blocked (`ALLOW_SQLITE_FALLBACK=False`). If PostgreSQL is unreachable, the system fails closed with HTTP 503 rather than serving stale local data.

2. **Defense-in-Depth Security**:
   - **Authentication**: Constant-time passkey verification using `hmac.compare_digest` prevents timing-based side-channel attacks.
   - **Session Integrity**: Ephemeral, cryptographically signed JSON Web Tokens (HMAC-SHA256, 15-minute expiry) issued for administrative operations.
   - **Information Leak Prevention**: Customer identifiers are masked (`CONS-***-1001`), database connection URIs are scrubbed in health endpoints, and sensitive exception traces are suppressed from client responses.
   - **Perimeter Hardening**: Host header validation, Content-Security-Policy (CSP), Strict-Transport-Security (HSTS), X-Frame-Options (`DENY`), and 1 MB payload limits.

3. **Multi-Horizon Machine Learning Serving**:
   - Pre-trained serialized scikit-learn models (`ridge_h1.joblib`, `extratrees_h6.joblib`, `isolation_forest.joblib`) are loaded once into memory during service initialization.
   - Ground truth metrics: $h=1$ Ridge ($R^2 = 0.5573$), $h=6$ ExtraTrees ($R^2 = 0.0064$), and $h=144$ Time-of-Day Baseline ($R^2 = 0.1105$).
   - Statistical wastage engine enforces a 3-interval (30-minute) persistence filter to suppress transient appliance startup spikes.

---

## 4. Execution & Development Commands

### Run Standalone FastAPI Server:
```bash
# From repository root
python start_app.py
```
Or via virtualenv directly:
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Database Migrations:
```bash
# Check migration history
alembic history

# Upgrade to latest revision (Revision 207fa595bbc0)
alembic upgrade head
```

### Run Backend Tests:
```bash
pytest tests/ -v
```
