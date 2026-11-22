import os
import re
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Tuple
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.base import Base

def mask_database_url(url: str) -> str:
    """
    Masks credentials in database connection URLs for safe diagnostic output and logging.
    Example: postgresql+psycopg2://user:password@localhost:5432/db -> postgresql+psycopg2://user:****@localhost:5432/db
    """
    if not url:
        return ""
    # Mask password pattern ://username:password@
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)

def get_engine_and_url() -> Tuple[Engine, str, bool]:
    """
    Creates the SQLAlchemy Engine according to environment configuration.
    
    1. Attempts primary connection (e.g. PostgreSQL) with production-grade connection pooling:
       - pool_size, max_overflow, pool_timeout, pool_recycle, pool_pre_ping.
    2. If primary connection fails:
       - In non-development environments (e.g. production): Fails closed immediately (RuntimeError).
       - In development/test/demo environments with ALLOW_SQLITE_FALLBACK=True:
         Falls back safely to local SQLite development database.
         
    Returns:
        Tuple[Engine, str, bool]: (engine, active_url, is_sqlite_fallback)
    """
    database_url = settings.DATABASE_URL
    is_postgres = "postgresql" in database_url.lower()

    if is_postgres:
        try:
            engine = create_engine(
                database_url,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,
                connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT}
            )
            # Perform live pre-flight verification
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(f"Successfully connected to primary PostgreSQL database at: {mask_database_url(database_url)}")
            return engine, database_url, False
        except (OperationalError, Exception) as exc:
            masked_url = mask_database_url(database_url)
            # Production Fail-Closed Enforcement: Never fall back to SQLite in production!
            if settings.ENVIRONMENT not in ("development", "test", "demo") or not settings.ALLOW_SQLITE_FALLBACK:
                error_msg = (
                    f"CRITICAL DATABASE FAILURE: Unable to connect to primary PostgreSQL database at {masked_url} "
                    f"in environment '{settings.ENVIRONMENT}'. SQLite fallback is disallowed in production. "
                    f"Error detail: {exc}"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg) from exc

            # Safe fallback for development/testing/demonstration
            sqlite_path = Path(settings.SQLITE_DB_PATH)
            if not sqlite_path.is_absolute():
                sqlite_path = settings.BASE_DIR / sqlite_path
            sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"
            logger.warning(
                f"Primary database connection failed ({exc}). Falling back to SQLite at: {sqlite_url}"
            )
            fallback_engine = create_engine(
                sqlite_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True
            )
            return fallback_engine, sqlite_url, True

    # Direct SQLite connection specified
    sqlite_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
    return sqlite_engine, database_url, False

# Initialize active engine and configuration state
engine, active_db_url, is_sqlite_fallback = get_engine_and_url()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for yielding transactional database sessions.
    Automatically rolls back on unhandled exceptions and always closes the session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for safe transactional database operations.
    Automatically commits on success, rolls back on exception, and closes session.
    
    Usage:
        with get_db_context() as session:
            session.add(record)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db_tables():
    """Creates all database tables based on declarative models."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified and initialized successfully.")
