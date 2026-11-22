# WattSense AI™ — Academic References & Bibliography

**Document Reference**: `WATT-REFS-2026`  
**Academic Year**: 2026  
**Document Type**: Annotated Academic Bibliography & Citations  

---

## 1. Empirical Datasets & Provenance

1. **UCI Appliances Energy Prediction Benchmark**:
   - **Authors**: Luis M. Candanedo, Véronique Feldheim, Dominique Deramaix.
   - **Title**: *Data driven prediction models of energy use of appliances in a low-energy house*.
   - **Journal**: *Energy and Buildings*, Vol. 140, pp. 81–97, 2017.
   - **DOI**: `10.1016/j.enbuild.2017.01.083`
   - **Data Accession**: UCI Machine Learning Repository (`energydata_complete.csv`, 19,735 readings at 10-minute intervals).
   - **Scope & Provenance**: Continuous sub-hourly telemetry recorded from a single residential dwelling in Stambruges, Belgium over 4.5 months (January 11 to May 27, 2016).

2. **State Grid Corporation of China (SGCC) Smart Grid Dataset**:
   - **Institution**: State Grid Corporation of China.
   - **Reference**: *Electricity Theft Detection in Smart Grids: A Benchmark Dataset*. IEEE Transactions on Industrial Informatics, 2020.
   - **Repository**: GitHub (`henryRDlab/ElectricityTheftDetection`).
   - **Role in WattSense AI**: Used exclusively for macro-distribution auditing and cross-cadence behavioral benchmarks; strictly separated from customer-facing wastage detection.

---

## 2. Machine Learning, Time-Series Forecasting & Anomaly Detection

3. **Geurts, P., Ernst, D., & Wehenkel, L. (2006)**.
   - *Extremely randomized trees*.
   - *Machine Learning*, 63(1), 3–42.
   - *Role*: Theoretical basis for the ExtraTrees Regressor ensemble utilized in operational horizons.

4. **Hoerl, A. E., & Kennard, R. W. (1970)**.
   - *Ridge regression: Biased estimation for nonorthogonal problems*.
   - *Technometrics*, 12(1), 55–67.
   - *Role*: Mathematical basis for the $L_2$-regularized linear regressor deployed for 10-minute dispatch ($h=1$).

5. **Box, G. E., Jenkins, G. M., Reinsel, G. C., & Ljung, G. M. (2015)**.
   - *Time Series Analysis: Forecasting and Control* (5th ed.).
   - John Wiley & Sons.
   - *Role*: Principles of autoregressive modeling, temporal lag structures, and chronological train/validation/test partitioning.

6. **Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., ... & Duchesnay, É. (2011)**.
   - *Scikit-learn: Machine learning in Python*.
   - *Journal of Machine Learning Research*, 12, 2825–2830.

---

## 3. Energy Standards & Industrial Efficiency Frameworks

7. **International Organization for Standardization (ISO)**.
   - *ISO 50006:2014 — Energy management systems: Measuring energy performance using energy baselines (EnB) and energy performance indicators (EnPI)*.
   - Geneva, Switzerland: ISO.
   - *Role*: Methodological foundation for time-of-day and day-of-week conditional baseline expectation profiling.

8. **International Energy Agency (IEA)**.
   - *Standby Power and Low-Energy Devices: Tracking Clean Energy Progress*.
   - Paris, France: IEA, 2023.
   - *Role*: Empirical motivation regarding 5%–10% residential energy loss attributed to standby base-load power.

---

## 4. Software Architecture, Web Standards & Cybersecurity

9. **Open Web Application Security Project (OWASP)**.
   - *OWASP Application Security Verification Standard (ASVS) 4.0.3*.
   - OWASP Foundation, 2021.
   - *Role*: Institutional framework for perimeter hardening, Insecure Direct Object Reference (IDOR) prevention, timing attack mitigation, and request entity limits.

10. **Ramírez, Sebastián (Tiangolo)**.
    - *FastAPI: Modern, High-Performance Web Framework for Python*.
    - https://fastapi.tiangolo.com/, 2024.

11. **PostgreSQL Global Development Group**.
    - *PostgreSQL 18 Documentation: Continuous Archiving and Point-in-Time Recovery (PITR)*.
    - https://www.postgresql.org/docs/18/, 2024.
