import time
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import engine, active_db_url, is_sqlite_fallback, mask_database_url
from backend.app.db.models import (
    Customer,
    ConsumptionRecord,
    WastageAlert,
    Recommendation,
    AdminModelMetric,
)
from backend.app.schemas.admin import DatabaseHealthResponse

class DatabaseHealthService:
    """Dedicated service for database connectivity verification and diagnostic telemetry."""

    @classmethod
    def get_health_status(cls, db: Session) -> DatabaseHealthResponse:
        """
        Executes active database ping, calculates latency, gathers connection pool
        telemetry, and returns table record counts.
        """
        start_time = time.perf_counter()
        db_connected = False
        latency_ms = 0.0

        try:
            db.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            db_connected = True
        except Exception as exc:
            logger.error(f"Database health check ping failed: {exc}")
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            db_connected = False

        # Determine dialect and clean database name without exposing credentials
        dialect = engine.dialect.name
        db_name = "unknown"
        try:
            if hasattr(engine.url, "database") and engine.url.database:
                db_name = engine.url.database.split("/")[-1].split("\\")[-1]
        except Exception:
            db_name = "unknown"

        # Connection pool diagnostics
        pool_status: Dict[str, Any] = {
            "pool_class": engine.pool.__class__.__name__
        }
        if hasattr(engine.pool, "size"):
            try:
                pool_status.update({
                    "configured_pool_size": getattr(engine.pool, "size")(),
                    "checked_in_connections": getattr(engine.pool, "checkedin")(),
                    "checked_out_connections": getattr(engine.pool, "checkedout")(),
                    "overflow_connections": getattr(engine.pool, "overflow")(),
                })
            except Exception:
                pass

        # Table row counts
        table_counts: Dict[str, int] = {}
        if db_connected:
            try:
                table_counts = {
                    "customers": db.query(Customer).count(),
                    "consumption_records": db.query(ConsumptionRecord).count(),
                    "wastage_alerts": db.query(WastageAlert).count(),
                    "recommendations": db.query(Recommendation).count(),
                    "admin_model_metrics": db.query(AdminModelMetric).count(),
                }
            except Exception as exc:
                logger.warning(f"Failed to query table counts during DB health check: {exc}")
                table_counts = {"error": 0}

        # Status classification
        if not db_connected:
            status = "UNAVAILABLE"
        elif is_sqlite_fallback:
            status = "DEGRADED"  # Operational, but running on fallback SQLite rather than target PostgreSQL
        else:
            status = "HEALTHY"

        return DatabaseHealthResponse(
            status=status,
            database_connected=db_connected,
            dialect=dialect,
            database_name=db_name,
            active_url_masked=mask_database_url(active_db_url),
            is_fallback=is_sqlite_fallback,
            fail_closed_enforced=(settings.ENVIRONMENT not in ("development", "test", "demo")),
            environment=settings.ENVIRONMENT,
            latency_ms=latency_ms,
            pool_status=pool_status,
            table_counts=table_counts,
            timestamp=datetime.now(timezone.utc),
        )
