from fastapi import APIRouter, Query

from app.config import CASE2_NOTIONAL, DEFAULT_COST
from app.schemas import Case2ExportIn
from app.services import run_case2

router = APIRouter(prefix="/api")


@router.get("/case2")
def case2_get(
    source: str = Query("offline"),
    top_n: int = Query(10, ge=3, le=12),
    cost: float = Query(DEFAULT_COST, ge=0.0, le=0.02),
    notional: float = Query(CASE2_NOTIONAL, gt=0),
):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_case2(source, top_n, cost, notional, export_fmt=None)


@router.post("/case2/export")
def case2_export(body: Case2ExportIn):
    return run_case2(body.source, body.top_n, body.cost, body.notional, export_fmt=body.fmt)
