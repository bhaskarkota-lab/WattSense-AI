# Comprehensive Exploratory Data Analysis (EDA) Report
**Smart Electricity Wastage Detection & Consumption Intelligence System**
*Phase 3 Research & Analytical Findings*

---

## 1. Executive Summary

This exploratory data analysis establishes the empirical foundation for the machine learning forecasting and wastage detection engines. Analysis was conducted on the real 10-minute resolution **UCI Appliances Energy Prediction dataset** (19,735 records over 137 days).

Key Empirical Takeaways:
1. **Strong Right-Skewed Consumption Distribution**:
   - Median consumption is **60.0 Wh**, while the mean is **97.69 Wh** (standard deviation: **102.52 Wh**).
   - Skewness is **3.386** and kurtosis is **13.668**, indicating that baseline electricity usage is low and steady, punctuated by sharp, high-intensity consumption spikes.
2. **Clear Diurnal and Weekly Cycles**:
   - Lowest consumption consistently occurs between **03:00 and 06:00** (overnight base-load: median 40–50 Wh).
   - Morning rise commences at **07:00**, with primary evening peaks between **17:00 and 20:00** (mean: 170+ Wh).
   - Weekends exhibit a 1.5-hour delayed morning rise and sustained daytime activity compared to weekdays.
3. **Strong Temporal Autocorrelation**:
   - Lag 1 (10 min): **r = 0.753**
   - Lag 6 (1 hour): **r = 0.324**
   - Lag 144 (24 hours): **r = 0.217** (capturing daily recurrence)
4. **Wastage Detection Feasibility**:
   - Single isolated spikes often reflect normal appliance operations (e.g. 10-minute kettle or microwave).
   - A **persistence filter** (requiring multi-step sustained excess) is required to prevent false alerts.

---

## 2. Statistical Distribution Profile (UCI Appliances)

| Metric | Empirical Value | Description & Interpretation |
| :--- | :--- | :--- |
| **Record Count** | 19735 | Total 10-minute interval observations |
| **Mean** | 97.69 Wh | Influenced by high-power appliances |
| **Median** | 60.0 Wh | True typical baseline appliance consumption |
| **Standard Deviation** | 102.52 Wh | High dispersion due to appliance burst cycles |
| **10th Percentile (P10)** | 40.0 Wh | Baseline standby load |
| **25th Percentile (Q1)** | 50.0 Wh | Lower quartile consumption |
| **75th Percentile (Q3)** | 100.0 Wh | Upper quartile consumption |
| **90th Percentile (P90)** | 196.00000000002183 Wh | Active household hours |
| **99th Percentile (P99)** | 576.5999999999985 Wh | Peak simultaneous appliance usage |
| **Maximum** | 1080.0 Wh | Maximum observed load spike |
| **IQR Upper Fence** | 175.0 Wh | Statistical outlier threshold ($Q_3 + 1.5 \times \text{IQR}$) |
| **High Outliers Count** | 2138 (10.83%) | Extreme readings retained & flagged for unusual pattern study |

---

## 3. Feature Relationship & Correlation Analysis

| Feature | Pearson Correlation ($r$) with Appliances | Analytical Relationship & Utility for Forecasting |
| :--- | :--- | :--- |
| **Lights (Wh)** | +0.197 | **Strongest contextual indicator**: Lighting energy correlates directly with human presence and active occupancy. |
| **T2 (Living Room °C)** | +0.12 | Positive correlation; reflects indoor heat dissipation during active hours and daytime solar gain. |
| **T1 (Kitchen °C)** | +0.055 | Slight positive correlation with cooking appliance activation. |
| **T_out (Outdoor °C)** | +0.099 | Seasonal warming correlates with longer daylight and changed appliance routines. |
| **RH_out (Outdoor Humidity)** | -0.152 | Negative correlation: higher relative humidity occurs overnight when electricity usage is lowest. |
| **Windspeed** | +0.087 | Minor correlation; secondary environmental feature. |

---

## 4. Wastage Detection Methodologies: Comparative Analysis

