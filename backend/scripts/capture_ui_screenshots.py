"""
Automated UI Screenshot Capture Script.
Uses headless Chrome with a dedicated temporary profile to capture publication-grade
screenshots of the Customer Portal and Admin Dashboard.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "Smart_Electricity_Wastage_Real_Data" / "reports" / "screenshots"

TARGETS = [
    {
        "url": "http://127.0.0.1:8000/?consumer=CONS-RES-1001",
        "file": "01_customer_portal_normal.png",
        "desc": "Customer Portal - Normal Residential Profile (CONS-RES-1001)"
    },
    {
        "url": "http://127.0.0.1:8000/?consumer=CONS-RES-2002",
        "file": "02_customer_portal_wastage.png",
        "desc": "Customer Portal - Overnight Baseload Wastage (CONS-RES-2002)"
    },
    {
        "url": "http://127.0.0.1:8000/?consumer=CONS-COM-3003",
        "file": "03_customer_portal_commercial.png",
        "desc": "Customer Portal - Commercial Bakery Weekend Idling (CONS-COM-3003)"
    },
    {
        "url": "http://127.0.0.1:8000/?portal=admin",
        "file": "04_admin_auth_gate.png",
        "desc": "Admin & Research Hub - Passkey Authorization Gate"
    },
    {
        "url": "http://127.0.0.1:8000/?portal=admin&admin_auth=true",
        "file": "05_admin_telemetry_hub.png",
        "desc": "Admin & Research Hub - Forecasting & Wastage Telemetry Leaderboard"
    }
]

def capture_screenshots():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    temp_profile = Path(r"C:\Users\pavan\AppData\Local\Temp\chrome-ui-shots")
    
    print("=" * 70)
    print("Capturing Full-Stack UI Screenshots...")
    print(f"Target Directory: {SCREENSHOT_DIR}")
    print("=" * 70)

    for idx, target in enumerate(TARGETS, 1):
        out_file = SCREENSHOT_DIR / target["file"]
        print(f"[{idx}/5] Capturing: {target['desc']}")
        print(f"      URL: {target['url']}")
        
        args = [
            CHROME_PATH,
            "--headless=new",
            "--disable-gpu",
            f"--user-data-dir={temp_profile}_{idx}",
            f"--screenshot={out_file}",
            "--window-size=1280,1200",
            "--virtual-time-budget=3000",
            target["url"]
        ]
        
        try:
            res = subprocess.run(args, capture_output=True, text=True, timeout=20)
            if out_file.exists():
                size_kb = out_file.stat().st_size / 1024.0
                print(f"      [OK] Saved to {target['file']} ({size_kb:.1f} KB)")
            else:
                print(f"      [WARN] File not created: {res.stderr[:200]}")
        except Exception as e:
            print(f"      [ERROR] {e}")
        
        time.sleep(1)

    print("=" * 70)
    print("Screenshot capture sequence complete!")
    print("=" * 70)

if __name__ == "__main__":
    capture_screenshots()
