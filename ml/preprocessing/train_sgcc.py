from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, IsolationForest, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

DATA = Path("data/processed/sgcc_clean.csv")
MODEL = Path("models/sgcc_random_forest.joblib")
REPORT = Path("reports/sgcc_metrics.json")

def main():
    if not DATA.exists():
        raise FileNotFoundError("Run `python prepare_sgcc.py` after placing SGCC CSV files in data/raw/sgcc/.")
    df = pd.read_csv(DATA)
    y = df["label"].astype(int)
    X = df.drop(columns=["label"]).apply(pd.to_numeric, errors="coerce")
    X = X.replace([float("inf"), float("-inf")], float("nan"))

    # Stratification preserves the minority theft class in the test split.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    clf = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(
            n_estimators=350, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1
        ))
    ])
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    proba = clf.predict_proba(X_test)[:, 1]
    report = classification_report(
        y_test, pred, output_dict=True, zero_division=0
    )
    metrics = {
        "dataset": "SGCC electricity theft detection dataset",
        "rows": int(len(df)),
        "features": int(X.shape[1]),
        "class_counts": {str(k): int(v) for k, v in y.value_counts().items()},
        "test_size": 0.2,
        "classification_report": report,
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "label_note": "Class 1 is the dataset's theft/anomaly label, not a direct label for general electricity wastage."
    }
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODEL)
    REPORT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Model: {MODEL}")

if __name__ == "__main__":
    main()
