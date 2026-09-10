from fastapi import APIRouter, Query

from app.services import run_backtest

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
