import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.attribution import router as attribution_router
from app.api.backtest import router as backtest_router
from app.api.case1 import router as case1_router
from app.api.case2 import router as case2_router
from app.api.optimize import router as optimize_router
from app.api.risk import router as risk_router
from app.api.screen import router as screen_router
from app.api.suitability import router as suitability_router
from app.api import router as health_router
from app.config import APP_NAME, APP_VERSION, DISCLAIMER, ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


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

app.include_router(health_router)
app.include_router(screen_router)
app.include_router(backtest_router)
app.include_router(optimize_router)
app.include_router(risk_router)
app.include_router(case1_router)
app.include_router(suitability_router)
app.include_router(attribution_router)
app.include_router(case2_router)


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
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
