from fastapi import APIRouter, Query

from app.services import run_case1

router = APIRouter(prefix="/api")


@router.get("/case1")
def case1(
    source: str = Query("offline"),
    top_n: int = Query(10, ge=3, le=12),
    capital: float = Query(100000, gt=0),
    cost: float = Query(0.0015, ge=0.0, le=0.02),
):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_case1(source, top_n, capital, cost)
