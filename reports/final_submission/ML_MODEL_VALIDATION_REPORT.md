# WattSense AI™ — Machine Learning Model Validation & Scientific Audit Report

**Document ID:** `WATTSENSE-ML-VAL-2026-001`  
**Evaluation Date:** November 22, 2026  
**Auditor:** Senior Machine Learning Engineer, Data Scientist & Scientific Validation Specialist  
**Project:** WattSense AI™ — Smart Electricity Wastage Detection & Consumption Intelligence System  
**Repository Root:** `Smart_Electricity_Wastage_Real_Data/`  
**Classification:** **CONDITIONALLY VALIDATED**

---

## 1. Executive Summary

An exhaustive, independent mathematical, empirical, and architectural audit of the machine learning subsystem in **WattSense AI™** was performed. The evaluation encompassed:
1. Cryptographic and structural verification of model artifacts (`best_forecaster_h1.joblib`, `best_forecaster_h6.joblib`, `best_forecaster_h144.joblib`).
2. Full dataset integrity audit of the UCI Appliances Energy Prediction dataset (19,735 raw readings at 10-minute cadence) and the State Grid Corporation of China (SGCC) theft detection benchmark.
3. Rigorous data leakage inspection across all 44 engineered predictive features, lag structures, rolling statistics, and chronological split boundaries.
4. Independent re-calculation of forecasting metrics ($\text{MAE}$, $\text{RMSE}$, $R^2$, $\text{sMAPE}$) on the strict chronological test set, compared against four distinct non-parametric and domain baselines.
5. Algorithmic verification of the Electricity Wastage Detection Engine and Persistence Filter (30-minute / 3-interval requirement).
6. Live end-to-end trace from FastAPI endpoints (`/api/v1/customer/...` and `/api/v1/admin/...`) through PostgreSQL to the in-memory inference pipeline.

### High-Level Verdict by Subsystem

| Subsystem / Horizon | Algorithm | Test $R^2$ | Test MAE | Test RMSE | Status | Key Scientific Finding |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Horizon $h=1$ (10 min)** | Ridge Regression | **0.5573** | **26.62 Wh** | **60.53 Wh** | **PASS** | Outperforms all baselines in RMSE and $R^2$; fast, stable, and deterministic. |
| **Horizon $h=6$ (1 hour)** | ExtraTrees Regressor | **0.0064** | **62.15 Wh** | **90.68 Wh** | **CONDITIONALLY VALIDATED** | Generalization degrades on unseen spring data; Time-of-Day baseline achieves lower MAE (48.01 Wh). |
| **Horizon $h=144$ (24 hours)** | ExtraTrees Regressor | **-0.3040** | **71.03 Wh** | **103.80 Wh** | **CONDITIONALLY VALIDATED** | Strong distribution shift at 24h horizon; Time-of-Day baseline ($R^2=0.1105$, MAE=47.73 Wh) outperforms tree ensemble. |
| **Wastage Detection Engine** | Conditional + Persistence | N/A | N/A | N/A | **PASS** | Correctly filters transient spikes; requires 3 consecutive 10-minute intervals (30 min); zero future leakage. |
| **FastAPI Backend Integration** | Async Uvicorn / REST | N/A | N/A | N/A | **PASS** | Live inference verified; zero hardcoded/fabricated metrics; 93/93 automated tests passing. |

---

## 2. Model Inventory

The WattSense AI project evaluated six candidate model families (V1 through V6) during the Phase 4 research lifecycle. The top-performing algorithm per horizon was selected based strictly on validation split performance and serialized into `models/consumption_forecasting/`.

### 2.1 Production Model Artifacts

| Model Version / Horizon | Artifact Filename | Algorithm | Artifact Size | Loading Status | Features ($N$) | Target Variable |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Model V3 ($h=1$)** | `best_forecaster_h1.joblib` | `Pipeline(StandardScaler, Ridge(alpha=10.0))` | 3.11 KB (3,185 B) | **SUCCESS** | 44 numerical | $\text{Appliances}_{t+1}$ (Wh) |
| **Model V5 ($h=6$)** | `best_forecaster_h6.joblib` | `ExtraTreesRegressor(n_estimators=100, max_depth=12)` | 13.43 MB (13,755,777 B) | **SUCCESS** | 44 numerical | $\text{Appliances}_{t+6}$ (Wh) |
| **Model V5 ($h=144$)** | `best_forecaster_h144.joblib` | `ExtraTreesRegressor(n_estimators=100, max_depth=12)` | 13.98 MB (14,313,489 B) | **SUCCESS** | 44 numerical | $\text{Appliances}_{t+144}$ (Wh) |

