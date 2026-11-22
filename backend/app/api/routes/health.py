from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db.session import get_db, active_db_url
from backend.app.schemas.admin import AdminHealthStatus
from backend.app.db.models import Customer, ConsumptionRecord, WastageAlert
from backend.app.core.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health", summary="Basic API health check")
def health_check(db: Session = Depends(get_db)):
    """Verifies that the API service and database connection are operational."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False
        raise HTTPException(status_code=503, detail=f"Database unreachable: {e}")

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if db_ok else "disconnected",
        "engine": "PostgreSQL" if "postgresql" in active_db_url else "SQLite"
    }
