"""
WattSense AI™ — Safe Cleanup & Quarantine Script
1. Creates cleanup_quarantine/ directory.
2. Moves identified duplicate/obsolete candidates into quarantine with a detailed manifest.
3. Cleans disposable __pycache__ and bytecode caches.
4. Generates data/README.md and LICENSE.
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parent.parent.parent

def run_cleanup():
    print("=" * 80)
    print("WattSense AI™ — Safe Cleanup & Quarantine Process")
    print(f"Target Root: {root}")
    print("=" * 80)

    # 1. Create cleanup_quarantine directory
    quarantine_dir = root / "cleanup_quarantine"
    quarantine_dir.mkdir(exist_ok=True)
    print(f"[1] Verified Quarantine Directory: {quarantine_dir.relative_to(root)}")

    # 2. Move duplicate / obsolete candidates to quarantine
    candidates = [
        ("backend/alembic.ini", "Duplicate legacy Alembic configuration. Root alembic.ini is the single source of truth for Alembic migrations and Docker."),
        ("backend/electricity_wastage_dev.db", "Obsolete 81 KB pre-seed SQLite database. Root electricity_wastage_dev.db is the complete 282 KB source database containing all 1,024 verified records.")
    ]

    manifest_entries = []
    for rel_path, reason in candidates:
        src = root / rel_path
        dest = quarantine_dir / Path(rel_path).name
        if dest.exists():
            sz = dest.stat().st_size
            manifest_entries.append((Path(rel_path).name, rel_path, reason, sz))
            print(f"  [QUARANTINED]: Already in quarantine: {dest.name} ({sz:,} bytes)")
        elif src.exists():
            sz = src.stat().st_size
            shutil.move(str(src), str(dest))
            manifest_entries.append((Path(rel_path).name, rel_path, reason, sz))
            print(f"  [QUARANTINED]: Moved {rel_path} -> cleanup_quarantine/{dest.name} ({sz:,} bytes)")
        else:
            print(f"  [SKIPPED]: {rel_path} does not exist.")

    # Write quarantine manifest
    manifest_file = quarantine_dir / "QUARANTINE_MANIFEST.md"
    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write("# WattSense AI™ — Quarantine Manifest\n\n")
        f.write(f"**Generated**: {datetime.now(timezone.utc).isoformat()} UTC\n\n")
        f.write("The files in this directory were identified during the repository audit as duplicate or obsolete artifacts.\n")
        f.write("They have been moved here safely rather than permanently deleted to preserve auditability.\n\n")
        f.write("| Quarantined File | Original Location | Size | Reason for Quarantine |\n")
        f.write("| :--- | :--- | :---: | :--- |\n")
        for name, orig, reason, sz in manifest_entries:
            f.write(f"| `{name}` | `{orig}` | {sz:,} bytes | {reason} |\n")
        f.write("\n\n### Restoration Instructions\n")
        f.write("To restore any file, simply move it back to its original location relative to repository root.\n")

    print(f"  [MANIFEST]: Wrote {manifest_file.relative_to(root)}")

    # 3. Clean disposable caches (__pycache__, *.pyc)
    pycache_count = 0
    pyc_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if "node_modules" in dirpath or "cleanup_quarantine" in dirpath:
            continue
        for d in list(dirnames):
            if d == "__pycache__":
                target_d = Path(dirpath) / d
                try:
                    shutil.rmtree(target_d)
                    pycache_count += 1
                except Exception as e:
                    print(f"  Warning: Could not remove {target_d}: {e}")
        for f in filenames:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                target_f = Path(dirpath) / f
                try:
                    target_f.unlink()
                    pyc_count += 1
                except Exception as e:
                    print(f"  Warning: Could not remove {target_f}: {e}")

    print(f"\n[2] Cleared Disposable Clutter:")
    print(f"  - Removed {pycache_count} __pycache__ directories")
    print(f"  - Removed {pyc_count} compiled bytecode files (.pyc)")

    # 4. Create data/README.md
    data_readme = root / "data" / "README.md"
    with open(data_readme, "w", encoding="utf-8") as f:
        f.write("# WattSense AI™ — Dataset Repository Documentation\n\n")
        f.write("## 1. Overview\n")
        f.write("This directory contains the experimental datasets utilized by the WattSense AI™ platform for training multi-horizon electricity forecasting models and evaluating wastage detection baselines.\n\n")
        f.write("## 2. Dataset Structure\n\n")
        f.write("- `data/raw/uci/energydata_complete.csv`:\n")
        f.write("  - **Source**: UCI Machine Learning Repository — Appliances Energy Prediction Dataset.\n")
        f.write("  - **Context**: 10-minute continuous telemetry from a single residential household in Stambruges, Belgium over 4.5 months (19,735 observations).\n")
        f.write("  - **Academic Note**: This dataset models sub-hourly residential appliance draw and ambient indoor/outdoor climate parameters for one real residential property.\n\n")
        f.write("- `data/interim/uci_interim_cleaned.csv`:\n")
        f.write("  - Intermediate data generated by Phase 2 preprocessing, verifying strict 10-minute monotonic timestamps, missing-value imputation, and unit standardization (Wh to kWh).\n\n")
        f.write("- `data/processed/uci/uci_features.csv`:\n")
        f.write("  - Master feature store containing lag features ($t-1$, $t-6$, $t-144$), cyclical temporal encodings (hour sin/cos, day of week sin/cos), and rolling statistics strictly preventing future target leakage.\n\n")
        f.write("- `data/processed/sgcc/sgcc_clean.csv`:\n")
        f.write("  - State Grid Corporation of China (SGCC) daily smart meter consumption benchmarking data used for cross-dataset validation.\n")
    print(f"\n[3] Created Dataset Documentation: {data_readme.relative_to(root)}")

    # 5. Create LICENSE (MIT License)
    license_file = root / "LICENSE"
    with open(license_file, "w", encoding="utf-8") as f:
        f.write("MIT License\n\n")
        f.write("Copyright (c) 2026 WattSense AI Contributors\n\n")
        f.write("Permission is hereby granted, free of charge, to any person obtaining a copy\n")
        f.write("of this software and associated documentation files (the \"Software\"), to deal\n")
        f.write("in the Software without restriction, including without limitation the rights\n")
        f.write("to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n")
        f.write("copies of the Software, and to permit persons to whom the Software is\n")
        f.write("furnished to do so, subject to the following conditions:\n\n")
        f.write("The above copyright notice and this permission notice shall be included in all\n")
        f.write("copies or substantial portions of the Software.\n\n")
        f.write("THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n")
        f.write("IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n")
        f.write("FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n")
        f.write("AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n")
        f.write("LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n")
        f.write("OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n")
        f.write("SOFTWARE.\n")
    print(f"[4] Created License File: {license_file.relative_to(root)}")

    print("\n" + "=" * 80)
    print("SAFE CLEANUP & QUARANTINE COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_cleanup()
