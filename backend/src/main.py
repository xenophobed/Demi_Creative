"""
Creative Agent FastAPI Application

Children's Creative Workshop API Service
"""

import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from .api.models import ErrorResponse, ErrorDetail, HealthCheckResponse
from .paths import DATA_DIR, UPLOAD_DIR, AUDIO_DIR, VIDEO_DIR, VIDEO_JOBS_DIR
from .services.database import db_manager, session_repo
from .services.database.schema import init_schema, migrate_json_sessions


# Load environment variables
load_dotenv()


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

    yield

    # On shutdown
    print("👋 Creative Agent API Shutting down...")

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
    openapi_url="/api/openapi.json"
)


# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "http://localhost:5173",  # Vite frontend
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    """Request validation error handler"""
    errors = []

    for error in exc.errors():
        errors.append(ErrorDetail(
            field=".".join(str(loc) for loc in error["loc"]),
            message=error["msg"],
            code=error["type"]
        ))

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request parameter validation failed",
            details=errors,
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Value error handler"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="ValueError",
            message=str(exc),
            timestamp=datetime.now()
        ).model_dump(mode='json')
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
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get(
    "/",
    response_model=HealthCheckResponse,
    tags=["Health Check"]
)
async def root():
    """Root path health check"""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(),
        services={
            "api": "running",
            "session_manager": "running"
        }
    )


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health Check"]
)
async def health_check():
    """Health check endpoint"""
    # Check database connection
    db_connected = db_manager.is_connected

    # Check environment variables
    required_env_vars = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    env_vars_set = all(os.getenv(var) for var in required_env_vars)

    services_status = {
        "api": "running",
        "database": "running" if db_connected else "disconnected",
        "environment": "configured" if env_vars_set else "missing_keys"
    }

    overall_status = "healthy" if all(
        s in ["running", "configured"] for s in services_status.values()
    ) else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now(),
        services=services_status
    )


# ============================================================================
# Static Files (Audio, Uploads)
# ============================================================================

# Ensure directories exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Scoped static file mounts (blocks access to DB files, sessions, vectors, video_jobs)
app.mount("/data/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/data/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/data/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")


# ============================================================================
# API Routes
# ============================================================================

from .api.routes import image_to_story, interactive_story, audio, video, users, news_to_kids

app.include_router(image_to_story.router)
app.include_router(interactive_story.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(users.router)
app.include_router(news_to_kids.router)


# ============================================================================
# Main Entry Point (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
