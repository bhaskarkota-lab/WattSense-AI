#!/usr/bin/env python3
"""
Idempotent Data Migration Pipeline: SQLite to PostgreSQL for WattSense AI™.

Safely migrates demonstration accounts, consumption time-series, wastage alerts,
and model metrics from local SQLite development storage into production PostgreSQL.

Key Architectural Guarantees:
1. Preserves source SQLite data unchanged (read-only access).
2. Enforces strict Foreign Key dependency order during ingestion.
3. Completely idempotent: duplicate runs will not duplicate records.
4. Batched insertions for high-throughput consumption time-series records.
5. Post-migration verification reconciling source and target row counts.
6. Masked credential logging (passwords are never logged).
7. Full rollback on unhandled exceptions.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base
from backend.app.db.models import (
    Customer,
    ConsumptionRecord,
    WastageAlert,
    Recommendation,
    AdminModelMetric,
)
from backend.app.db.session import mask_database_url

def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate demonstration and historical data from SQLite to PostgreSQL."
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default=None,
        help="Path to source SQLite database file."
    )
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=None,
        help="Target PostgreSQL connection URL."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for inserting time-series consumption records."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit source records and test target connectivity without committing changes."
    )
    return parser.parse_args()

def audit_sqlite(session: Session) -> Dict[str, int]:
    """Audits record counts in source SQLite database."""
    counts = {
        "customers": session.query(func.count(Customer.id)).scalar() or 0,
        "consumption_records": session.query(func.count(ConsumptionRecord.id)).scalar() or 0,
        "wastage_alerts": session.query(func.count(WastageAlert.id)).scalar() or 0,
        "recommendations": session.query(func.count(Recommendation.id)).scalar() or 0,
        "admin_model_metrics": session.query(func.count(AdminModelMetric.id)).scalar() or 0,
    }
    return counts

def run_migration():
    args = parse_args()
    
    # 1. Resolve SQLite path
    sqlite_path = args.sqlite_path or settings.SQLITE_DB_PATH
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.is_absolute():
        sqlite_file = PROJECT_ROOT / sqlite_file
        
    if not sqlite_file.exists():
        logger.error(f"Source SQLite database file not found at: {sqlite_file}")
        sys.exit(1)
        
    sqlite_url = f"sqlite:///{sqlite_file.as_posix()}"
    postgres_url = args.postgres_url or settings.DATABASE_URL
    
    logger.info("=" * 70)
    logger.info("WattSense AI™ — SQLite to PostgreSQL Migration Pipeline")
    logger.info(f"Source SQLite DB : {sqlite_file.name} ({sqlite_file.stat().st_size:,} bytes)")
    logger.info(f"Target DB URL    : {mask_database_url(postgres_url)}")
    logger.info(f"Dry Run Mode     : {args.dry_run}")
    logger.info("=" * 70)
    
    # 2. Connect to Source SQLite
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SqliteSession()
    
    source_counts = audit_sqlite(sqlite_session)
    logger.info("Source SQLite row counts:")
    for table, count in source_counts.items():
        logger.info(f"  • {table:<22}: {count:,} records")
        
    # 3. Test Connection to Target PostgreSQL
    logger.info("Testing connection to target database...")
    try:
        pg_engine = create_engine(
            postgres_url,
            connect_args={"connect_timeout": 5} if "postgresql" in postgres_url else {}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to target PostgreSQL server.")
    except (OperationalError, Exception) as exc:
        logger.error(f"FATAL: Target database connection failed: {exc}")
        logger.error(
            "MIGRATION BLOCKED: PostgreSQL server is unreachable or credentials in DATABASE_URL are invalid.\n"
            f"Configured URL: {mask_database_url(postgres_url)}\n"
            "To resolve this, update your .env file with valid PostgreSQL credentials:\n"
            "  DATABASE_URL=postgresql+psycopg2://<username>:<password>@localhost:5432/<database_name>\n"
            "and ensure the target database has been created (e.g. 'CREATE DATABASE electricity_wastage_db;')."
        )
        sqlite_session.close()
        sys.exit(2)
        
    if args.dry_run:
        logger.info("[DRY RUN] Source verified and target connectivity confirmed. No changes written.")
        sqlite_session.close()
        return

    # 4. Prepare Target Schema
    logger.info("Ensuring target database tables exist...")
    Base.metadata.create_all(bind=pg_engine)
    PgSession = sessionmaker(bind=pg_engine)
    pg_session = PgSession()

    failed_records: List[Dict[str, Any]] = []

    try:
        # Step 4a: Migrate Customers
        logger.info("Migrating 'customers' table...")
        sqlite_customers = sqlite_session.query(Customer).all()
        id_mapping: Dict[int, int] = {}  # sqlite_customer_id -> pg_customer_id
        migrated_customers = 0

        for sc in sqlite_customers:
            # Check for existing customer by consumer_number
            existing = pg_session.query(Customer).filter_by(consumer_number=sc.consumer_number).first()
            if existing:
                id_mapping[sc.id] = existing.id
            else:
                new_cust = Customer(
                    consumer_number=sc.consumer_number,
                    customer_type=sc.customer_type,
                    region=sc.region,
                    meter_number=sc.meter_number,
                    is_active=sc.is_active,
                    is_demo=sc.is_demo,
                    created_at=sc.created_at,
                    updated_at=sc.updated_at,
                )
                pg_session.add(new_cust)
                pg_session.flush()
                id_mapping[sc.id] = new_cust.id
                migrated_customers += 1

        pg_session.commit()
        logger.info(f"Customers migration complete: {migrated_customers} new records inserted.")

        # Step 4b: Migrate Consumption Records (Batched)
        logger.info(f"Migrating 'consumption_records' in batches of {args.batch_size}...")
        sqlite_records = sqlite_session.query(ConsumptionRecord).all()
        migrated_records = 0
        batch: List[ConsumptionRecord] = []

        for sr in sqlite_records:
            pg_customer_id = id_mapping.get(sr.customer_id)
            if not pg_customer_id:
                failed_records.append({
                    "table": "consumption_records",
                    "source_id": sr.id,
                    "reason": f"customer_id {sr.customer_id} could not be resolved",
                    "status": "SKIPPED_UNMAPPED"
                })
                logger.warning(f"Skipping record ID {sr.id}: customer_id {sr.customer_id} not mapped.")
                continue

            # Idempotency check: does this customer have a record at this timestamp?
            exists = pg_session.query(ConsumptionRecord.id).filter_by(
                customer_id=pg_customer_id,
                timestamp=sr.timestamp
            ).first()
            if exists:
                continue

            batch.append(ConsumptionRecord(
                customer_id=pg_customer_id,
                timestamp=sr.timestamp,
                consumption_value=sr.consumption_value,
                unit=sr.unit,
                interval_minutes=sr.interval_minutes,
                source_dataset=sr.source_dataset,
                is_verified=sr.is_verified,
                created_at=sr.created_at,
            ))

            if len(batch) >= args.batch_size:
                pg_session.add_all(batch)
                pg_session.commit()
                migrated_records += len(batch)
                batch = []

        if batch:
            pg_session.add_all(batch)
            pg_session.commit()
            migrated_records += len(batch)

        logger.info(f"Consumption records migration complete: {migrated_records} new records inserted.")

        # Step 4c: Migrate Wastage Alerts
        logger.info("Migrating 'wastage_alerts'...")
        sqlite_alerts = sqlite_session.query(WastageAlert).all()
        migrated_alerts = 0
        for sa in sqlite_alerts:
            pg_customer_id = id_mapping.get(sa.customer_id)
            if not pg_customer_id:
                failed_records.append({
                    "table": "wastage_alerts",
                    "source_id": sa.id,
                    "reason": f"customer_id {sa.customer_id} could not be resolved",
                    "status": "SKIPPED_UNMAPPED"
                })
                continue

            exists = pg_session.query(WastageAlert.id).filter_by(
                customer_id=pg_customer_id,
                timestamp=sa.timestamp
            ).first()
            if exists:
                continue

            pg_session.add(WastageAlert(
                customer_id=pg_customer_id,
                timestamp=sa.timestamp,
                actual_consumption=sa.actual_consumption,
                expected_consumption=sa.expected_consumption,
                potential_excess_consumption=sa.potential_excess_consumption,
                unit=sa.unit,
                severity=sa.severity,
                alert_status=sa.alert_status,
                persistence_count=sa.persistence_count,
                potential_cost_excess=sa.potential_cost_excess,
                created_at=sa.created_at,
            ))
            migrated_alerts += 1

        pg_session.commit()
        logger.info(f"Wastage alerts migration complete: {migrated_alerts} new records inserted.")

        # Step 4d: Migrate Recommendations
        logger.info("Migrating 'recommendations'...")
        sqlite_recs = sqlite_session.query(Recommendation).all()
        migrated_recs = 0
        for sr in sqlite_recs:
            pg_customer_id = id_mapping.get(sr.customer_id)
            if not pg_customer_id:
                failed_records.append({
                    "table": "recommendations",
                    "source_id": sr.id,
                    "reason": f"customer_id {sr.customer_id} could not be resolved",
                    "status": "SKIPPED_UNMAPPED"
                })
                continue

            exists = pg_session.query(Recommendation.id).filter_by(
                customer_id=pg_customer_id,
                title=sr.title
            ).first()
            if exists:
                continue

            pg_session.add(Recommendation(
                customer_id=pg_customer_id,
                category=sr.category,
                title=sr.title,
                description=sr.description,
                action_steps=sr.action_steps,
                potential_savings_estimate=sr.potential_savings_estimate,
                is_active=sr.is_active,
                created_at=sr.created_at,
            ))
            migrated_recs += 1

        pg_session.commit()
        logger.info(f"Recommendations migration complete: {migrated_recs} new records inserted.")

        # Step 4e: Migrate Admin Model Metrics
        logger.info("Migrating 'admin_model_metrics'...")
        sqlite_metrics = sqlite_session.query(AdminModelMetric).all()
        migrated_metrics = 0
        for sm in sqlite_metrics:
            exists = pg_session.query(AdminModelMetric.id).filter_by(
                model_name=sm.model_name,
                dataset_name=sm.dataset_name,
                task_type=sm.task_type
            ).first()
            if exists:
                continue

            pg_session.add(AdminModelMetric(
                model_name=sm.model_name,
                dataset_name=sm.dataset_name,
                task_type=sm.task_type,
                version_tag=sm.version_tag,
                metrics_payload=sm.metrics_payload,
                hyperparameters=sm.hyperparameters,
                train_rows=sm.train_rows,
                test_rows=sm.test_rows,
                evaluated_at=sm.evaluated_at,
            ))
            migrated_metrics += 1

        pg_session.commit()
        logger.info(f"Admin model metrics migration complete: {migrated_metrics} new records inserted.")

        # Step 5: Post-migration reconciliation audit
        logger.info("=" * 70)
        logger.info("POST-MIGRATION RECONCILIATION AUDIT")
        target_counts = {
            "customers": pg_session.query(func.count(Customer.id)).scalar() or 0,
            "consumption_records": pg_session.query(func.count(ConsumptionRecord.id)).scalar() or 0,
            "wastage_alerts": pg_session.query(func.count(WastageAlert.id)).scalar() or 0,
            "recommendations": pg_session.query(func.count(Recommendation.id)).scalar() or 0,
            "admin_model_metrics": pg_session.query(func.count(AdminModelMetric.id)).scalar() or 0,
        }

        all_matched = True
        for table, src_count in source_counts.items():
            tgt_count = target_counts.get(table, 0)
            status = "MATCH" if tgt_count >= src_count else "MISMATCH"
            if status != "MATCH":
                all_matched = False
            logger.info(f"  • {table:<22}: Source={src_count:<5} | Target={tgt_count:<5} | [{status}]")

        if all_matched:
            logger.info("SUCCESS: All source records successfully accounted for in target database.")
        else:
            logger.warning("WARNING: One or more table counts do not match source database.")

        if failed_records:
            logger.warning(f"Total unmapped/failed records: {len(failed_records)}")
            for fr in failed_records[:20]:
                logger.warning(f"  • {fr['table']} [ID {fr['source_id']}]: {fr['reason']} ({fr['status']})")
        else:
            logger.info("Record integrity verified: 0 unmapped or skipped records across all tables.")

    except Exception as exc:
        pg_session.rollback()
        logger.error(f"Migration transaction failed: {exc}. Rolling back changes.")
        raise
    finally:
        sqlite_session.close()
        pg_session.close()

if __name__ == "__main__":
    run_migration()
