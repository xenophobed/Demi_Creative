"""
Creative Agent FastAPI Application

Children's Creative Workshop API Service
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.models import ErrorDetail, ErrorResponse, HealthCheckResponse
from .paths import (
    AUDIO_DIR,
    DATA_DIR,
    STYLED_DIR,
    UPLOAD_DIR,
    VIDEO_DIR,
    VIDEO_JOBS_DIR,
)
from .services.database import db_manager, session_repo
from .services.database.schema import init_schema, migrate_json_sessions
from .services.kids_daily_scheduler import daily_drop_scheduler
from .services.retention_scheduler import retention_scheduler

logger = logging.getLogger(__name__)

# Load environment variables from backend/.env regardless of cwd
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env")


def _patch_anthropic_async_http_client_close() -> None:
    """Guard anthropic async client close on partially-initialized wrappers.

    In some env/version mixes, AsyncHttpxClientWrapper may be garbage-collected
    before httpx.AsyncClient internals are fully initialized, which raises:
    AttributeError: 'AsyncHttpxClientWrapper' object has no attribute '_state'
    """
    try:
        from anthropic._base_client import AsyncHttpxClientWrapper
    except Exception:
        return

    if getattr(AsyncHttpxClientWrapper, "_creative_agent_close_guard", False):
        return

    original_aclose = getattr(AsyncHttpxClientWrapper, "aclose", None)
    if original_aclose is None:
        return

    async def _safe_aclose(self, *args, **kwargs):
        if not hasattr(self, "_state"):
            return
        return await original_aclose(self, *args, **kwargs)

    def _safe_del(self) -> None:
        if not hasattr(self, "_state"):
            return
        try:
            asyncio.get_running_loop().create_task(self.aclose())
        except Exception:
            pass

    AsyncHttpxClientWrapper.aclose = _safe_aclose
    AsyncHttpxClientWrapper.__del__ = _safe_del
    AsyncHttpxClientWrapper._creative_agent_close_guard = True
    logger.info("Installed anthropic AsyncHttpxClientWrapper close guard")


_patch_anthropic_async_http_client_close()


# ============================================================================
# Lifespan Events
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # On startup
    print("🚀 Creative Agent API Starting...")

    # Connect to database
    await db_manager.connect()
    print("📦 Database connected")

    # Initialize schema
    await init_schema(db_manager)

    # Migrate JSON session data
    migrated = await migrate_json_sessions(db_manager)
    if migrated > 0:
        print(f"📂 Migrated {migrated} JSON sessions to database")

    # Clean up expired sessions
    cleaned = await session_repo.cleanup_expired_sessions()
    print(f"🧹 Cleaned up {cleaned} expired sessions")

    # Start Daily Drop scheduler (#97) outside test env.
    scheduler_enabled = os.getenv("DAILY_DROP_ENABLED", "1") != "0"
    if scheduler_enabled and os.getenv("ENVIRONMENT") != "test":
        await daily_drop_scheduler.start()

    # Start retention cleanup scheduler (#145) outside test env.
    retention_enabled = os.getenv("RETENTION_CLEANUP_ENABLED", "1") != "0"
    if retention_enabled and os.getenv("ENVIRONMENT") != "test":
        await retention_scheduler.start()

    # MCP server diagnostics
    from .mcp_servers import MCP_SERVER_STATUS

    print("🔌 MCP Servers:")
    for server, status in MCP_SERVER_STATUS.items():
        icon = "✅" if status == "ok" else "❌"
        short_status = "OK" if status == "ok" else status
        print(f"  {icon} {server}: {short_status}")

    yield

    # On shutdown
    print("👋 Creative Agent API Shutting down...")

    # Disconnect from database
    if scheduler_enabled and os.getenv("ENVIRONMENT") != "test":
        await daily_drop_scheduler.stop()

    if retention_enabled and os.getenv("ENVIRONMENT") != "test":
        await retention_scheduler.stop()

    # Disconnect from database
    await db_manager.disconnect()
    print("📦 Database disconnected")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Creative Agent API",
    description="Children's Creative Workshop - AI Agent Content Generation Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# ============================================================================
# CORS Middleware
# ============================================================================

_default_origins = "http://localhost:3000,http://localhost:5173"
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]
# Keep FRONTEND_URL for backward compatibility
_frontend_url = os.getenv("FRONTEND_URL", "")
if _frontend_url and _frontend_url not in _allowed_origins:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Request validation error handler"""
    errors = []

    for error in exc.errors():
        errors.append(
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"]),
                message=error["msg"],
                code=error["type"],
            )
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request parameter validation failed",
            details=errors,
            timestamp=datetime.now(),
        ).model_dump(mode="json"),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Value error handler"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="ValueError", message=str(exc), timestamp=datetime.now()
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General error handler"""
    print(f"❌ Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="Internal server error, please try again later",
            timestamp=datetime.now(),
        ).model_dump(mode="json"),
    )


# ============================================================================
# Health Check
# ============================================================================


@app.get("/", response_model=HealthCheckResponse, tags=["Health Check"])
async def root():
    """Root path health check"""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(),
        services={"api": "running", "session_manager": "running"},
    )


@app.get("/health", response_model=HealthCheckResponse, tags=["Health Check"])
async def health_check():
    """Health check endpoint"""
    # Check database connection
    db_connected = db_manager.is_connected

    # Check environment variables
    required_env_vars = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    env_vars_set = all(os.getenv(var) for var in required_env_vars)

    # Determine Daily Drop scheduler status
    scheduler_enabled = os.getenv("DAILY_DROP_ENABLED", "1") != "0"
    if not scheduler_enabled:
        scheduler_status = "disabled"
    elif daily_drop_scheduler._task and not daily_drop_scheduler._task.done():
        scheduler_status = "running"
    else:
        scheduler_status = "stopped"

    # Determine retention scheduler status
    retention_enabled = os.getenv("RETENTION_CLEANUP_ENABLED", "1") != "0"
    if not retention_enabled:
        retention_status = "disabled"
    elif retention_scheduler._task and not retention_scheduler._task.done():
        retention_status = "running"
    else:
        retention_status = "stopped"

    # MCP server import status
    from .mcp_servers import MCP_SERVER_STATUS

    mcp_all_ok = all(v == "ok" for v in MCP_SERVER_STATUS.values())

    services_status = {
        "api": "running",
        "database": "running" if db_connected else "degraded",
        "session_manager": "running" if db_connected else "degraded",
        "environment": "configured" if env_vars_set else "missing_keys",
        "daily_drop_scheduler": scheduler_status,
        "retention_scheduler": retention_status,
        "mcp_servers": dict(MCP_SERVER_STATUS),
    }

    # Determine overall health — ignore nested mcp_servers dict in top-level check
    top_level_ok = all(
        s in ["running", "configured", "disabled"]
        for k, s in services_status.items()
        if isinstance(s, str)
    )
    overall_status = "healthy" if (top_level_ok and mcp_all_ok) else "degraded"  # v2-healthfix

    return HealthCheckResponse(
        status=overall_status,
        version="1.1.0",
        timestamp=datetime.now(),
        services=services_status,
    )


# ============================================================================
# Static Files (Audio, Uploads) — local dev only
# ============================================================================

# Only mount local StaticFiles when not using Supabase Storage (#343).
# In production (STORAGE_BACKEND=supabase) files are served from the CDN.
if os.getenv("STORAGE_BACKEND", "local").lower() != "supabase":
    # Ensure directories exist
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    STYLED_DIR.mkdir(parents=True, exist_ok=True)

    # Scoped static file mounts (blocks access to DB files, sessions, vectors, video_jobs)
    app.mount("/data/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
    app.mount("/data/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
    app.mount("/data/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")
    app.mount("/data/styled", StaticFiles(directory=str(STYLED_DIR)), name="styled")


# ============================================================================
# API Routes
# ============================================================================

from .api.routes import (
    admin_artifacts,
    admin_hub,
    achievements,
    agents,
    artifacts,
    audio,
    hub,
    image_to_story,
    inspiration_daily,
    interactive_story,
    kids_daily,
    library,
    memory,
    onboarding,
    subscriptions,
    usage,
    users,
    video,
    voice,
)

app.include_router(image_to_story.router)
app.include_router(interactive_story.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(voice.router)
app.include_router(users.router)
app.include_router(agents.router)
app.include_router(onboarding.router)
app.include_router(hub.router)
app.include_router(kids_daily.router)
app.include_router(inspiration_daily.router)
app.include_router(subscriptions.router)
app.include_router(artifacts.router)
app.include_router(admin_artifacts.router)
app.include_router(admin_hub.router)
app.include_router(achievements.router)
app.include_router(library.router)
app.include_router(memory.router)
app.include_router(usage.router)


# ============================================================================
# Main Entry Point (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
