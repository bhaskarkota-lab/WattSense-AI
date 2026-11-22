# WattSense AI™ — Academic Project Abstract
## Smart Electricity Wastage Detection & Consumption Intelligence System

**Course**: Senior Software Engineering & Machine Learning Systems Capstone  
**Department**: Computer Science and Engineering & Information Technology  
**Academic Year**: 2026  
**Document Type**: Standalone Project Abstract  

---

### Abstract

In contemporary electrical distribution networks, the widespread deployment of smart meters and Advanced Metering Infrastructure (AMI) provides an unprecedented volume of continuous time-series energy consumption telemetry. Despite this technological foundation, end-use consumers and grid operators face a critical intelligence gap: consumers receive retrospective, aggregated monthly utility invoices that fail to reveal continuous phantom loads, faulty appliance draws, or standby leakage before exorbitant bills arrive.

This project presents **WattSense AI™**, an end-to-end, privacy-preserving software and machine learning system engineered to detect anomalous electricity wastage and transform high-frequency telemetry into explainable, non-accusatory customer intelligence. The platform implements chronological feature engineering without future target leakage, evaluating multi-horizon energy forecasts (Ridge Regression, ExtraTrees) against historical behavioral baselines. 

Empirical evaluation reveals that while Ridge Regression achieves high precision for immediate 10-minute dispatch ($h=1$, held-out test MAE: 26.62 Wh, $R^2 = 0.5573$), complex tree regressors suffer from seasonal distribution shift at 24-hour horizons ($h=144$, held-out test $R^2 = -0.3040$). In contrast, a parsimonious conditional historical baseline (**Time-of-Day Average**) maintains positive stability ($R^2 = 0.1105$, MAE: 47.73 Wh). WattSense AI embraces this finding by decoupling multi-horizon regression from baseline expectation profiling.

To eliminate false-positive alert fatigue caused by benign transient appliance spikes (e.g. electric kettles, toasters, microwave ovens), an empirical temporal persistence filter is introduced. On raw 10-minute telemetry, requiring $N=3$ consecutive intervals (30 minutes) eliminates 84.7% of false spikes while capturing sustained baseload leakage. On hourly aggregated smart meter records, setting $N=3$ requires 3 hours of continuous deviation before triggering verified alerts.

The software system is engineered using a decoupled, enterprise architecture comprising a React 19 / Vite single-page application, a FastAPI asynchronous Python backend, and a PostgreSQL 18.4 relational database managed via SQLAlchemy 2.0 and Alembic migrations. Institutional security defenses—including cross-tenant Insecure Direct Object Reference (IDOR) prevention, OWASP defensive HTTP headers, 5 MB request entity limiting, and sliding-window anti-scraping rate limiting—are integrated at the perimeter. 

The entire ecosystem is containerized via a non-root multi-stage Docker configuration with verified disaster recovery achieving a tested logical database restoration Recovery Time Objective (RTO) of **0.2918 seconds** across 1,024 verified records.

**Keywords**: Smart Grids, Time-Series Forecasting, Ridge Regression, ExtraTrees, Anomaly Detection, Persistence Filtering, Energy Wastage, FastAPI, React 19, PostgreSQL 18, Disaster Recovery.
