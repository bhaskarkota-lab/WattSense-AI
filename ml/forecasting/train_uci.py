from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DATA = Path("data/raw/uci/energydata_complete.csv")
OUT = Path("data/processed/uci_anomaly_results.csv")
MODEL_DIR = Path("models")
REPORT = Path("reports/uci_metrics.json")

def main():
    if not DATA.exists():
        raise FileNotFoundError("Run `python download_uci.py` first.")
    df = pd.read_csv(DATA)
    if "date" not in df or "Appliances" not in df:
        raise ValueError("Expected UCI columns 'date' and 'Appliances'.")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["Appliances"] = pd.to_numeric(df["Appliances"], errors="coerce")
    df = df.dropna(subset=["date", "Appliances"]).sort_values("date").reset_index(drop=True)

    # Appliances is measured in Wh. The model uses time and environmental variables.
    df["hour"] = df["date"].dt.hour
    df["dayofweek"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    feature_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c not in {"Appliances", "rv1", "rv2"}
    ]
    X = df[feature_cols].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    iso = Pipeline([
        ("scale", StandardScaler()),
        ("model", IsolationForest(
            n_estimators=300, contamination=0.05, random_state=42
        ))
    ])
    iso.fit(X)
    df["anomaly_prediction"] = iso.predict(X)
    df["anomaly_score"] = iso.decision_function(X)
    df["status"] = np.where(df["anomaly_prediction"] == -1, "Unusual consumption", "Normal")

    # K-Means is used for exploratory grouping, not as a labelled anomaly classifier.
    kmeans = Pipeline([
        ("scale", StandardScaler()),
        ("model", KMeans(n_clusters=3, n_init=10, random_state=42))
    ])
    df["usage_cluster"] = kmeans.fit_predict(X)

    # Time-ordered holdout regression baseline: predict appliance energy from context.
    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = df["Appliances"].iloc[:split], df["Appliances"].iloc[split:]
    reg = RandomForestRegressor(n_estimators=250, random_state=42, n_jobs=-1)
    reg.fit(X_train, y_train)
    pred = reg.predict(X_test)
    metrics = {
        "dataset": "UCI Appliances Energy Prediction",
        "rows": int(len(df)),
        "features_used": feature_cols,
        "isolation_forest_flagged": int((df["anomaly_prediction"] == -1).sum()),
        "regression_holdout": {
            "split": "first 80% train, last 20% test (time ordered)",
            "MAE_Wh": float(mean_absolute_error(y_test, pred)),
            "RMSE_Wh": float(np.sqrt(mean_squared_error(y_test, pred))),
            "R2": float(r2_score(y_test, pred))
        },
        "note": "UCI has no confirmed wastage/anomaly labels. Isolation Forest flags unusual patterns, not verified wastage."
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)
    joblib.dump(iso, MODEL_DIR / "uci_isolation_forest.joblib")
    joblib.dump(kmeans, MODEL_DIR / "uci_kmeans.joblib")
    joblib.dump(reg, MODEL_DIR / "uci_random_forest_regressor.joblib")
    REPORT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Results: {OUT}")

if __name__ == "__main__":
    main()
