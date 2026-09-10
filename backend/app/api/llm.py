"""LLM API routes for AlphaQuant.

SCOPE.md red line: LLM is used ONLY for report summaries, FAQ assistance,
document illustrations, and voice synthesis. NEVER for trading strategy
generation, payment, or live trading.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import (
    generate_doc_illustration,
    generate_report_summary,
    generate_spoken_intro,
    run_llm_status,
    run_llm_vision,
)

router = APIRouter(prefix="/api/llm")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class VisionRequest(BaseModel):
    image_b64: str
    prompt: str = "Describe this financial chart."


class IllustrationRequest(BaseModel):
    prompt: str = ""
    provider: str = "sensenova_image"


class VoiceRequest(BaseModel):
    text: str = ""
    provider: str = "stepfun"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
def llm_status():
    """LLM configuration status (no secrets exposed)."""
    return run_llm_status()


@router.get("/summary")
def llm_summary(
    source: str = Query("offline"),
    provider: str = Query("stepfun"),
):
    """Generate a risk report summary via LLM (non-strategy)."""
    if source not in ("auto", "offline"):
        source = "offline"
    if provider not in ("stepfun", "sensenova", "qiji"):
        provider = "stepfun"
    return generate_report_summary(source, provider=provider)


@router.post("/voice")
def llm_voice(req: VoiceRequest):
    """Generate a spoken project intro via TTS (non-strategy)."""
    return generate_spoken_intro(text=req.text, provider=req.provider)


@router.post("/illustration")
def llm_illustration(req: IllustrationRequest):
    """Generate a document illustration image (non-strategy)."""
    provider = (
        req.provider
        if req.provider in ("sensenova_image", "qiji_image")
        else "sensenova_image"
    )
    return generate_doc_illustration(prompt=req.prompt, provider=provider)


@router.post("/vision")
def llm_vision(req: VisionRequest):
    """Describe a financial chart image via vision model (non-strategy)."""
    return run_llm_vision(req.image_b64, prompt=req.prompt)
