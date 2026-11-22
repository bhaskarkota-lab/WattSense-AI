# WattSense AI™ — REST API Reference & Endpoint Specification

**Document Reference**: `WATT-DOCS-API-2026`  
**Base URL**: `http://127.0.0.1:8000/api/v1`  
**Authentication**: Bearer Token (HMAC-SHA256 JWT for Admin Endpoints)  

---

## 1. Public & Customer Endpoints

### 1.1 Liveness & Health Probe
- **Endpoint**: `GET /health`
- **Auth**: None (Public)
- **Description**: Returns lightweight operational health and database connectivity status.
- **Response (200 OK)**:
  ```json
  {
    "status": "OPERATIONAL",
    "timestamp": "2026-11-22T00:00:00Z",
    "database": "CONNECTED",
    "version": "1.0.0"
  }
  ```

### 1.2 Customer Lookup
- **Endpoint**: `POST /api/v1/customer/lookup`
- **Auth**: None (Sanitized via Consumer Number Regex `^CONS-[A-Z]{3}-[0-9]{4}$`)
- **Request Body**:
  ```json
  {
    "consumer_number": "CONS-RES-1001"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "consumer_number": "CONS-RES-1001",
    "customer_type": "Residential",
    "region": "North Grid District",
    "meter_number": "MTR-90812-N",
    "sanctioned_load_kw": 7.5,
    "tariff_rate": 6.50
  }
  ```

### 1.3 Customer Consumption Summary
- **Endpoint**: `GET /api/v1/customer/{consumer_number}/summary`
- **Response (200 OK)**:
  ```json
  {
    "consumer_number": "CONS-RES-1001",
    "total_consumed_kwh": 381.24,
    "average_daily_kwh": 27.23,
    "estimated_bill_inr": 2478.06,
    "status_headline": "Electricity Usage Within Expected Parameters"
  }
  ```

### 1.4 Customer Consumption History
- **Endpoint**: `GET /api/v1/customer/{consumer_number}/consumption`
- **Description**: Returns up to 336 hourly consumption readings for time-series chart rendering.

### 1.5 Wastage Detection Report
- **Endpoint**: `GET /api/v1/customer/{consumer_number}/wastage-report`
- **Response (200 OK)**:
  ```json
  {
    "consumer_number": "CONS-RES-2002",
    "unit": "kWh",
    "total_excess_identified": 6.10,
    "active_alerts_count": 5,
    "summary_message": "Identified 5 unusual consumption period(s) totaling an estimated 6.10 kWh of potential excess usage."
  }
  ```

### 1.6 Customer Recommendations
- **Endpoint**: `GET /api/v1/customer/{consumer_number}/recommendations`
- **Response (200 OK)**: Returns prioritized actionable efficiency suggestions.

---

## 2. Administrative Endpoints (Bearer Auth Required)

### 2.1 Administrative Authentication
- **Endpoint**: `POST /api/v1/admin/auth`
- **Request Body**:
  ```json
  {
    "passkey": "<ADMIN_SECRET_KEY>"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer",
    "expires_in_minutes": 60
  }
  ```

### 2.2 PostgreSQL Database Health & Inventory
- **Endpoint**: `GET /api/v1/admin/db-health`
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "status": "HEALTHY",
    "dialect": "postgresql",
    "database_name": "electricity_wastage_db",
    "record_counts": {
      "customers": 3,
      "consumption_records": 1008,
      "wastage_alerts": 5,
      "recommendations": 4,
      "admin_model_metrics": 4,
      "total": 1024
    }
  }
  ```

### 2.3 ML Model Forecasting Benchmarks
- **Endpoint**: `GET /api/v1/admin/forecasting-benchmarks`
- **Headers**: `Authorization: Bearer <token>`
- **Description**: Returns serialized multi-horizon evaluation telemetry for $h=1$, $h=6$, and $h=144$.
