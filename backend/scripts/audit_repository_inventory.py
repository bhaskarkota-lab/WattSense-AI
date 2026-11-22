"""
WattSense AI™ — Repository Audit & Inventory Script
Performs complete scanning and classification of all files and directories into Categories A through N.
"""
import os
import sys
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent

def classify_file(rel_path_str: str) -> str:
    p = rel_path_str.replace("\\", "/")
    
    # J. Temporary files / Caches
    if "__pycache__" in p or ".pytest_cache" in p or p.endswith(".pyc") or p.endswith(".pyo"):
        return "J. Temporary / Cache files"
    if p.startswith("frontend/node_modules/"):
        return "K. Generated / External dependencies (node_modules)"
    if p.startswith("frontend/dist/"):
        return "K. Generated build files (frontend/dist)"

    # N. Sensitive or confidential files
    if p == ".env" or p.endswith(".secret") or p.endswith(".key") or p.endswith(".pem"):
        return "N. Sensitive / Local environment files"

    # H. Deployment and Docker
    if p in ("Dockerfile", "docker-compose.yml", ".dockerignore") or p.startswith("nginx/"):
        return "H. Deployment & Docker infrastructure"

    # I. Configuration
    if p in (".env.example", ".env.production.example", ".gitignore", "pytest.ini", "alembic.ini") or p.endswith(".config.js") or p.endswith("package.json") or p.endswith("package-lock.json") or p.endswith("requirements.txt"):
        return "I. Project Configuration & Manifests"

    # B. Machine learning models and artifacts
    if p.startswith("models/consumption_forecasting/") or p.endswith(".joblib"):
        return "B. Machine Learning Models & Artifacts"
    if p in ("models/train_uci.py", "models/train_sgcc.py", "backend/scripts/train_forecasting.py"):
        return "B. Machine Learning Training Code"

    # C. Datasets and preprocessing
    if p.startswith("data/") or p in ("download_uci.py", "prepare_sgcc.py"):
        return "C. Datasets & Preprocessing Pipelines"

    # D. Backend and database
    if p.startswith("backend/alembic/") or p.endswith(".db") or p.startswith("backups/"):
        return "D. Database Migrations, Backups & SQLite files"
    if p.startswith("backend/app/db/"):
        return "D. Database ORM & Session Models"
    if p.startswith("backend/app/"):
        return "A. Essential Application Source Code (Backend)"
    if p.startswith("backend/scripts/"):
        return "A. Operational & Diagnostic Backend Scripts"

    # E. Frontend
    if p.startswith("frontend/src/") or p.startswith("frontend/public/") or p.startswith("frontend/index.html"):
        return "E. Frontend Source Code (React 19 / Vite)"

    # F. Tests
    if p.startswith("tests/") or p == "run_tests.bat":
        return "F. Automated Test Suites & Fixtures"

    # G. Documentation & Phase Reports
    if p.endswith(".md") or p.startswith("reports/") or p.startswith("docs/"):
        return "G. Technical Documentation & Reports"

    # Batch / shell convenience runners
    if p in ("start.bat", "start_app.py"):
        return "A. Convenience Application Launchers"

    return "L. Miscellaneous / Candidate for Review"

def scan():
    inventory = {}
    cat_counts = {}
    total_size = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        
        # Don't walk deep into node_modules or .pytest_cache for file-by-file detail to save memory
        if "node_modules" in rel_dir or ".pytest_cache" in rel_dir or "__pycache__" in rel_dir:
            continue
            
        for f in filenames:
            full_p = Path(dirpath) / f
            rel_p = str(full_p.relative_to(root)).replace("\\", "/")
            try:
                sz = full_p.stat().st_size
            except Exception:
                sz = 0
                
            cat = classify_file(rel_p)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            inventory[rel_p] = {
                "size_bytes": sz,
                "category": cat
            }
            total_files += 1
            total_size += sz

    print("=" * 80)
    print(f"WattSense AI™ — Repository File Inventory Summary")
    print(f"Total Tracked Files (excluding deep node_modules/.pytest_cache): {total_files}")
    print(f"Total Size: {total_size / (1024*1024):.2f} MB")
    print("=" * 80)
    for cat, count in sorted(cat_counts.items()):
        print(f"  [{count:3d} files] : {cat}")

    out_file = root / "reports" / "repository_inventory.json"
    with open(out_file, "w", encoding="utf-8") as out:
        json.dump(inventory, out, indent=2)
    print(f"\nSaved inventory mapping to: {out_file.relative_to(root)}")

if __name__ == "__main__":
    scan()
