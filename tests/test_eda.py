from pathlib import Path
from backend.app.core.config import settings

def test_eda_report_and_charts_exist():
    """Verifies that all Phase 3 EDA visualisations and report files exist and are non-empty."""
    eda_dir = settings.REPORTS_DIR / "eda"
    assert (eda_dir / "eda_comprehensive_report.md").exists()
    
    report_text = (eda_dir / "eda_comprehensive_report.md").read_text(encoding="utf-8")
    assert "Distribution of Appliance Consumption" in report_text or "Statistical Distribution Profile" in report_text
    assert "Diurnal" in report_text
    assert "Persistence-Filtered" in report_text

    # Verify all 8 UCI visualisations
    uci_charts = [
        "01_consumption_distribution.png",
        "02_hourly_consumption_pattern.png",
        "03_weekday_vs_weekend.png",
        "04_weekly_trend_decomposition.png",
        "05_correlation_heatmap.png",
        "06_autocorrelation_acf.png",
        "07_temperature_humidity_vs_energy.png",
        "08_wastage_detection_baselines.png"
    ]
    uci_dir = eda_dir / "uci"
    for chart in uci_charts:
        chart_p = uci_dir / chart
        assert chart_p.exists(), f"Missing chart {chart}"
        assert chart_p.stat().st_size > 10000, f"Chart {chart} appears too small or corrupt"

def test_sgcc_status_documentation():
    """Verifies that SGCC local unavailability is properly documented without fabricated data."""
    sgcc_status_file = settings.REPORTS_DIR / "eda" / "sgcc" / "sgcc_status.md"
    assert sgcc_status_file.exists()
    text = sgcc_status_file.read_text(encoding="utf-8")
    assert "UNAVAILABLE LOCALLY" in text
    assert "henryRDlab/ElectricityTheftDetection" in text
    assert "theft benchmark" in text.lower()
