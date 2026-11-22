from pathlib import Path
from backend.app.services.data_ingestion import DataIngestionService

def test_audit_uci_dataset_not_found(tmp_path):
    """Verifies graceful handling when UCI dataset file is missing."""
    fake_path = tmp_path / "non_existent.csv"
    audit = DataIngestionService.audit_uci_dataset(fake_path)
    assert audit["status"] == "NOT_FOUND"
    assert "error" in audit

def test_audit_uci_dataset_with_valid_csv(tmp_path):
    """Verifies data quality validation on a simulated clean UCI CSV."""
    csv_file = tmp_path / "test_uci.csv"
    csv_file.write_text(
        "date,Appliances,lights,T1,RH_1\n"
        "2016-01-11 17:00:00,60,30,19.89,47.596667\n"
        "2016-01-11 17:10:00,60,30,19.89,46.693333\n",
        encoding="utf-8"
    )
    audit = DataIngestionService.audit_uci_dataset(csv_file)
    assert audit["total_records"] == 2
    assert audit["features_count"] == 5
    assert audit["missing_values_count"] == 0
    assert audit["negative_values_count"] == 0
    assert audit["data_quality_status"] == "VALID"
    assert audit["unit_verified"] == "Wh (Watt-hours)"

def test_audit_sgcc_dataset_missing_folder(tmp_path):
    """Verifies graceful handling when SGCC raw folder has no files."""
    empty_folder = tmp_path / "sgcc_empty"
    empty_folder.mkdir()
    audit = DataIngestionService.audit_sgcc_dataset(empty_folder)
    assert audit["status"] == "PENDING_DOWNLOAD"
    assert audit["is_theft_dataset"] is True
