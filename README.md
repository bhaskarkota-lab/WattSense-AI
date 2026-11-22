# WattSense AI™ — Smart Electricity Wastage Detection & Consumption Intelligence System

[![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.3-61DAFB.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.4-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)](https://www.docker.com/)
[![Automated Tests](https://img.shields.io/badge/Tests-93%20Passed%20(100%25)-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Project Title & Academic Overview

**WattSense AI™** is an end-to-end, enterprise-grade electricity consumption intelligence and anomalous wastage detection platform designed for smart grid utility distribution and residential customer empowerments. Combining chronological machine learning forecasting with statistical hour-of-day conditioning and multi-interval persistence filtering, WattSense AI™ identifies unusual electricity consumption patterns and converts telemetry into actionable, sanitized customer recommendations while enforcing institutional cyber-defensive controls.

---

## 2. Project Overview

Modern Advanced Metering Infrastructure (AMI) generates massive volumes of high-frequency power draw telemetry. However, traditional utility customer interfaces provide only retrospective, aggregated monthly billing statements. Consumers are unable to identify continuous background draws, equipment malfunctions, or standby leakage until substantial financial and environmental costs have accumulated. 

WattSense AI™ bridges this divide by delivering an automated, privacy-preserving analytics pipeline that:
1. Ingests sub-hourly smart meter readings.
2. Forecasts short- and long-term expected energy consumption profiles.
3. Compares actual power draw against historical behavioral baselines.
4. Filters transient spikes to prevent false-positive alert fatigue.
5. Surfaces explainable, non-accusatory energy efficiency guidance to end consumers.
6. Provides power distribution administrators with real-time grid diagnostics, data quality auditing, and model performance telemetry.

---

## 3. Problem Statement

Residential and commercial utility consumers routinely experience avoidable electricity wastage due to:
- **Standby Phantom Loads**: Continuous power draw from unmonitored electronic devices, transformers, and entertainment systems remaining in low-power standby modes.
- **Appliance Malfunctions**: Degraded HVAC compressors, refrigeration seal leaks, or faulty water heating elements drawing continuous unmodulated energy.
- **Lack of Actionable Visibility**: Customers receive raw kilowatt-hour (kWh) metrics without contextual expectation baselines or financial translation.
- **Alert Fatigue from Raw Anomalies**: Naive statistical anomaly detectors trigger excessive false alarms on standard, transient spikes (e.g. running a microwave or vacuum cleaner).

---

## 4. Project Objectives

1. **Multi-Horizon Energy Forecasting**: Develop and evaluate chronological machine learning models for short-term ($h=1$, $h=6$) and multi-day ($h=144$) load predictions without future target leakage.
2. **Persistence-Filtered Wastage Detection**: Implement expected consumption baselines coupled with an $N$-consecutive-interval persistence filter to suppress transient operational spikes while capturing sustained base-load leakage.
3. **Consumer-First Explainable Interface**: Deliver a clean, accessible web application presenting consumption findings, estimated monetary savings (₹ INR), and actionable appliance steps without exposing internal algorithms or defamatory language.
4. **Administrative Telemetry Hub**: Provide utility administrators with live database health monitoring, automated dataset quality auditing, model version tracking, and runtime configuration tuning.
5. **Production Hardening & Disaster Recovery**: Implement PostgreSQL 18.4 storage with ACID transactions, Alembic schema migrations, Docker multi-stage containerization, automated logical backups with cryptographic checksums, and OWASP security perimeter defenses.

---

## 5. Proposed Solution & Architecture

WattSense AI™ decouples raw data science research from customer-facing intelligence through a robust four-tier architecture:

```
+-----------------------------------------------------------------------------------+
|                              PRESENTATION LAYER                                   |
|   React 19 SPA | Vite 8 Bundler | Tailwind CSS | Chart.js Interactive Telemetry  |
+-----------------------------------------+-----------------------------------------+
                                          | RESTful API / JSON (CORS Restricted)
                                          v
+-----------------------------------------------------------------------------------+
|                              APPLICATION LAYER                                    |
|   FastAPI 0.115 | Uvicorn ASGI Server | Pydantic v2 Validation | Python 3.12      |
|   - Security Headers (nosniff, DENY)    - Request Size Limiting (5 MB)            |
|   - HMAC-SHA256 Token Auth              - Sliding-Window Rate Limiting (20 req/m) |
|   - TrustedHost Header Protection       - Distributed Correlation IDs             |
+--------------------+------------------------------------+-------------------------+
                     |                                    |
                     v                                    v
+------------------------------------+   +------------------------------------------+
|       MACHINE LEARNING ENGINE      |   |             DATA STORAGE LAYER           |
| - Ridge Regression Forecaster (h=1)|   | - PostgreSQL 18.4 (electricity_wastage)  |
| - ExtraTrees Regressors (h=6, 144) |   | - SQLAlchemy 2.0 ORM & Connection Pool   |
| - Hour-of-Day Conditional Baseline |   | - Alembic Versioned Migrations           |
| - Multi-Interval Persistence Filter|   | - Automated pg_dump Snapshot Utility     |
+------------------------------------+   +------------------------------------------+
```

---

## 6. Key Features

- **Automated Wastage Detection Engine**: Calculates behavioral expectations via hour-of-day conditioning and enforces a 3-interval persistence gate to isolate base-load leakage.
- **Scientifically Grounded Reporting**: Strictly replaces accusatory labels ("theft") with objective terminology ("potential excess consumption") and frames monetary benefits as non-binding estimates.
- **Cross-Tenant Isolation (IDOR Defense)**: Enforces cryptographic JWT verification token checks ensuring consumers access strictly their own utility records.
- **Sub-Second Disaster Recovery**: Tested physical restore of 1,024 records across all relational tables in **0.2918 seconds (~291.8 ms)**.
- **Containerized Orchestration**: Docker multi-stage build running as unprivileged `appuser` (UID 10001) with internal bridge network isolation for PostgreSQL.
- **Comprehensive QA Test Suite**: 93 automated unit, integration, live PostgreSQL, security, and restore test cases passing with 100% test coverage.

---

## 7. System Architecture Diagram

```mermaid
flowchart TD
    Client["Client Browser"] -->|HTTPS / TLS 1.3| Nginx["Nginx Reverse Proxy / Perimeter Gate"]
    Nginx -->|Proxy Pass :8000| App["FastAPI Application Container (appuser:10001)"]
    
    subgraph AppSecurity["Application Perimeter Defense"]
        App --> RateLimit["Sliding-Window IP Rate Limiter"]
        RateLimit --> BodyLimit["5 MB Payload Size Limiter"]
        BodyLimit --> SecHeaders["OWASP Security Headers & X-Request-ID"]
    end
    
    SecHeaders --> Router["FastAPI Router (/api/v1)"]
    Router --> CustAPI["Customer Route: Lookup, Summary, Wastage, Recommendations"]
    Router --> AdminAPI["Admin Route: Auth, DB Health, Datasets, Metrics"]
    
    CustAPI --> WastageService["Wastage Detection Engine (Baselines + Persistence)"]
    CustAPI --> ForecastService["ML Inference Engine (Ridge & ExtraTrees)"]
    
    WastageService --> DBLayer["SQLAlchemy 2.0 Session Pool"]
    AdminAPI --> DBLayer
    
    DBLayer -->|Internal Bridge wattsense_network| Postgres["PostgreSQL 18.4 Container (wattsense_postgres:5432)"]
    Postgres --> Volume[("Persistent Docker Volume postgres_data")]
```

---

## 8. Technology Stack

| Layer | Component | Version | Role in System |
| :--- | :--- | :---: | :--- |
| **Frontend** | React | 19.3.1 | Component-driven Single Page Application |
| **Bundler & Tooling** | Vite | 8.3.8 | Modern ECMAScript asset bundling & compilation |
| **Visualization** | Chart.js & react-chartjs-2 | 4.6.1 / 5.3.1 | Responsive 168-hour consumption telemetry graphs |
| **Styling** | Tailwind CSS & Lucide Icons | 3.4.1 / 1.77.0 | Accessible, responsive utility styling and badges |
| **Backend Framework** | FastAPI | 0.115.x | High-performance asynchronous Python web framework |
| **Application Server**| Uvicorn | 0.30.x | Production ASGI server with uvloop & httptools |
| **Data Validation** | Pydantic v2 | 2.9.x | Strict schema parsing, typing, and configuration hygiene |
| **Machine Learning** | Scikit-Learn, Pandas, NumPy | 1.5.x / 2.2.x | Model training, lag engineering, and feature pipelines |
| **Model Persistence** | Joblib | 1.4.x | Serialized pre-trained forecaster models |
| **Database Engine** | PostgreSQL | 18.4 | Enterprise relational database with ACID compliance |
| **ORM & Pooling** | SQLAlchemy | 2.0.36 | Context-managed sessions, parameterization, and pooling |
| **Migrations** | Alembic | 1.14.0 | Version-controlled declarative database migrations |
| **Containerization** | Docker & Docker Compose | 29.6.1 / v5.3.0| Multi-stage non-root container deployment |
| **Quality Assurance** | Pytest, Httpx, Pytest-Asyncio | 8.3.x / 0.27.x | 93-test automated regression and security suite |

---

## 9. Machine Learning Methodology

### 9.1 Multi-Horizon Problem Formulation & Empirical Metrics
Electricity forecasting predicts future power draw $y_{t+h}$ given historical observations $y_{t}, y_{t-1}, \dots$ and exogenous climate covariates $X_{t}$. All models were evaluated under strict chronological splits (70% Train, 15% Validation, 15% Held-out Test) without target leakage:
- **Short-Term Horizon ($h=1$, 10-minute ahead)**: Immediate demand scheduling utilizing Ridge Regression ($L_2$ regularization $\alpha=1.0$).
  - *Validation*: MAE = 26.96 Wh, RMSE = 59.22 Wh, $R^2 = 0.5690$, sMAPE = 24.47%.
  - *Held-out Test*: MAE = **26.62 Wh**, RMSE = **60.53 Wh**, $R^2 = \mathbf{0.5573}$, sMAPE = 22.11%.
  - *Baseline Context*: Substantially outperforms Persistence / Last Observation (Test MAE: 26.72 Wh, $R^2 = 0.4611$) and Time-of-Day Average (Test MAE: 48.01 Wh, $R^2 = 0.1134$).
- **Medium-Term Horizon ($h=6$, 1-hour ahead)**: Operational sub-hourly planning modeled via ExtraTrees Regressor ($N=100$, min_samples_split=5).
  - *Validation*: MAE = 45.57 Wh, RMSE = 82.47 Wh, $R^2 = 0.1645$, sMAPE = 36.95%.
  - *Held-out Test*: MAE = 62.15 Wh, RMSE = 90.68 Wh, $R^2 = 0.0064$, sMAPE = 47.98%.
  - *Baseline Context*: On the held-out test partition, the historical conditional **Time-of-Day Average Baseline** achieves MAE = **48.01 Wh**, RMSE = **85.66 Wh**, $R^2 = \mathbf{0.1134}$, maintaining stability under seasonal transition.
- **Daily Horizon ($h=144$, 24-hour day-ahead)**: Full day-ahead scheduling.
  - *ExtraTrees Validation*: MAE = 47.06 Wh, RMSE = 83.93 Wh, $R^2 = 0.1460$, sMAPE = 39.93%.
  - *ExtraTrees Held-out Test*: MAE = 71.03 Wh, RMSE = 103.80 Wh, $R^2 = -0.3040$, sMAPE = 50.72% (due to seasonal distribution shift from winter training to late-spring test data).
  - *Parsimonious Baseline Winner*: The historical conditional **Time-of-Day Average Baseline** achieved MAE = **47.73 Wh**, RMSE = **85.73 Wh**, $R^2 = \mathbf{0.1105}$, outperforming complex tree regressors. Consequently, WattSense AI decouples multi-horizon regression from daily baseline expectation profiling.

### 9.2 Leakage-Free Chronological Feature Engineering
Features are constructed strictly using backward-looking windows to prevent future data leakage:
- **Lag Features**: $t-1$, $t-2$, $t-3$, $t-6$, $t-144$.
- **Cyclical Temporal Encodings**: $\sin(2\pi \cdot \text{hour}/24)$, $\cos(2\pi \cdot \text{hour}/24)$, $\sin(2\pi \cdot \text{dow}/7)$, $\cos(2\pi \cdot \text{dow}/7)$.
- **Rolling Aggregations**: 6-interval and 144-interval rolling mean and variance computed over strictly causal historical partitions.

### 9.3 Expected Baselines & Persistence Filtering
Wastage detection evaluates:
$$\Delta_t = \max(0, y_t - B_t)$$
where $B_t$ is the historical conditional baseline for that hour of the day. A wastage alert is emitted only if:
$$\sum_{i=0}^{k-1} \mathbb{I}(\Delta_{t-i} > \tau) \ge k$$
where $k$ is the persistence threshold and $\tau$ is the anomaly threshold. 

**Cadence & Interval Clarification**:
- **Raw Telemetry Cadence (UCI Dataset, $\Delta t = 10\text{ min}$)**: Setting $k=3$ consecutive intervals represents **30 minutes** of sustained elevated consumption, suppressing short transient spikes (e.g. running an electric kettle or microwave for 10 minutes) while capturing sustained equipment runaways.
- **Hourly Aggregated Cadence (Smart Meter Portal, $\Delta t = 60\text{ min}$)**: Setting $k=3$ consecutive intervals represents **3 hours** of sustained load excess. In the demonstration database, high-wastage account `CONS-RES-2002` records alerts with `persistence_count=6` (representing 6 consecutive hours of nocturnal baseline leakage).

---

## 10. Dataset Information & Academic Context

WattSense AI™ evaluates its pipelines using real-world empirical energy datasets:

1. **UCI Appliances Energy Prediction Dataset**:
   - **Repository**: UCI Machine Learning Repository (Accession: Energydata Complete).
   - **Observations**: 19,735 records sampled at 10-minute resolution over 4.5 months (January 11, 2016 to May 27, 2016).
   - **Characteristics**: Sub-metered appliance power consumption (Wh) coupled with ambient indoor conditions ($T_1 \dots T_9$, $RH_1 \dots RH_9$) and local weather data from Chievres Airport station.
   - **Academic Note**: The UCI dataset captures power draw from a **single residential household** in Stambruges, Belgium. It provides deep micro-level telemetry for sub-hourly appliance draw.
2. **State Grid Corporation of China (SGCC) Dataset**:
   - **Context**: 42,372 customers sampled at daily resolution over 2.5 years.
   - **Usage**: Used for macro-level distribution benchmarks and cross-cadence behavioral validation.
3. **Demonstration Consumer Profiles**:
   - For interactive evaluation, three representative customer accounts are modeled from verified historical data without storing Personally Identifiable Information (PII):
     - `CONS-RES-1001`: Residential Suburban Home (standard, compliant usage; 0 alerts; baseline compliant).
     - `CONS-RES-2002`: Urban Apartment (persistent overnight standby base-load leakage; 5 alerts, 6.10 kWh excess; persistence count = 6).
     - `CONS-COM-3003`: Commercial Bakery & Cafe (commercial facility profile with weekend non-operational excess).

---

## 11. Database Architecture & Schema Design

The relational schema is enforced via PostgreSQL 18.4 with Alembic revision `207fa595bbc0`:

```
+--------------------------------------------------------------------------+
|                              CUSTOMERS                                   |
| PK id (Int) | consumer_number (VarChar UK) | meter_number (VarChar UK)   |
| customer_type (VarChar) | region (VarChar) | is_active (Bool)            |
| is_demo (Bool) | created_at / updated_at (Timestamps with TZ)            |
+------------------------------------+-------------------------------------+
                                     | 1:N
                                     v
+--------------------------------------------------------------------------+
|                         CONSUMPTION_RECORDS                              |
| PK id (Int) | FK customer_id (Int) | timestamp (DateTime with TZ)        |
| consumption_value (Float) | unit (VarChar: kWh) | interval_minutes (Int) |
| source_dataset (VarChar) | is_verified (Bool) | created_at (Timestamp)  |
+------------------------------------+-------------------------------------+
                                     | 1:N
                                     v
+--------------------------------------------------------------------------+
|                           WASTAGE_ALERTS                                 |
| PK id (Int) | FK customer_id (Int) | timestamp (DateTime with TZ)        |
| actual_consumption (Float) | expected_consumption (Float)                |
| potential_excess_consumption (Float) | severity (VarChar: LOW/MED/HIGH)   |
| alert_status (VarChar: NEW/RESOLVED) | persistence_count (Int)           |
+------------------------------------+-------------------------------------+
                                     | 1:N
                                     v
+--------------------------------------------------------------------------+
|                           RECOMMENDATIONS                                |
| PK id (Int) | FK customer_id (Int) | category (VarChar)                  |
| title (VarChar) | description (Text) | action_steps (Text)               |
| potential_savings_estimate (VarChar) | created_at (Timestamp)             |
+--------------------------------------------------------------------------+
```

---

## 12. Security Implementation & Defensive Controls

1. **Authentication & Token Expiration**:
   - Master administrative passkey configured exclusively via environment variables (`ADMIN_SECRET_KEY`).
   - Constant-time string comparison (`secrets.compare_digest`) prevents timing-attack side channels.
   - JWT tokens signed with HMAC-SHA256, strictly expiring after 60 minutes.
2. **Insecure Direct Object References (IDOR) Defense**:
   - Real utility customer routes enforce token subject matching (`sub == consumer_number`). Token signed for Customer A cannot query Customer B.
3. **Input Sanitization & SQLi Prevention**:
   - All database queries parameterized via SQLAlchemy 2.0 ORM.
   - Consumer identifiers validated via regex `^[A-Z0-9_\-]{3,64}$`.
4. **Denial of Service (DoS) Request Entity Limits**:
   - Incoming request bodies are restricted to **5 MB maximum** (`MAX_REQUEST_SIZE_BYTES = 5,242,880`), immediately returning `HTTP 413 Payload Too Large`.
5. **Anti-Scraping Rate Limiting**:
   - Sliding-window in-memory rate limiting throttles lookup attempts to **20 requests / minute**, returning `HTTP 429 Too Many Requests` in 8.14 ms.
6. **Defensive HTTP Security Headers**:
   - Responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
7. **Production Fail-Closed Architecture**:
   - Application configuration strictly prohibits silent fallback to SQLite when `ENVIRONMENT="production"`.

---

## 13. Installation & Local Execution Guide

### Prerequisites
- Python 3.12+ (AMD64 / x86_64)
- Node.js 20+ and npm
- PostgreSQL 18.x (or Docker)

### Step 1: Clone Repository & Set Up Virtual Environment
```bash
git clone https://github.com/your-repo/WattSense-AI.git
cd WattSense-AI/Smart_Electricity_Wastage_Real_Data

# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux / macOS
.venv\Scripts\activate          # On Windows
```

### Step 2: Install Dependencies
```bash
# Install Python backend dependencies
pip install -r requirements.txt

# Install Node.js frontend dependencies
cd frontend
npm ci
npm run build
cd ..
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` and configure your local PostgreSQL connection:
```bash
cp .env.example .env
```
Ensure `.env` contains valid credentials:
```ini
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/electricity_wastage_db
ADMIN_SECRET_KEY=replace_with_your_own_secure_random_secret
SECRET_KEY=replace_with_your_own_secure_random_secret
```

### Step 4: Run Migrations & Start Local Server
```bash
# Apply Alembic migrations
alembic upgrade head

# Start FastAPI server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://127.0.0.1:8000` to access the application.

---

## 14. Docker Deployment Instructions

WattSense AI™ includes a production-grade multi-service Docker Compose configuration:

```bash
# Build images and start containers in detached mode
docker compose up -d

# Check container status and healthchecks
docker compose ps

# View real-time container application logs
docker compose logs -f app
```

### Accessing Docker Services:
- Web Application & Customer Portal: `http://127.0.0.1:8000`
- Public Health Liveness Probe: `http://127.0.0.1:8000/health`
- Stopping Containers: `docker compose down`

---

## 15. API Documentation & Testing

### Interactive API Explorer (Development Mode Only)
When running in `ENVIRONMENT=development`, interactive OpenAPI Swagger documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

*(Note: Per security specifications, `/docs` and `/redoc` are conditionally suppressed in production mode).*

### Running the Automated Test Suite (93 Tests)
Execute the complete test suite covering unit tests, integration tests, live PostgreSQL assertions, and security regression checks:
```bash
pytest -v
```
All 93 tests execute and pass in approximately 5 seconds.

---

## 16. Disaster Recovery & Automated Backup

### Executing an Automated Physical Backup
```bash
python backend/scripts/backup_postgres.py
```
- Performs a plain-text SQL logical dump via `pg_dump`.
- Computes cryptographic SHA256 checksum for audit validation.
- Automatically enforces safe rolling retention (preserves minimum 5 snapshots).
- Stored at: `backups/postgres_backups/electricity_wastage_db_backup_<timestamp>.sql`.

### Tested Recovery Time Objective (RTO)
Logical SQL restoration of all 5 tables and 1,024 records was tested into an isolated target database (`watt_restore_verify_db`) via `psql`/`pg_restore`, achieving a measured recovery time of **0.2918 seconds (~291.8 ms)**.

**WAL Archiving & PITR Status**:
- **WAL Archiving**: Currently **disabled** (`archive_mode = off`) in the local Docker and host PostgreSQL environments.
- **Continuous PITR & 15-Minute RPO**: **Unverified**. Continuous Point-in-Time Recovery and sub-15-minute Recovery Point Objectives are documented as enterprise production recommendations and require managed cloud database clustering (e.g., AWS Aurora / GCP Cloud SQL).
- **Tested Scope**: Logical SQL snapshot generation and isolated logical database restoration have been verified. WAL-based continuous log recovery was not tested.

---

## 17. Project Limitations & Ethical Disclaimers

1. **Single-Household Telemetry (UCI Dataset)**: The primary sub-hourly experimental dataset represents telemetry from one real residential household in Belgium (Candanedo et al., 2017). While providing 19,735 high-resolution records, generalizations across differing climatic zones or industrial facilities require localized retraining.
2. **Demonstration Profiles vs. Production Accounts**: Demonstration customer profiles (`CONS-RES-1001`, `CONS-RES-2002`, `CONS-COM-3003`) are synthetic customer wrappers around verified historical intervals. No real customer names or personal identities are stored.
3. **Non-Accusatory Classification**: An anomalous consumption spike indicates unusual equipment draw, unmonitored baseline leakage, or sensor deviation. It does not constitute evidence of illegal utility diversion or electricity theft. SGCC electricity theft research remains strictly separate from customer-facing wastage detection.
4. **Estimated Financial Savings**: All monetary savings calculations are non-binding estimates modeled on standard utility tariff averages (₹7.50 / kWh).
5. **Production Readiness Boundary**: The application has been verified in a **local Docker container environment** (`wattsense_app` and `wattsense_postgres` on loopback `127.0.0.1`). Public cloud deployment, managed cloud database clustering, and cloud secret rotation remain pending.

---

## 18. Future Scope & Roadmap

- **Smart Thermostat Integration**: Bidirectional control interfacing with OpenADR / Zigbee smart plugs to automatically throttle unmonitored standby draws.
- **Deep Sequence Modeling**: Benchmarking temporal fusion transformers (TFT) and N-BEATS architectures against the current Ridge and ExtraTrees regressors.
- **High-Resolution Disaggregation (NILM)**: Integrating Non-Intrusive Load Monitoring algorithms to decompose total aggregate draw into specific appliance signatures without sub-metering hardware.
- **Cloud Managed Clustering**: Deployment on AWS ECS / Fargate with Aurora PostgreSQL Multi-AZ automated replication.

---

## 19. Academic Submission & Faculty Review Suite

| Document Name | Location | Target Audience & Contents |
| :--- | :--- | :--- |
| **Comprehensive Academic Report** | [ACADEMIC_PROJECT_REPORT.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/academic/ACADEMIC_PROJECT_REPORT.md) | 17-section IEEE/academic technical report covering problem formulation, architecture, ML modeling, and empirical findings. |
| **Teacher Demonstration Guide** | [TEACHER_DEMO_GUIDE.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/reports/final_submission/TEACHER_DEMO_GUIDE.md) | Faculty demonstration walkthrough, demo customer profiles, persistence filter defense, and viva voce Q&A. |
| **Project Abstract** | [PROJECT_ABSTRACT.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/academic/PROJECT_ABSTRACT.md) | Standalone executive abstract for examiners and evaluators. |
| **Academic References** | [REFERENCES.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/academic/REFERENCES.md) | Annotated academic bibliography, dataset citations, and regulatory standards. |
| **Final Cleanup & Certification** | [FINAL_PROJECT_CLEANUP_REPORT.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/reports/final_submission/FINAL_PROJECT_CLEANUP_REPORT.md) | Repository organization certification, physical restructuring audit, and regression test results. |
| **System Architecture** | [ARCHITECTURE.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/architecture/ARCHITECTURE.md) | Multi-tier architecture, sequence diagrams, and service boundaries. |
| **ML Methodology & Baselines** | [FORECASTING_AND_WASTAGE.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/machine_learning/FORECASTING_AND_WASTAGE.md) | Mathematical formulation of multi-horizon models, persistence filter, and error metrics. |
| **Relational Database Schema** | [DATABASE_SCHEMA.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/database/DATABASE_SCHEMA.md) | 3NF database schema, table specifications, constraints, and ER diagrams. |
| **Security & Hardening** | [SECURITY_AND_HARDENING.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/security/SECURITY_AND_HARDENING.md) | OWASP ASVS Level 2 compliance, IDOR defense, and security middleware. |
| **Installation & Setup** | [INSTALLATION_AND_SETUP.md](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/docs/installation/INSTALLATION_AND_SETUP.md) | Local development, virtualenv, Docker deployment, and testing instructions. |

---

## 20. Academic Project Details & Licensing

- **Project**: WattSense AI™ — Smart Electricity Wastage Detection & Consumption Intelligence System
- **Academic Stream**: Computer Science & Engineering / Data Science & Cloud Computing
- **Repository Maintainer**: Engineering Project Team
- **Academic Year**: 2026
- **License**: MIT Open Source License (refer to [LICENSE](file:///c:/Users/pavan/Downloads/Smart_Electricity_Wastage_Real_Data_Project/Smart_Electricity_Wastage_Real_Data/LICENSE))
