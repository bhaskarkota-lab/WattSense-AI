# SGCC Electricity Theft Detection Dataset — Availability & Status

## 1. Local Availability Status
- **Status**: UNAVAILABLE LOCALLY (`data/raw/sgcc/` contains no extracted CSV files).
- **Research Rule**: Synthetic records and fabricated charts are strictly forbidden for SGCC.

## 2. Official Acquisition Source
- **Primary Repository**: [henryRDlab/ElectricityTheftDetection](https://github.com/henryRDlab/ElectricityTheftDetection)
- **Archive Parts Required**: `data.zip`, `data.z01`, `data.z02` (multi-part zip archive)
- **Secondary Source**: IEEE Dataport: *Electricity Theft Detection in Smart Grids*

## 3. Dataset Characteristics
- **Scale**: 42,372 customer profiles across 1,035 days.
- **Cadence**: Daily aggregate electricity consumption.
- **Labels**: Binary `FLAG` (0: Normal customer, 1: Theft/tampered meter).
- **Integrity Restriction**: `FLAG = 1` is an electricity theft benchmark label, strictly separate from general customer wastage.
