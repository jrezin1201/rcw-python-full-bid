"""
Main FastAPI application entry point.
Configures the application, middleware, and routes.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel

from app.api.routes import auth, debug, extraction_jobs, health, jobs, takeoff_jobs, users
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import engine
from app.models.user import UserRole
from app.services.user_service import UserService
from app.ui import routes as ui_routes

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Runs startup and shutdown logic.
    """
    # Startup
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")

    # Create database tables
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)

    # Create first superuser if it doesn't exist (unless disabled)
    if not settings.DISABLE_BOOTSTRAP_USERS:
        from sqlmodel import Session

        with Session(engine) as session:
            existing_user = UserService.get_by_email(session, settings.FIRST_SUPERUSER_EMAIL)
            if not existing_user:
                logger.info("Creating first superuser...")
                from app.schemas.user import UserCreate

                try:
                    # Validate password length for bcrypt (max 72 bytes)
                    password_bytes = settings.FIRST_SUPERUSER_PASSWORD.encode('utf-8')
                    if len(password_bytes) > 72:
                        logger.error(
                            f"FIRST_SUPERUSER_PASSWORD is too long ({len(password_bytes)} bytes). "
                            "Bcrypt maximum is 72 bytes. Please use a shorter password."
                        )
                        raise ValueError("Password too long for bcrypt")

                    superuser = UserCreate(
                        email=settings.FIRST_SUPERUSER_EMAIL,
                        password=settings.FIRST_SUPERUSER_PASSWORD,
                        full_name="Admin User",
                    )
                    UserService.create(session, superuser, role=UserRole.ADMIN)
                    logger.info(f"Superuser created: {settings.FIRST_SUPERUSER_EMAIL}")
                except Exception as e:
                    logger.error(f"Failed to create superuser: {e}")
                    logger.warning("Continuing without superuser. User auth endpoints may not work.")
    else:
        logger.info("User bootstrapping disabled (DISABLE_BOOTSTRAP_USERS=true)")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# Configure CORS for NextJS development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # NextJS dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Specific methods for API
    allow_headers=["x-api-key", "content-type", "accept"],  # Headers needed for API auth and browser requests
)

# Include UI routes FIRST (no prefix - they serve at root)
# This provides the web UI for the application
logger.info("Including UI routes...")
try:
    app.include_router(ui_routes.router, tags=["UI"])
    logger.info(f"UI routes included successfully. Routes: {[r.path for r in app.routes if hasattr(r, 'path') and ('bid' in r.path or r.path == '/')]}")
except Exception as e:
    logger.error(f"Failed to include UI routes: {e}")
    import traceback
    traceback.print_exc()

# Include API routers AFTER UI routes
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)

# Takeoff extraction routes (simplified version for RC Wendt)
app.include_router(
    takeoff_jobs.router,
    prefix=f"{settings.API_V1_PREFIX}/jobs",
    tags=["Takeoff Jobs"]
)

# Debug routes for signature validation and testing
app.include_router(
    debug.router,
    prefix=f"{settings.API_V1_PREFIX}/debug",
    tags=["Debug"]
)

# Generic background job demo routes.
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)

# Original extraction routes (kept under /extraction to avoid path conflicts).
# app.include_router(
#     extraction_jobs.router,
#     prefix=f"{settings.API_V1_PREFIX}/extraction",
#     tags=["Extraction Jobs"]
# )

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API root endpoint (moved to /api/v1/)
# NOTE: Commented out because it was conflicting with UI routes
# @app.get(f"{settings.API_V1_PREFIX}/")
# def api_root() -> dict:
#     """API root endpoint."""
#     return {
#         "message": f"Welcome to {settings.PROJECT_NAME} API",
#         "version": settings.VERSION,
#         "docs": f"{settings.API_V1_PREFIX}/docs",
#     }