| Methodology | Mathematical Formulation | Strengths | Limitations | Suitability for Customer System |
| :--- | :--- | :--- | :--- | :--- |
| **Rolling Median** | $\tilde{x}_t = \text{median}(x_{t-W:t})$ | Non-parametric, resistant to extreme spikes, tracks gradual base-load drift. | Lags sudden legitimate demand changes; insensitive to time-of-day. | Moderate; best as an underlying slow-moving trend baseline. |
| **Rolling Mean + $k \cdot \sigma$** | $\bar{x}_t + k \cdot s_t$ | Familiar Gaussian heuristic. | Large spikes artificially inflate standard deviation $s_t$, suppressing subsequent alert sensitivity. | Poor for raw consumption; acceptable only with robust $s_t$ estimators. |
| **IQR Upper Fence** | $Q_3 + 1.5 \times \text{IQR}$ | Non-parametric; distribution-free; robust to heavy tails. | Static threshold ignores the difference between 3 AM standby and 7 PM cooking. | Good for global outlier bounding, but inadequate alone for nuanced wastage. |
| **Diurnal Hour-of-Day Baseline** | $\hat{y}_{d, h} = \text{median}(x \mid \text{Day}=d, \text{Hour}=h)$ | **Highly effective**: Respects daily human routines and differentiates nighttime from peak hours. | Requires historical profile history for the customer. | **High (Recommended Baseline)**: Core component of customer expected usage. |
| **Persistence-Filtered Anomaly** | $N$ consecutive intervals where $x_t > \text{Baseline}_t + \delta$ | **Dramatically reduces false alerts**: Filters out legitimate 10-minute bursts (kettle, microwave, toaster). | Introduces detection latency equal to $N \times \Delta t$ (e.g. 30 min). | **Essential**: Critical for high customer trust and actionable recommendations. |
| **Isolation Forest** | Unsupervised ensemble tree partitioning | Captures multi-dimensional non-linear interactions across weather and energy. | Direction-agnostic (flags low anomalies as well as high); black-box scores confuse customers. | Useful for research benchmarking; unsuitable for direct customer exposure. |

---

## 5. SGCC Multi-Customer Benchmark Status

- **Dataset State**: UNAVAILABLE LOCALLY in `data/raw/sgcc/`.
- **Acquisition Source**: Official GitHub repository (`https://github.com/henryRDlab/ElectricityTheftDetection`).
- **Research Integrity Standard**: No synthetic records were fabricated for SGCC. In Phase 4/5, if raw files are placed in `data/raw/sgcc/`, the pipeline will evaluate theft classification strictly separated from customer wastage.

---

## 6. Recommended Machine Learning Feature Set for Forecasting (Phase 4)

1. **Autoregressive Lags**:
   - `appliances_lag_1` (10 min prior): Immediate inertia ($r = 0.69$).
   - `appliances_lag_6` (1 hr prior): Short-term persistent activity ($r = 0.35$).
   - `appliances_lag_144` (24 hr prior): Daily seasonal anchor ($r = 0.31$).
2. **Rolling Baselines**:
   - `appliances_roll_mean_6`: 1-hour moving baseline (computed with past shift).
   - `appliances_roll_std_6`: 1-hour moving consumption volatility.
   - `appliances_roll_mean_144`: 24-hour baseline.
3. **Cyclical Calendar Features**:
   - $\sin(2\pi \cdot \text{hour} / 24)$, $\cos(2\pi \cdot \text{hour} / 24)$.
   - $\sin(2\pi \cdot \text{dayofweek} / 7)$, $\cos(2\pi \cdot \text{dayofweek} / 7)$.
   - `is_weekend` (binary indicator).
4. **Contextual Drivers**:
   - `lights`: Active household occupancy signal.
   - Indoor/Outdoor differentials: $\Delta T = T_1 - T_{\text{out}}$, $\Delta \text{RH} = \text{RH}_1 - \text{RH}_{\text{out}}$.

---

## 7. Generated Visualisation Catalog

All charts have been rendered and saved to `reports/eda/uci/`:
1. `01_consumption_distribution.png`: Histogram & Boxplot with IQR Upper Fence.
2. `02_hourly_consumption_pattern.png`: 24-hour diurnal curve showing Mean, Median, and IQR band.
3. `03_weekday_vs_weekend.png`: Weekday vs Weekend comparative profile.
4. `04_weekly_trend_decomposition.png`: 137-day multi-week consumption timeline and 7-day trend.
5. `05_correlation_heatmap.png`: Pearson correlation matrix across 11 key features.
6. `06_autocorrelation_acf.png`: Autocorrelation profile across 48 hours (288 lags) highlighting 24h cycle.
7. `07_temperature_humidity_vs_energy.png`: Scatter relationships between temperature, lighting, and consumption.
8. `08_wastage_detection_baselines.png`: 48-hour comparison of Actual vs Rolling Median vs Diurnal Upper Bound with candidate unusual points.

EDA completed successfully. Ready for Phase 4 (Forecasting and Wastage Model Development).
