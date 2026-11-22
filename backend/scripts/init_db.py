import sys
import subprocess
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import engine, init_db_tables, SessionLocal, active_db_url
from backend.app.services.data_ingestion import DataIngestionService

def main():
    logger.info("==================================================================")
    logger.info("Starting Database Initialization & Dataset Ingestion Check...")
    logger.info(f"Target Database URL: {active_db_url}")
    logger.info("==================================================================")

    # 1. Initialize Tables
    init_db_tables()

    # 2. Check and Download UCI Dataset if missing
    uci_csv = settings.DATA_DIR / "raw" / "uci" / "energydata_complete.csv"
    if not uci_csv.exists():
        logger.info(f"UCI dataset not found at {uci_csv}. Triggering scripts/download_uci.py...")
        download_script = project_root / "scripts" / "download_uci.py"
        if download_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(download_script)],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"UCI download output: {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to run download_uci.py: {e.stderr}")
        else:
            logger.warning(f"download_uci.py not found at {download_script}")
    else:
        logger.info(f"UCI dataset verified at {uci_csv}")

    # 3. Audit Datasets
    uci_audit = DataIngestionService.audit_uci_dataset()
    logger.info(f"UCI Dataset Audit: {uci_audit}")

    sgcc_audit = DataIngestionService.audit_sgcc_dataset()
    logger.info(f"SGCC Dataset Audit: {sgcc_audit}")

    # 4. Seed Database Demonstration Profiles (strictly tagged is_demo=True)
    with SessionLocal() as db:
        seed_result = DataIngestionService.seed_initial_database_data(db)
        logger.info(f"Database Seeding Result: {seed_result}")

    logger.info("==================================================================")
    logger.info("Database initialization completed successfully.")
    logger.info("==================================================================")

if __name__ == "__main__":
    main()
