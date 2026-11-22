"""
Phase 2 Data Preprocessing & Feature Engineering Execution Script
Runs the data engineering pipelines across all datasets.
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.logging import logger
from backend.app.services.preprocessing import PreprocessingService

def main():
    logger.info("==================================================================")
    logger.info("Starting Phase 2 Preprocessing & Feature Engineering Pipelines...")
    logger.info("==================================================================")

    # 1. Ensure Directories
    created_dirs = PreprocessingService.ensure_directories()
    logger.info(f"Verified {len(created_dirs)} data and report directories.")

    # 2. Preprocess UCI Household Dataset
    try:
        uci_report = PreprocessingService.preprocess_uci()
        logger.info(f"UCI Preprocessing Completed: {uci_report['final_rows']} rows, {uci_report['total_features']} features.")
    except Exception as e:
        logger.error(f"UCI Preprocessing failed: {e}")
        raise e

    # 3. Preprocess SGCC Dataset (or generate pipeline spec report if raw archive pending)
    sgcc_report = PreprocessingService.preprocess_sgcc()
    logger.info(f"SGCC Pipeline Status: {sgcc_report.get('status', 'PROCESSED')}")

    # 4. Audit Ancillary Dataset
    ancillary_report = PreprocessingService.audit_ancillary_dataset()
    logger.info(f"Ancillary Dataset Audit Status: {ancillary_report.get('status', 'AUDITED')}")

    logger.info("==================================================================")
    logger.info("Phase 2 Preprocessing & Feature Engineering Completed Successfully!")
    logger.info("==================================================================")

if __name__ == "__main__":
    main()