### 2.2 Model Architecture & Candidate Families Evaluated (V1–V6)

| Model Family ID | Algorithm | Preprocessing Pipeline | Primary Strengths | Limitations |
| :--- | :--- | :--- | :--- | :--- |
| **Model V1** | Non-Parametric Baselines (Persistence, Seasonal Naive, Time-of-Day) | None | Zero training cost; resilient to distribution drift. | Cannot capture multivariate weather/context interactions. |
| **Model V2** | Linear Regression | `StandardScaler()` | High interpretability; zero hyperparameters. | Prone to collinearity oscillations with 44 features. |
| **Model V3** | Ridge Regression ($L_2$ Regularization) | `StandardScaler()` | Suppresses multicollinearity; fast inference; compact artifact. | Linear assumption; cannot capture complex non-linear interactions. |
| **Model V4** | Random Forest Regressor | None (Native Tree Partitioning) | Non-linear feature interactions; robust to outliers. | Slower training; larger disk footprint (~15 MB). |
| **Model V5** | ExtraTrees Regressor | None (Extremely Randomized Trees) | Reduces variance; fast split selection; top validation score. | Prone to overfitting training seasonality under long horizons. |
| **Model V6** | HistGradientBoosting Regressor | None (Binned Histogram Boosting) | Native missing-value support; competitive accuracy. | Non-monotonic response on extreme extrapolation. |

### 2.3 Partition Sample Counts Across Horizons

The empirical dataset was partitioned strictly chronologically (70% Train, 15% Validation, 15% Test) with lead/lag boundaries:

| Horizon | Training Samples ($N_{\text{train}}$) | Validation Samples ($N_{\text{val}}$) | Test Samples ($N_{\text{test}}$) | Total Valid Samples |
| :--- | :---: | :---: | :---: | :---: |
| **$h=1$ (10 min)** | 13,713 | 2,938 | 2,939 | 19,590 |
| **$h=6$ (1 hour)** | 13,709 | 2,937 | 2,939 | 19,585 |
| **$h=144$ (24 hours)** | 13,612 | 2,917 | 2,918 | 19,447 |

---

## 3. Model Loading & Technical Verification

Each model was independently loaded into an isolated Python runtime using `joblib.load()` and evaluated against dimensionality, boundary inputs, and exception handling:

1. **Joblib Loading**: All 3 artifacts loaded without warnings or missing module errors on Python 3.12.10, scikit-learn 1.6+.
2. **Dimensionality & Features**: All models strictly require 44 numeric features matching `forecasting_metadata.json`.
3. **Missing-Value Handling**:
   - `best_forecaster_h1.joblib` (Ridge Pipeline): Scikit-learn `StandardScaler` raises `ValueError: Input X contains NaN. Ridge does not accept missing values`. Complete input is strictly required.
   - `best_forecaster_h6.joblib` and `best_forecaster_h144.joblib` (ExtraTrees): Handle `NaN` natively without crashing.
4. **Invalid Input Handling**: Passing string/object data safely raises `ValueError: could not convert string to float`.
5. **Numerical Boundedness**: Across all 2,939 test set evaluations:
   - NaN / Inf predictions: **0 (0.00%)**.
   - Negative predictions: **0 (0.00%)** on real test distributions.
   - Output range for $h=1$: $[10.27, 612.25]$ Wh.
   - Output range for $h=6$: $[52.63, 341.99]$ Wh.
   - Output range for $h=144$: $[51.49, 351.55]$ Wh.

---

## 4. Dataset Integrity & Cadence Audit

### 4.1 Raw UCI Appliances Energy Dataset
- **File Location**: `data/raw/uci/energydata_complete.csv`
- **Total Records**: 19,735 rows, 29 columns.
- **Date Range**: `2016-01-11 17:00:00` to `2016-05-27 18:00:00`.
- **Sampling Cadence**: Exactly **10 minutes** between consecutive rows. Time difference set: `{'0 days 00:10:00'}` (100% uniform).
- **Missing Values**: 0 nulls across all 19,735 rows.
- **Duplicate Timestamps**: 0 duplicate records.
- **Single Household Scope**: The UCI dataset represents a single residential house located in Stambruges, Belgium. It is used as a high-resolution 10-minute empirical benchmark and is **never** represented as observations from multiple utility customers.

### 4.2 Processed Features Dataset
- **File Location**: `data/processed/uci/uci_features.csv`
- **Total Records**: 19,591 rows, 49 columns.
- **Lead Row Handling**: Exactly 144 lead rows (24 hours) were removed to accommodate the longest lag window (`appliances_lag_144` and `appliances_roll_mean_144`).
- **Missing Values**: 0 nulls.

