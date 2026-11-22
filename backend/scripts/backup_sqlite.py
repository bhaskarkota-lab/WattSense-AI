"""
SQLite Source Database Backup and Integrity Verification Script.
Creates a timestamped snapshot of electricity_wastage_dev.db,
computes SHA256 checksums, and audits record counts.
"""
import os
import shutil
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
src_path = project_root / "electricity_wastage_dev.db"
backup_dir = project_root / "database" / "backups" / "sqlite_backups"
backup_dir.mkdir(parents=True, exist_ok=True)

ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
dst_path = backup_dir / f"electricity_wastage_dev_backup_{ts}.db"

shutil.copy2(src_path, dst_path)

src_hash = hashlib.sha256(src_path.read_bytes()).hexdigest()
dst_hash = hashlib.sha256(dst_path.read_bytes()).hexdigest()

assert src_hash == dst_hash, f"Checksum mismatch! {src_hash} != {dst_hash}"

conn = sqlite3.connect(dst_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [r[0] for r in cur.fetchall()]
counts = {}
for t in sorted(tables):
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    counts[t] = cur.fetchone()[0]
conn.close()

print(f"BACKUP_LOCATION: {dst_path}")
print(f"FILE_SIZE: {dst_path.stat().st_size:,} bytes")
print(f"SHA256_CHECKSUM: {src_hash}")
print("VERIFIED_COUNTS:")
for t, cnt in counts.items():
    print(f"  * {t}: {cnt}")
