"""城市地下管网巡检养护平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import ROUTERS
from app.store import store
from app.services.training import (
    TrainingAuthError,
    TrainingConflictError,
    TrainingNotFoundError,
    TrainingPermissionError,
    TrainingRequestError,
)

app = FastAPI(title="城市地下管网巡检养护平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(message: str, status_code: int, **extra: object) -> JSONResponse:
    payload: dict[str, object] = {"ok": False, "message": message, **extra}
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(TrainingRequestError)
def training_request_error(_: Request, exc: TrainingRequestError) -> JSONResponse:
    return _error_response(str(exc), exc.status_code)


@app.exception_handler(TrainingAuthError)
def training_auth_error(_: Request, exc: TrainingAuthError) -> JSONResponse:
    return _error_response(str(exc), exc.status_code)


@app.exception_handler(TrainingPermissionError)
def training_permission_error(_: Request, exc: TrainingPermissionError) -> JSONResponse:
    extra = {key: value for key, value in exc.detail.items() if key != "message"}
    return _error_response(exc.message, exc.status_code, **extra)


@app.exception_handler(TrainingNotFoundError)
def training_not_found_error(_: Request, exc: TrainingNotFoundError) -> JSONResponse:
    return _error_response(str(exc), exc.status_code)


@app.exception_handler(TrainingConflictError)
def training_conflict_error(_: Request, exc: TrainingConflictError) -> JSONResponse:
    return _error_response(exc.message, exc.status_code, blockers=exc.blockers)


for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。"""
    return {"ok": True, "app": settings.app_name, "modules": len(store.module_names())}


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。"""
    return store.overview()
