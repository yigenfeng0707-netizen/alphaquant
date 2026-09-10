from fastapi import APIRouter, Query

from app.services import run_brinson, run_brinson_multi

router = APIRouter(prefix="/api")


@router.get("/attribution/brinson")
def brinson(
    source: str = Query("offline"),
    method: str = Query("risk_parity"),
    top_n: int = Query(10, ge=3, le=12),
    codes: str | None = Query(None),
):
    if source not in ("auto", "offline"):
        source = "offline"
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    return run_brinson(source, method, top_n, code_list)


@router.get("/attribution/brinson/multi-period")
def brinson_multi(
    source: str = Query("offline"),
    method: str = Query("risk_parity"),
    top_n: int = Query(10, ge=3, le=12),
    codes: str | None = Query(None),
    n_periods: int = Query(4, ge=2, le=12),
):
    if source not in ("auto", "offline"):
        source = "offline"
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    return run_brinson_multi(source, method, top_n, code_list, n_periods)
