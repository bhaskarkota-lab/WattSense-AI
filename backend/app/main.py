import uuid
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import init_db_tables, SessionLocal, engine
from backend.app.services.data_ingestion import DataIngestionService
from backend.app.api.router import api_router
from backend.app.api.routes import v2_ml

# Maximum request payload size allowed (5 MB)
MAX_REQUEST_SIZE_BYTES = 5 * 1024 * 1024

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan setup and graceful connection pool teardown."""
    logger.info("Initializing database schema and checking seed data...")
    init_db_tables()
    with SessionLocal() as db:
        DataIngestionService.seed_initial_database_data(db)
    logger.info("Application startup sequence completed successfully.")
    yield
    logger.info("Application shutdown sequence: disposing database connection pool...")
    engine.dispose()
    logger.info("Database connections disposed cleanly. Shutdown complete.")

def create_application() -> FastAPI:
    """FastAPI application factory with production security hardening."""
    # Control OpenAPI documentation exposure in production
    show_docs = settings.ENVIRONMENT in ("development", "test", "demo")

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Intelligent Electricity Consumption Analysis and Wastage Detection Platform",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if show_docs else None,
        lifespan=lifespan
    )

    # 1. Production Security Headers & Request Correlation Middleware
    @app.middleware("http")
    async def security_and_telemetry_middleware(request: Request, call_next):
        # Enforce maximum request payload size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Payload Too Large. Maximum allowed request size is 5MB."}
            )

        # Generate or propagate request correlation ID
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Process request
        response: Response = await call_next(request)

        # Inject Production Security Headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        return response

    # 2. CORS configuration with explicitly restricted allowed origins (No wildcard credentialing)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "X-Customer-Token", "X-Request-ID"],
    )

    # 2b. Host header validation (Prevents Host Header Poisoning)
    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # 3. Public Health Probe (Liveness & Readiness for load balancers and frontend)
    @app.get("/health", summary="Public Infrastructure Health Check Probe", tags=["System Telemetry"])
    def public_health_check(response: Response):
        """
        Public health probe used by container orchestrators, load balancers, and frontend.
        Returns 200 OK when service and database are operational.
        Returns 503 Service Unavailable if database is unreachable.
        Never exposes sensitive database URLs or internal metrics.
        """
        db_connected = False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            db_connected = True
        except Exception as exc:
            logger.warning(f"Public health probe database check failed: {exc}")
            db_connected = False

        if not db_connected:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "DEGRADED",
                "service": settings.PROJECT_NAME,
                "version": "1.0.0",
                "database": "DISCONNECTED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        return {
            "status": "OPERATIONAL",
            "service": settings.PROJECT_NAME,
            "version": "1.0.0",
            "database": "CONNECTED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # 4. Mount API routers under versioned prefix (/api/v1 and /api/v2)
    app.include_router(api_router, prefix=settings.API_V1_STR)
    app.include_router(v2_ml.router, prefix="/api/v2")

    # 5. Mount compiled Frontend UI if available
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

        @app.get("/", summary="Customer and Admin Web Application")
        def serve_frontend():
            return FileResponse(frontend_dist / "index.html")
            
        @app.get("/api", summary="API Info")
        def api_info():
            return {
                "name": settings.PROJECT_NAME,
                "version": "1.0.0",
                "documentation": "/docs" if show_docs else "Disabled in production",
                "api_prefix": settings.API_V1_STR,
                "environment": settings.ENVIRONMENT
            }
    else:
        @app.get("/", summary="Root status check")
        def root():
            return {
                "name": settings.PROJECT_NAME,
                "version": "1.0.0",
                "documentation": "/docs" if show_docs else "Disabled in production",
                "api_prefix": settings.API_V1_STR,
                "environment": settings.ENVIRONMENT
            }

    return app

app = create_application()
