import os
import sys
import re
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
from backend.app.core.config import settings
from backend.app.db.session import mask_database_url

def run_backup():
    print("=" * 70)
    print("WattSense AI™ — Automated PostgreSQL Backup Utility")
    print("=" * 70)

    db_url = settings.DATABASE_URL
    if "postgresql" not in db_url.lower():
        print(f"Error: DATABASE_URL is not PostgreSQL: {mask_database_url(db_url)}")
        sys.exit(1)

    match = re.search(r"://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", db_url)
    if not match:
        print("Error: Could not parse DATABASE_URL")
        sys.exit(1)

    user, password, host, port, db_name = match.groups()
    port = port or "5432"

    # Find pg_dump.exe
    pg_dump_candidates = [
        Path(r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"),
        Path(r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"),
        Path(r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"),
    ]
    pg_dump_path = None
    for cand in pg_dump_candidates:
        if cand.exists():
            pg_dump_path = cand
            break

    if not pg_dump_path:
        # Fallback to system PATH
        pg_dump_path = "pg_dump"

    backup_dir = root / "database" / "backups" / "postgres_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{db_name}_backup_{timestamp}.sql"

    print(f"Source Database : '{db_name}' on {host}:{port}")
    print(f"Target Backup   : {backup_file.name}")
    print(f"Backup Tool     : {pg_dump_path}")

    # Set PGPASSWORD in environment for subprocess
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    cmd = [
        str(pg_dump_path),
        "-h", host,
        "-p", port,
        "-U", user,
        "-F", "p",  # Plain text SQL format
        "--no-owner",
        "--no-privileges",
        "-f", str(backup_file),
        db_name
    ]

    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        size = backup_file.stat().st_size
        with open(backup_file, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        print("\nBACKUP COMPLETED SUCCESSFULLY!")
        print(f"File Size : {size:,} bytes")
        print(f"SHA256    : {sha256}")
        print(f"Location  : {backup_file}")

        # Safe Rolling Retention Management: Keep at least 5 snapshots, purge files older than 30 days
        all_backups = sorted(list(backup_dir.glob("*.sql")), key=lambda p: p.stat().st_mtime, reverse=True)
        min_to_keep = 5
        max_age_seconds = 30 * 86400
        now_ts = datetime.now(timezone.utc).timestamp()
        
        pruned_count = 0
        if len(all_backups) > min_to_keep:
            for old_bkp in all_backups[min_to_keep:]:
                if (now_ts - old_bkp.stat().st_mtime) > max_age_seconds:
                    old_bkp.unlink()
                    pruned_count += 1
                    print(f"  [Retention]: Purged old backup beyond 30 days: {old_bkp.name}")
        
        print(f"Total Preserved Backups: {len(list(backup_dir.glob('*.sql')))} (Pruned {pruned_count} aged snapshots)")
        return backup_file, size, sha256
    except subprocess.CalledProcessError as e:
        print(f"\n[CRITICAL ERROR] Backup execution failed with return code {e.returncode}:")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Unexpected failure during backup: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_backup()
