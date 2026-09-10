from fastapi import APIRouter, Query

from app.services import run_screen

router = APIRouter(prefix="/api")


@router.get("/screen")
def screen(source: str = Query("offline"), top_n: int = Query(10, ge=3, le=12)):
    if source not in ("auto", "offline"):
        source = "offline"
    return run_screen(source, top_n)
