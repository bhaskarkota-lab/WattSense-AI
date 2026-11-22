"""
Comprehensive Preprocessing & Feature Engineering Service
Implements reproducible pipelines for:
1. UCI Appliances Energy Prediction (10-minute household time series).
2. SGCC Electricity Theft Detection (Daily multi-customer benchmark).
3. Ancillary Sub-metering Inspection.

RESEARCH INTEGRITY RULES:
- Never combine datasets with incompatible intervals or units.
- Preserve raw datasets untouched.
- Do not silently delete extreme readings (flag them explicitly).
- Prevent data leakage: compute rolling/lag features using past data only.
- Record preprocessing configuration and metrics in reports.
"""
from pathlib import Path
import json
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np

from backend.app.core.config import settings
from backend.app.core.logging import logger

class PreprocessingService:
    """Orchestrates data cleaning, transformation, and feature engineering."""

    @staticmethod
    def ensure_directories():
        """Creates the required Phase 2 data and report directories."""
        dirs = [
            settings.DATA_DIR / "raw" / "uci",
            settings.DATA_DIR / "raw" / "sgcc",
            settings.DATA_DIR / "processed" / "uci",
            settings.DATA_DIR / "processed" / "sgcc",
            settings.DATA_DIR / "interim",
            settings.REPORTS_DIR / "data_quality",
            settings.REPORTS_DIR / "preprocessing",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    @classmethod
    def preprocess_uci(
        cls,
        raw_path: Optional[Path] = None,
        save_interim: bool = True,
        save_processed: bool = True
    ) -> Dict[str, Any]:
        """
        Processes the UCI Appliances Energy Prediction dataset.
        
        Steps:
        1. Parse timestamps (%Y-%m-%d %H:%M:%S).
        2. Verify 10-minute cadence and sort chronologically.
        3. Check missing and negative values.
        4. Flag outliers (IQR method) without silent record deletion.
        5. Engineer time-series forecasting features:
           - Lags: 1 (10 min), 2 (20 min), 3 (30 min), 6 (1 hr), 144 (24 hr)
           - Rolling statistics: 1h rolling mean & std, 24h rolling mean
           - Temporal cyclics: hour_sin, hour_cos, day_of_week, is_weekend
        """
        cls.ensure_directories()
        source = raw_path or (settings.DATA_DIR / "raw" / "uci" / "energydata_complete.csv")
        if not source.exists():
            raise FileNotFoundError(f"Raw UCI dataset not found at: {source}")

        logger.info(f"Loading raw UCI dataset from {source}...")
        df = pd.read_csv(source)
        initial_rows = len(df)

        # 1. Standardize timestamp
        date_str = df["date"].astype(str).str.replace(r"(\d{4}-\d{2}-\d{2})(\d{2}:)", r"\1 \2", regex=True)
        df["timestamp"] = pd.to_datetime(date_str, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # 2. Target validation: Appliances (Wh)
        df["Appliances"] = pd.to_numeric(df["Appliances"], errors="coerce")
        neg_count = int((df["Appliances"] < 0).sum())
        if neg_count > 0:
            logger.warning(f"Found {neg_count} negative readings. Masking to NaN.")
            df["Appliances"] = df["Appliances"].mask(df["Appliances"] < 0)

        # 3. Outlier identification (flag, do not delete)
        q25 = df["Appliances"].quantile(0.25)
        q75 = df["Appliances"].quantile(0.75)
        iqr = q75 - q25
        upper_fence = q75 + 1.5 * iqr
        df["is_outlier_high"] = (df["Appliances"] > upper_fence).astype(int)
        outlier_count = int(df["is_outlier_high"].sum())

        # Save interim cleaned data if requested
        interim_path = settings.DATA_DIR / "interim" / "uci_interim_cleaned.csv"
        if save_interim:
            df.to_csv(interim_path, index=False)
            logger.info(f"Saved interim cleaned data to {interim_path}")

        # 4. Feature Engineering for Time-Series Forecasting
        # Temporal features
        df["hour"] = df["timestamp"].dt.hour
        df["dayofweek"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
        df["month"] = df["timestamp"].dt.month

        # Cyclical temporal encoding
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
        df["dayofweek_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7.0)
        df["dayofweek_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7.0)

        # Lag features (past values strictly to avoid lookahead leakage)
        # 1 step = 10 min, 6 steps = 1 hr, 144 steps = 24 hr
        df["appliances_lag_1"] = df["Appliances"].shift(1)
        df["appliances_lag_2"] = df["Appliances"].shift(2)
        df["appliances_lag_3"] = df["Appliances"].shift(3)
        df["appliances_lag_6"] = df["Appliances"].shift(6)
        df["appliances_lag_144"] = df["Appliances"].shift(144)

        # Rolling statistics (using closed='left' to prevent current target leakage)
        df["appliances_roll_mean_6"] = df["Appliances"].shift(1).rolling(window=6, min_periods=1).mean()
        df["appliances_roll_std_6"] = df["Appliances"].shift(1).rolling(window=6, min_periods=1).std().fillna(0)
        df["appliances_roll_mean_144"] = df["Appliances"].shift(1).rolling(window=144, min_periods=6).mean()

        # Environmental delta features (indoor vs outdoor temp/humidity differentials)
        if "T1" in df.columns and "T_out" in df.columns:
            df["temp_diff_indoor_outdoor"] = df["T1"] - df["T_out"]
        if "RH_1" in df.columns and "RH_out" in df.columns:
            df["humidity_diff_indoor_outdoor"] = df["RH_1"] - df["RH_out"]

        # Drop initial rows where 24h lag (144 steps) is NaN
        clean_df = df.dropna().reset_index(drop=True)
        final_rows = len(clean_df)

        processed_path = settings.DATA_DIR / "processed" / "uci" / "uci_features.csv"
        if save_processed:
            clean_df.to_csv(processed_path, index=False)
            logger.info(f"Saved processed UCI features ({final_rows} rows, {clean_df.shape[1]} cols) to {processed_path}")

        report = {
            "dataset": "UCI Appliances Energy Prediction",
            "source_file": str(source),
            "processed_file": str(processed_path),
            "interim_file": str(interim_path),
            "initial_rows": initial_rows,
            "final_rows": final_rows,
            "dropped_lead_rows_due_to_lags": initial_rows - final_rows,
            "total_features": int(clean_df.shape[1]),
            "feature_categories": {
                "target": "Appliances (Wh)",
                "lags": ["appliances_lag_1", "appliances_lag_2", "appliances_lag_3", "appliances_lag_6", "appliances_lag_144"],
                "rolling": ["appliances_roll_mean_6", "appliances_roll_std_6", "appliances_roll_mean_144"],
                "cyclical_temporal": ["hour_sin", "hour_cos", "dayofweek_sin", "dayofweek_cos", "is_weekend"],
                "environmental": [c for c in clean_df.columns if c.startswith("T") or c.startswith("RH_") or "diff" in c],
                "outlier_flags": ["is_outlier_high"]
            },
            "outlier_summary": {
                "upper_fence_Wh": float(round(upper_fence, 2)),
                "flagged_high_outliers": outlier_count,
                "outlier_policy": "Retained and flagged (not deleted) to allow unusual consumption pattern detection"
            },
            "sampling_interval": "10 minutes",
            "leakage_prevention": "Strictly chronological ordering. Rolling features use closed='left' shift to exclude future values."
        }

        report_path = settings.REPORTS_DIR / "preprocessing" / "uci_preprocessing_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info(f"Generated UCI preprocessing report at {report_path}")

        return report

    @classmethod
    def preprocess_sgcc(
        cls,
        raw_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Preprocesses SGCC Electricity Theft Detection data when present.
        
        Preserves:
        - Customer IDs / consumer identifiers.
        - FLAG labels (0: Normal, 1: Theft).
        - Multi-customer matrix representation.
        - Keeps theft classification isolated from wastage.
        """
        cls.ensure_directories()
        folder = raw_dir or (settings.DATA_DIR / "raw" / "sgcc")
        candidates = list(folder.glob("*.csv")) + list(folder.glob("*.CSV")) if folder.exists() else []
        
        if not candidates:
            report = {
                "dataset": "SGCC Electricity Theft Detection",
                "status": "RAW_SOURCE_PENDING_DOWNLOAD",
                "message": (
                    "Original SGCC raw CSV files are not currently placed in data/raw/sgcc/. "
                    "Download instructions: https://github.com/henryRDlab/ElectricityTheftDetection (data.zip, data.z01, data.z02). "
                    "Synthetic customer records are NOT fabricated for SGCC."
                ),
                "pipeline_spec": {
                    "expected_format": "CSV with consumer identifier (cons_no), binary FLAG (0/1), and daily consumption columns",
                    "id_preservation": "Customer identifiers are retained for auditing",
                    "cleaning_strategy": "Negative values masked, per-customer median imputation to avoid cross-customer leakage",
                    "label_definition": "FLAG 1 is theft/tampering benchmark label, strictly NOT general customer wastage"
                }
            }
            report_path = settings.REPORTS_DIR / "preprocessing" / "sgcc_preprocessing_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

        source = candidates[0]
        logger.info(f"Processing SGCC raw dataset from {source}...")
        df = pd.read_csv(source, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]

        # Identify label and customer id
        label_col = next((c for c in df.columns if c.lower() in {"flag", "label", "target", "class"}), None)
        id_col = next((c for c in df.columns if c.lower() in {"cons_no", "user_id", "id", "customer_id"}), None)

        if not label_col:
            raise ValueError(f"Could not identify label column in {source}. Columns found: {list(df.columns)[:10]}")

        # Map labels
        mapping = {"0": 0, "1": 1, 0: 0, 1: 1, "正常": 0, "窃电": 1, "NORMAL": 0, "THEFT": 1}
        df["FLAG"] = df[label_col].map(mapping)

        # Preserve ID column
        if id_col:
            df["cons_no"] = df[id_col].astype(str)
        else:
            df["cons_no"] = [f"SGCC-CUST-{i:05d}" for i in range(len(df))]

        # Daily consumption columns
        excluded = {label_col, "FLAG", id_col, "cons_no"}
        daily_cols = [c for c in df.columns if c not in excluded]

        # Convert daily consumption to numeric, mask negatives
        numeric_part = df[daily_cols].apply(pd.to_numeric, errors="coerce")
        numeric_part = numeric_part.mask(numeric_part < 0)
        
        # Per-customer median imputation (avoids data leakage across customer profiles)
        customer_medians = numeric_part.median(axis=1)
        numeric_part = numeric_part.apply(lambda col: col.fillna(customer_medians))
        # Global fallback for any rows with all NaNs
        numeric_part = numeric_part.fillna(0.0)

        # Reassemble cleaned dataset preserving ID and label
        cleaned = pd.DataFrame({"cons_no": df["cons_no"], "FLAG": df["FLAG"]})
        cleaned = pd.concat([cleaned, numeric_part], axis=1)

        out_path = settings.DATA_DIR / "processed" / "sgcc" / "sgcc_clean.csv"
        cleaned.to_csv(out_path, index=False)
        logger.info(f"Saved processed SGCC dataset to {out_path} ({len(cleaned)} customers)")

        report = {
            "dataset": "SGCC Electricity Theft Detection",
            "source_file": str(source),
            "processed_file": str(out_path),
            "total_customers": len(cleaned),
            "total_days": len(daily_cols),
            "class_distribution": {str(k): int(v) for k, v in cleaned["FLAG"].value_counts().items()},
            "id_column_preserved": "cons_no",
            "label_column": "FLAG",
            "unit_note": "Daily consumption readings. Unit requires verification before comparing to kWh tariffs.",
            "theft_separation_rule": "FLAG=1 is strictly an electricity theft benchmark. It is NEVER used as a general wastage label."
        }
        report_path = settings.REPORTS_DIR / "preprocessing" / "sgcc_preprocessing_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    @classmethod
    def audit_ancillary_dataset(
        cls,
        file_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Audits ancillary sub-metering datasets."""
        cls.ensure_directories()
        source = file_path or Path("C:/Users/pavan/Downloads/electricity_dataset.csv")
        if not source.exists():
            return {"status": "NOT_FOUND", "path": str(source)}

        df = pd.read_csv(source)
        report = {
            "dataset": "Ancillary Sub-metering Dataset",
            "file_path": str(source),
            "rows": len(df),
            "columns": list(df.columns),
            "missing_values": int(df.isna().sum().sum()),
            "sampling_interval": "Undefined (No timestamp index)",
            "measurement_units": "Unlabelled numeric sub-metering (kW / Watts)",
            "cross_dataset_policy": (
                "DO NOT MERGE: Incompatible with UCI (Wh, 10-min time series) and SGCC (daily customer matrix). "
                "Can be used strictly for standalone sub-meter component demonstration."
            )
        }
        report_path = settings.REPORTS_DIR / "preprocessing" / "ancillary_preprocessing_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
