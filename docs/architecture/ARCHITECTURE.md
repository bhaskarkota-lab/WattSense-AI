# WattSense AI™ — System Architecture & Detailed Design

**Document Reference**: `WATT-DOCS-ARCH-2026`  
**System Version**: 1.0.0  

---

## 1. High-Level Architectural Pattern

WattSense AI™ is engineered using a decoupled, multi-tier service-oriented architecture comprising four primary tiers:
1. **Presentation Tier**: React 19 Single Page Application (SPA) bundled via Vite 8.
2. **Security & Perimeter Tier**: Nginx Reverse Proxy, security headers middleware, request entity size limiter (5 MB), and IP rate limiter.
3. **Application & Intelligence Tier**: FastAPI asynchronous Python 3.12 backend managing business logic, machine learning inference, and wastage detection.
4. **Data & Persistence Tier**: PostgreSQL 18.4 relational storage managed via SQLAlchemy 2.0 ORM and Alembic schema migrations.

```mermaid
flowchart TD
    subgraph PresentationTier["1. Presentation Layer (Browser Client)"]
        SPA["React 19 / Vite Single Page Application"]
        PortalView["Customer Intelligence Portal"]
        AdminView["Admin Diagnostic & Telemetry Hub"]
        SPA --> PortalView & AdminView
    end

    subgraph SecurityPerimeter["2. Perimeter Defense Layer"]
        Proxy["Nginx TLS 1.3 Reverse Proxy"]
        SecHeaders["Defensive Headers (X-Content-Type-Options, Frame-Options)"]
        SizeLimit["Request Entity Size Limiter (5 MB Limit)"]
        RateLimit["Sliding-Window Anti-Scraping Rate Limiter"]
        Proxy --> SecHeaders --> SizeLimit --> RateLimit
    end

    subgraph BackendTier["3. Application & Intelligence Engine (FastAPI 0.115)"]
        Gateway["API Gateway (/api/v1)"]
        AuthSvc["Cryptographic Auth Service (PBKDF2 / HMAC-SHA256)"]
        CustSvc["Customer Findings Service & IDOR Validator"]
        WastageEngine["Electricity Wastage Detection Engine"]
        ForecastSvc["Multi-Horizon Forecasting Engine (Ridge & ExtraTrees)"]
        Gateway --> AuthSvc & CustSvc
        CustSvc --> WastageEngine & ForecastSvc
    end

    subgraph PersistenceTier["4. Data & Persistence Layer"]
        ORM["SQLAlchemy 2.0 Connection Pool"]
        AlembicVer["Alembic Versioning (207fa595bbc0)"]
        PG[("PostgreSQL 18.4 (electricity_wastage_db)")]
        Volume[("Persistent Volume: postgres_data (/var/lib/postgresql)")]
        AuthSvc & CustSvc & WastageEngine --> ORM
        ORM --> AlembicVer --> PG --> Volume
    end

    PresentationTier -->|HTTPS :8000| SecurityPerimeter
    SecurityPerimeter --> Gateway
```

---

## 2. Decoupled Intelligence & Detection Flow

The machine learning and anomaly detection engine operates through a two-stage decoupled pipeline:

```mermaid
sequenceDiagram
    participant User as Consumer Browser
    participant API as Customer API Route
    participant ML as ML Forecasting Service
    participant Engine as Wastage Detection Service
    participant DB as PostgreSQL Database

    User->>API: GET /api/v1/customer/{consumer_number}/wastage-report
    API->>API: Sanitize & Validate IDOR Permissions
    API->>DB: Query 336 Hourly Consumption Readings
    DB-->>API: Return Historical Time-Series
    API->>Engine: Evaluate Consumption Series (Actual vs Expected)
    Engine->>ML: Retrieve Model Expectations (Ridge h=1, ExtraTrees h=6)
    ML-->>Engine: Return Predicted Load Vector
    Engine->>Engine: Compute Deviation: delta = max(0, actual - baseline)
    Engine->>Engine: Apply Persistence Gate (k >= 3 consecutive intervals)
    Engine-->>API: Return Sanitized Findings & Excess Metrics
    API-->>User: 200 OK (Clean Status, Avoidable Surcharges, Savings Steps)
```

---

## 3. Deployment Boundaries

- **Local Verification**: The entire architecture is packaged into a multi-stage Docker Compose deployment on loopback `127.0.0.1:8000`.
- **Cloud Readiness**: Service boundaries and stateless backend design enable zero-code container deployment to AWS ECS (Fargate) or GCP Cloud Run with Amazon Aurora or Google Cloud SQL.
