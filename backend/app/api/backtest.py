from fastapi import APIRouter, Query

from app.services import run_backtest, run_walk_forward

router = APIRouter(prefix="/api")


@router.get("/backtest")
def backtest(
    source: str = Query("offline"),
    strategy: str = Query("multi_factor"),
    cost: float = Query(0.0015, ge=0.0, le=0.02),
):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_backtest(source, strategy, cost)


@router.get("/backtest/walk-forward")
def walk_forward(
    source: str = Query("offline"),
    train_ratio: float = Query(0.714, ge=0.5, le=0.9),
    cost: float = Query(0.0015, ge=0.0, le=0.02),
):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_walk_forward(source, train_ratio, cost)
