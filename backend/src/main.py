"""
Creative Agent FastAPI Application

儿童创意工坊 API 服务
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


# 加载环境变量
load_dotenv()


# ============================================================================
# Lifespan Events
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("🚀 Creative Agent API Starting...")

    # 连接数据库
    await db_manager.connect()
    print("📦 Database connected")

    # 初始化schema
    await init_schema(db_manager)

    # 迁移JSON会话数据
    migrated = await migrate_json_sessions(db_manager)
    if migrated > 0:
        print(f"📂 Migrated {migrated} JSON sessions to database")

    # 清理过期会话
    cleaned = await session_repo.cleanup_expired_sessions()
    print(f"🧹 Cleaned up {cleaned} expired sessions")

    yield

    # 关闭时
    print("👋 Creative Agent API Shutting down...")

    # 断开数据库连接
    await db_manager.disconnect()
    print("📦 Database disconnected")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Creative Agent API",
    description="儿童创意工坊 - AI Agent 内容生成服务",
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
        "http://localhost:3000",  # React 前端
        "http://localhost:5173",  # Vite 前端
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
    """请求验证错误处理"""
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
            message="请求参数验证失败",
            details=errors,
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """值错误处理"""
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
    """通用错误处理"""
    print(f"❌ Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="服务器内部错误，请稍后重试",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get(
    "/",
    response_model=HealthCheckResponse,
    tags=["健康检查"]
)
async def root():
    """根路径健康检查"""
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
    tags=["健康检查"]
)
async def health_check():
    """健康检查端点"""
    # 检查数据库连接
    db_connected = db_manager.is_connected

    # 检查环境变量
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

# 确保目录存在
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_JOBS_DIR.mkdir(parents=True, exist_ok=True)

# 挂载静态文件
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")


# ============================================================================
# API Routes
# ============================================================================

from .api.routes import image_to_story, interactive_story, audio, video, users

app.include_router(image_to_story.router)
app.include_router(interactive_story.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(users.router)


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
