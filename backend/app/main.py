import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.attribution import router as attribution_router
from app.api.backtest import router as backtest_router
from app.api.case1 import router as case1_router
from app.api.case2 import router as case2_router
from app.api.llm import router as llm_router
from app.api.optimize import router as optimize_router
from app.api.risk import router as risk_router
from app.api.screen import router as screen_router
from app.api.suitability import router as suitability_router
from app.api import router as health_router
from app.config import APP_NAME, APP_VERSION, DISCLAIMER, ROOT

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

# 启动预热：对主要业务读接口各请求一次，触发数据加载与计算缓存，
# 消除公网首次访问（冷启动首轮 TTFB 1.5-2.2s）的等待。
WARMUP_PATHS = (
    "/api/screen",
    "/api/backtest/walk-forward",
    "/api/suitability",
    "/api/optimize",
)


async def _warmup(app: FastAPI) -> None:
    """通过 ASGI in-process 调用触发业务路由预热，不依赖外部端口。"""
    timeout = httpx.Timeout(90.0, connect=10.0)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://warmup", timeout=timeout
    ) as client:
        for path in WARMUP_PATHS:
            try:
                resp = await client.get(path)
                logging.info("warmup %s -> %s", path, resp.status_code)
            except Exception as exc:  # noqa: BLE001 预热失败不阻断启动
                logging.warning("warmup %s failed: %s", path, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.wait_for(_warmup(app), timeout=120.0)
    except Exception as exc:  # noqa: BLE001
        logging.warning("warmup aborted (server still starting): %s", exc)
    yield


def resolve_static_dir() -> Path | None:
    raw = os.environ.get("STATIC_DIR", "").strip()
    candidates = []
    if raw:
        candidates.append(Path(raw))
    candidates.append(ROOT / "frontend" / "dist")
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    return None


STATIC_DIR = resolve_static_dir()

app = FastAPI(
    title=f"{APP_NAME} API",
    version=APP_VERSION,
    description="因子增强选股 + 风险平价配置演示接口。非实盘。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.ms\.show",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# gzip 压缩所有响应（含 /assets 静态资源与 JSON API）。
# 注意：StaticFiles 不会自动挑选 *.gz 文件，因此 gzip 必须在响应层完成；
# 最小 500B 才压缩，小响应零开销。
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(health_router)
app.include_router(screen_router)
app.include_router(backtest_router)
app.include_router(optimize_router)
app.include_router(risk_router)
app.include_router(case1_router)
app.include_router(suitability_router)
app.include_router(attribution_router)
app.include_router(case2_router)
app.include_router(llm_router)


@app.get("/")
def root():
    if STATIC_DIR is not None:
        return FileResponse(STATIC_DIR / "index.html")
    return {
        "ok": True,
        "service": APP_NAME,
        "docs": "/docs",
        "health": "/health",
        "disclaimer": DISCLAIMER,
    }


if STATIC_DIR is not None:
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # P3：未知 /api/* 路径返回 404 JSON，与 SPA fallback（200 + index.html）区分，
        # 避免三层验证与前端误判——只有真正注册过的 /api 路由才应返回业务 JSON。
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                {"ok": False, "error": "api endpoint not found"},
                status_code=404,
            )
        static_dir = STATIC_DIR
        if static_dir is None:  # 理论上不可达：本函数仅在 STATIC_DIR 存在时注册
            return JSONResponse(
                {"ok": False, "error": "static assets unavailable"}, status_code=503
            )
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
