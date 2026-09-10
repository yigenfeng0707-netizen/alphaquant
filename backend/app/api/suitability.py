from fastapi import APIRouter, HTTPException, Query

from app.engines.suitability import read_audit
from app.schemas import SuitabilityEvaluateIn
from app.services import run_suitability_evaluate, run_suitability_get

router = APIRouter(prefix="/api")


@router.get("/suitability")
def suitability_get(source: str = Query("offline"), top_n: int = Query(10, ge=3, le=12)):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_suitability_get(source, top_n)


@router.get("/suitability/logs")
def suitability_logs(limit: int = Query(20, ge=1, le=100)):
    return {"ok": True, "implemented": True, "logs": read_audit(limit)}


@router.post("/suitability/evaluate")
def suitability_evaluate(body: SuitabilityEvaluateIn):
    try:
        return run_suitability_evaluate(
            answers=body.answers,
            source=body.source,
            method=body.method,
            session_label=body.session_label,
            top_n=body.top_n,
            write_audit=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
