"""
Smart Electricity Wastage Detection & Consumption Intelligence Platform
Production Application Launcher.

Starts the FastAPI server serving both the REST API (/api/v1) and
the compiled React Single-Page Application (/).
"""

import sys
import os
import webbrowser
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if project_root.name == "scripts":
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

import uvicorn

def main():
    print("=" * 70)
    print("Starting Smart Electricity Wastage Detection System...")
    print("  * Customer Portal & Admin Dashboard: http://localhost:8000")
    print("  * Interactive API Docs (Swagger):   http://localhost:8000/docs")
    print("=" * 70)

    # Launch uvicorn server
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
