# WattSense AI™ — Installation & System Setup Guide

**Document Reference**: `WATT-DOCS-INSTALL-2026`  

---

## 1. System Prerequisites

Before running WattSense AI™, ensure the host machine meets the following requirements:
- **Operating System**: Windows 11 / Linux (Ubuntu 22.04+) / macOS 13+
- **Python**: Python 3.12.x (AMD64)
- **Node.js**: Node.js 18+ and npm 9+
- **Database**: PostgreSQL 18.4 (or SQLite fallback for quick testing)
- **Container Runtime** (Optional): Docker Engine 24+ and Docker Compose v2+

---

## 2. Option A: Local Development Setup

### Step 1: Clone Repository & Create Virtual Environment
```bash
# Navigate to project directory
cd Smart_Electricity_Wastage_Real_Data

# Create and activate Python virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### Step 2: Install Backend Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Local Environment
```bash
cp .env.example .env
# Edit .env with your local PostgreSQL credentials or use SQLite fallback for dev
```

### Step 4: Run Database Migrations & Initial Seed
```bash
alembic upgrade head
python backend/scripts/init_db.py
```

### Step 5: Start Backend API
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 6: Start Frontend Development Server
Open a second terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 3. Option B: Docker Containerized Quick-Start

For zero-configuration container execution:
```bash
# From repository root
docker compose up -d

# Verify container health
docker ps
```
Open **`http://localhost:8000`** in your browser to access the unified Single Page Application and API.

---

## 4. Running Automated Tests

```bash
# Execute complete 93-test regression suite
pytest -v
```
