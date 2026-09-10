from fastapi import APIRouter

from app.config import APP_NAME, APP_VERSION, DISCLAIMER

router = APIRouter()


@router.get("/health")
def health():
    return {
        "ok": True,
        "service": APP_NAME,
        "version": APP_VERSION,
        "disclaimer": DISCLAIMER,
        "stack": "FastAPI + Vue3",
    }
