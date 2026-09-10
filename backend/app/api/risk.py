from fastapi import APIRouter, Query

from app.services import run_risk

router = APIRouter(prefix="/api")


@router.get("/risk")
def risk(
    source: str = Query("offline"),
    top_n: int = Query(10, ge=3, le=12),
    method: str = Query("risk_parity"),
    codes: str | None = Query(None),
):
    if source not in ("auto", "offline"):
        source = "offline"
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    return run_risk(source, code_list, method, top_n)