---

## 5. Data Leakage Assessment

A thorough audit was conducted to ensure zero lookahead data leakage:

1. **Chronological Splitting**: The dataset is sliced chronologically without random shuffling:
   $$\text{Train Index } [0 \dots 13712] < \text{Val Index } [13713 \dots 16650] < \text{Test Index } [16651 \dots 19589]$$
   Timestamps strictly satisfy $\max(T_{\text{train}}) < \min(T_{\text{val}})$ and $\max(T_{\text{val}}) < \min(T_{\text{test}})$.
2. **Lag Features**: All lag features use strictly positive integer shifts ($t-1$, $t-2$, $t-3$, $t-6$, $t-144$), representing past observations.
3. **Rolling Statistics**: Rolling statistics (`appliances_roll_mean_6`, `appliances_roll_std_6`, `appliances_roll_mean_144`) are computed on `.shift(1)` to ensure the current observation at time $t$ is excluded from the summary window.
4. **Target Shift**: The target variable is created as $y_{t+h} = \text{Appliances}_{t+h}$ via `.shift(-h)`. Features at time $t$ contain no future consumption readings.
5. **Preprocessing Leakage**: For the Ridge pipeline, `StandardScaler` is enclosed in an `sklearn.pipeline.Pipeline` object and fitted exclusively on `X_train`. Validation and test splits are only transformed.
6. **Time-of-Day Baseline**: The hourly conditional means are calculated exclusively from `df_train` and evaluated against `df_val` and `df_test`.

**Leakage Audit Conclusion**: **Zero lookahead leakage detected.**

---

## 6. Forecasting Performance & Baseline Benchmark Reconciliation

All models and four baseline algorithms were evaluated on the **identical held-out test partition** ($N_{\text{test}} = 2,939$ for $h=1, 6$; $N_{\text{test}} = 2,918$ for $h=144$):

### 6.1 Horizon $h=1$ (10 Minutes Ahead)

| Model / Baseline | MAE (Wh) | RMSE (Wh) | $R^2$ | sMAPE (%) | MAPE (%) | Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Selected ML: Ridge Regression** | **26.62** | **60.53** | **0.5573** | 22.11% | 23.80% | **Best Overall ($R^2$ & RMSE)** |
| *Baseline: Last-Observation (Persistence)* | 26.72 | 66.79 | 0.4611 | 19.75% | 21.51% | Strong short-term benchmark |
| *Baseline: Time-of-Day Average* | 48.01 | 85.66 | 0.1134 | 38.68% | 48.51% | Weak at 10m horizon |
| *Baseline: Rolling 24h Average* | 50.38 | 89.75 | 0.0268 | 43.12% | 53.23% | High lag dampening |
| *Baseline: Seasonal Naive (24h)* | 52.49 | 109.21 | -0.4410 | 37.58% | 49.24% | Poor tracking of intra-day spikes |

### 6.2 Horizon $h=6$ (1 Hour Ahead)

| Model / Baseline | MAE (Wh) | RMSE (Wh) | $R^2$ | sMAPE (%) | MAPE (%) | Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| *Baseline: Persistence* | 46.38 | 101.81 | -0.2524 | 31.02% | 38.24% | Severe error on large changes |
| *Baseline: Time-of-Day Average* | **48.01** | **85.66** | **0.1134** | **38.68%** | **48.51%** | **Best MAE Benchmark** |
| *Baseline: Rolling 24h Average* | 51.39 | 90.85 | 0.0028 | 43.98% | 54.37% | Baseline anchor |
| *Baseline: Seasonal Naive (24h)* | 52.60 | 109.63 | -0.4522 | 37.57% | 48.76% | Poor performance |
| **Selected ML: ExtraTreesRegressor** | 62.15 | 90.68 | 0.0064 | 47.98% | 74.73% | Overfitted validation seasonality |

*Validation vs Test Discrepancy Note*: On the validation split, ExtraTrees achieved $\text{MAE} = 45.57$ Wh and $R^2 = 0.1645$, successfully outperforming all baselines. However, on the held-out test split (May 2016 spring data), performance dropped to $\text{MAE} = 62.15$ Wh and $R^2 = 0.0064$.

### 6.3 Horizon $h=144$ (24 Hours Ahead)

