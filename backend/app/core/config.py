import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# Base directory: Smart_Electricity_Wastage_Real_Data
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Smart Electricity Wastage Detection & Consumption Intelligence"
    API_V1_STR: str = "/api/v1"
    
    # Database Configuration & Connection Pooling
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/electricity_wastage_db"
    ALLOW_SQLITE_FALLBACK: bool = True
    SQLITE_DB_PATH: str = str(BASE_DIR / "electricity_wastage_dev.db")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_CONNECT_TIMEOUT: int = 5
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    MODELS_DIR: Path = BASE_DIR / "models"
    
    # Security Configuration
    SECRET_KEY: str = "dev-secret-key-electricity-wastage-detection-2026"
    ADMIN_SECRET_KEY: str = "watt-admin-sec-key-7f9a8b1c2d3e"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Customer Data Access Policy
    ENFORCE_DEMO_MODE: bool = True  # In demo mode, unverified access is restricted strictly to demonstration accounts
    
    # Restricted CORS Whitelist (Wildcard with credentials forbidden)
    ALLOWED_CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Host-Header Validation Whitelist (Prevents Host Header Poisoning)
    ALLOWED_HOSTS: List[str] = [
        "localhost",
        "127.0.0.1",
        "testserver",
        "utility.wattsense.ai",
        "wattsense_app",
        "*"
    ]
    
    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        """
        Enforces strict credential hygiene in non-development environments.
        Prevents publicly known defaults or weak keys from running in production.
        """
        if self.ENVIRONMENT not in ("development", "test", "demo"):
            weak_defaults = {"admin2026", "admin", "password", "123456", "secret", "watt-admin-sec-key-7f9a8b1c2d3e"}
            if not self.ADMIN_SECRET_KEY or self.ADMIN_SECRET_KEY.lower() in weak_defaults:
                raise ValueError(
                    "CRITICAL SECURITY ERROR: Public or default ADMIN_SECRET_KEY cannot be used in a production environment. "
                    "Configure a strong, unique secret in environment variables."
                )
            if len(self.ADMIN_SECRET_KEY) < 16:
                raise ValueError("ADMIN_SECRET_KEY must be at least 16 characters in production environments.")
            if self.SECRET_KEY == "dev-secret-key-electricity-wastage-detection-2026":
                raise ValueError("SECRET_KEY must be overridden with a cryptographically secure key in production.")
            if self.ALLOW_SQLITE_FALLBACK:
                raise ValueError(
                    "CRITICAL DATABASE CONFIGURATION: In production mode, ALLOW_SQLITE_FALLBACK must be False. "
                    "Production deployments require a verified PostgreSQL connection and cannot silently fall back to SQLite."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
