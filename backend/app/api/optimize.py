from fastapi import APIRouter, Query

from app.services import run_optimize

router = APIRouter(prefix="/api")


@router.get("/optimize")
def optimize(
    source: str = Query("offline"),
    top_n: int = Query(10, ge=3, le=12),
    codes: str | None = Query(None, description="逗号分隔代码，缺省则用因子选股结果"),
):
    if source not in ("auto", "offline"):
        source = "offline"
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    return run_optimize(source, code_list, top_n)