| Model / Baseline | MAE (Wh) | RMSE (Wh) | $R^2$ | sMAPE (%) | MAPE (%) | Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| *Baseline: Time-of-Day Average* | **47.73** | **85.73** | **0.1105** | **38.55%** | **48.25%** | **Best Overall Benchmark** |
| *Baseline: Persistence* | 52.23 | 109.26 | -0.4448 | 37.08% | 48.92% | Outdated 24h reference |
| *Baseline: Seasonal Naive (24h)* | 52.23 | 109.26 | -0.4448 | 37.08% | 48.92% | Identical to persistence at 144 |
| *Baseline: Rolling 24h Average* | 53.15 | 95.75 | -0.1095 | 45.41% | 55.54% | Oversmoothed |
| **Selected ML: ExtraTreesRegressor** | 71.03 | 103.80 | -0.3040 | 50.72% | 85.43% | Negative $R^2$ on test set |

*Scientific Interpretation of $h=144$ Negative $R^2$*: Forecasting a single residential appliance load 24 hours into the future has high stochastic variance. The tree ensemble overfitted the winter/early-spring training distribution, causing negative $R^2$ on the May 2016 test set. The non-parametric Time-of-Day average baseline demonstrates higher robustness ($\text{MAE} = 47.73$ Wh, $R^2 = 0.1105$).

---

## 7. Forecasting Behaviour & Edge-Case Stability

The models were tested under six operational edge-case scenarios:

1. **Determinism Across Repeated Inference**:
   - Calling `.predict()` repeatedly with identical inputs produced bitwise identical predictions ($|\Delta| = 0.00 \times 10^0$).
2. **High Consumption Sensitivity (Simulated 800 Wh Spike)**:
   - $h=1$ (Ridge): Responds appropriately, scaling forecast to **520.88 Wh**.
   - $h=6$ (ExtraTrees): Dampens to **243.98 Wh** (expected regression to mean).
   - $h=144$ (ExtraTrees): Dampens to **180.14 Wh** (reflects long-term expectation).
3. **Standby / Baseload Sensitivity (Simulated 10 Wh Load)**:
   - $h=1$ (Ridge): Predicts **42.10 Wh** (strictly non-negative).
   - $h=6$ (ExtraTrees): Predicts **100.16 Wh** (bounded).
   - $h=144$ (ExtraTrees): Predicts **165.49 Wh** (bounded).
4. **Diurnal Cycle Tracking (Night 03:00 vs Day 14:00)**:
   - $h=1$: Night forecast **238.68 Wh** vs Day forecast **270.59 Wh**.
   - $h=6$: Night forecast **73.79 Wh** vs Day forecast **117.30 Wh**.
   - $h=144$: Night forecast **81.01 Wh** vs Day forecast **201.72 Wh** (captures diurnal peak).

---

## 8. Wastage Detection & Persistence Filtering Audit

The Electricity Wastage Detection Engine relies on a **Historical Conditional Baseline** combined with an **IQR Upper Fence** and an **Aggregated Persistence Filter**.

### 8.1 Empirical Verification of Persistence Scenarios

| Scenario Description | Tested Pattern | Alerts Triggered | Suppressed Bursts | Engine Behavior |
| :--- | :--- | :---: | :---: | :--- |
| **Normal Baseload** | 10 intervals within bounds | **0** | **0** | Normal operation; no false alerts. |
| **Isolated Spike (10 min)** | 1 interval at 250 Wh | **0** | **1** | **Suppressed**. Correctly ignored as standard appliance burst (e.g. kettle/toaster). |
| **Dual Spike (20 min)** | 2 intervals at 250 Wh | **0** | **1** | **Suppressed**. Below the 3-interval minimum threshold. |
| **3 Consecutive Intervals (30 min)** | 3 intervals at 250 Wh | **1** | **0** | **Triggered**. Event created: duration=30m, excess=450.0 Wh, severity=MEDIUM. |
| **4 Consecutive Intervals (40 min)** | 4 intervals at 250 Wh | **1** | **0** | **Triggered**. Event created: duration=40m, excess=600.0 Wh, severity=HIGH. |
| **6 Consecutive Intervals (60 min)** | 6 intervals at 300 Wh | **1** | **0** | **Triggered**. Event created: duration=60m, excess=1,200.0 Wh, severity=HIGH. |

### 8.2 SGCC Theft Benchmark Separation
- The State Grid Corporation of China (SGCC) dataset is strictly a **theft classification benchmark** containing daily readings.
- The `FLAG` attribute (1=Theft, 0=Normal) is **never** presented as general electricity wastage ground truth.
- All customer-facing messages strictly use validated terminology:
  - *"Potential excess consumption"*
  - *"Unusual consumption"*
  - *"Estimated potential excess energy"*
  - Never claims confirmed electricity theft or guaranteed monetary savings.

---

## 9. Backend Inference & API Integration

Live end-to-end integration was audited against the running FastAPI backend:

1. **Model Loading at Startup**: The application loads the three joblib models into memory via `forecasting_service.py` without disk thrashing on requests.
2. **Admin Benchmarks Endpoint** (`GET /api/v1/admin/forecasting-benchmarks`):
   - Authenticated access via `X-Admin-Key`: **HTTP 200 OK**.
   - Returns complete benchmark payload matching `forecasting_metadata.json` with 4 baselines and 5 candidate models.
   - Unauthenticated access: **HTTP 401 Unauthorized** (enforced).
3. **Customer Wastage Endpoint** (`GET /api/v1/customer/{consumer_number}/wastage-report`):
   - Verified on live customer `CONS-RES-2002`: **HTTP 200 OK**.
   - Correctly returns **5 active wastage alerts** totaling **6.10 kWh** of potential excess consumption, each detailing the persistence duration and expected baseline.
4. **Automated Test Suite**:
   - `pytest tests -q` executed from the inner application root.
   - Result: **93 passed in 14.23s (100% pass rate)**.

---

## 10. Reproducibility Audit

- **Metadata Verification**: The test metrics computed directly from the saved `.joblib` models on the held-out test split match the stored `forecasting_metadata.json` and PostgreSQL `admin_model_metrics` records with **zero delta** ($\Delta \text{MAE} = 0.0000$, $\Delta R^2 = 0.0000$).
- **Deterministic Re-execution**: Training scripts (`ml/forecasting/train_forecasting.py`, `ml/preprocessing/preprocess_all.py`) specify fixed random seeds (`random_state=42`) and deterministic sorting on timestamps.

---

## 11. Identified Issues & Technical Risks

1. **Long-Horizon Generalization Degradation ($h=6$ and $h=144$)**:
   - The ExtraTrees ensemble overfitted to the training and validation seasons (January–April). When evaluated on the unseen May test set, seasonal distribution shift caused $R^2$ to drop to $0.0064$ at $h=6$ and $-0.3040$ at $h=144$.
   - The simple Time-of-Day baseline achieved superior generalization at $h=6$ ($\text{MAE} = 48.01$ Wh) and $h=144$ ($\text{MAE} = 47.73$ Wh, $R^2 = 0.1105$).
2. **Missing Input Handling in Ridge Pipeline ($h=1$)**:
   - `StandardScaler` raises a `ValueError` if any feature contains `NaN`. The pipeline lacks an imputation step (e.g. `SimpleImputer`) prior to scaling.
3. **Unconstrained Lower Bound**:
   - While Ridge regression did not produce negative predictions on the test set, unbounded linear models can theoretically output negative values under extreme out-of-distribution inputs if not clipped.

---

## 12. Recommended Improvements

1. **Ensemble / Baseline Fallback for Long Horizons**:
   - At $h=144$, replace or ensemble the ExtraTrees model with the Time-of-Day baseline, which demonstrates superior stability across seasonal shifts.
2. **Post-Processing Non-Negativity Clipping**:
   - Add explicit domain clipping in `forecasting_service.py`:
     $$\hat{y}_{\text{final}} = \max(0.0, \hat{y}_{\text{pred}})$$
3. **Pipeline Imputation**:
   - Insert `SimpleImputer(strategy="median")` into the Ridge pipeline before `StandardScaler` to handle telemetry packet drops gracefully.

---

## 13. Final Acceptance Classification

| Evaluation Criterion | Assessed Status | Justification |
| :--- | :---: | :--- |
| **Model Correctness & Loading** | **PASS** | All artifacts load, execute, and predict deterministically without runtime errors. |
| **Data Leakage & Chronological Rigor** | **PASS** | Strict chronological boundaries; zero future lookahead in lags, rolling windows, or targets. |
| **Wastage Detection Engine** | **PASS** | Correctly distinguishes short bursts from sustained anomalies using 30-minute persistence. |
| **FastAPI Backend Integration** | **PASS** | Live REST endpoints serve real model predictions; zero fabricated data; 93/93 tests pass. |
| **Forecasting Accuracy ($h=1$)** | **PASS** | Outperforms all baselines on RMSE and $R^2$ ($R^2=0.5573$, MAE=26.62 Wh). |
| **Forecasting Generalization ($h=6, h=144$)** | **CONDITIONALLY VALIDATED** | Significant generalization loss on test partition; naive Time-of-Day baseline outperforms ML models. |
| **OVERALL PROJECT CLASSIFICATION** | **CONDITIONALLY VALIDATED** | **The system is architecturally sound and production-grade, but long-horizon ML models require baseline fallback.** |

---
*Report certified by Senior Machine Learning Validation Specialist.*  
*Submission artifact generated for academic review and faculty evaluation.*
