"""LLM client for AlphaQuant (non-strategy purposes only).

SCOPE.md red line: LLM is used ONLY for report summaries, FAQ assistance,
document illustration, and voice synthesis. NEVER for trading strategy
generation, payment, or live trading.

All five API calls use OpenAI-compatible chat/completions format via httpx.
Credentials are read from config.py (which reads .env). If API keys are
missing, functions gracefully degrade to local fallback text.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app.config import (
    LLM_ENABLED,
    LLM_TIMEOUT_SEC,
    QIJI_API_KEY,
    QIJI_BASE_URL,
    QIJI_IMAGE_API_KEY,
    QIJI_IMAGE_BASE_URL,
    QIJI_IMAGE_MODEL_ID,
    QIJI_MODEL_TEXT,
    SENSENOVA_API_KEY,
    SENSENOVA_BASE_URL,
    SENSENOVA_IMAGE_API_KEY,
    SENSENOVA_IMAGE_BASE_URL,
    SENSENOVA_IMAGE_MODEL_ID,
    SENSENOVA_MODEL_ID,
    STEP_API_KEY,
    STEP_BASE_URL,
    STEP_MODEL_FALLBACK1,
    STEP_MODEL_PRIMARY,
    STEP_MODEL_VISION,
    STEP_MODEL_VOICE,
)

logger = logging.getLogger("alphaquant.llm")

# ---------------------------------------------------------------------------
# SCOPE guard -- prevents accidental strategy-generation prompts.
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYWORDS = [
    "strategy",
    "signal",
    "buy",
    "sell",
    "position",
    "trade",
    "portfolio weight",
    "allocation ratio",
    "backtest result",
    "sharpe target",
    "factor weight",
]

_STRATEGY_BLOCK = (
    "SCOPE ALERT: This request may involve trading strategy generation, "
    "which is prohibited by docs/SCOPE.md. Request blocked."
)


def _check_scope(prompt: str) -> None:
    """Raise ValueError if prompt asks for strategy/trading signals."""
    lower = prompt.lower()
    for kw in _FORBIDDEN_KEYWORDS:
        if kw in lower and (
            "generat" in lower or "creat" in lower or "predict" in lower
        ):
            raise ValueError(_STRATEGY_BLOCK)


# ---------------------------------------------------------------------------
# Low-level OpenAI-compatible call
# ---------------------------------------------------------------------------


def _chat_completions(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Call OpenAI-compatible /chat/completions endpoint. Returns parsed JSON."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    payload.update(extra)
    t = timeout or LLM_TIMEOUT_SEC
    with httpx.Client(timeout=t) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _audio_speech(
    base_url: str,
    api_key: str,
    model: str,
    text: str,
    *,
    voice: str = "default",
    timeout: float | None = None,
) -> bytes:
    """Call OpenAI-compatible /audio/speech endpoint. Returns audio bytes."""
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    t = timeout or LLM_TIMEOUT_SEC
    with httpx.Client(timeout=t) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content


def _images_generate(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    *,
    size: str = "1024x1024",
    n: int = 1,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Call OpenAI-compatible /images/generations endpoint. Returns parsed JSON."""
    url = f"{base_url.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": n,
    }
    t = timeout or LLM_TIMEOUT_SEC
    with httpx.Client(timeout=t) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Fallback text (used when API keys missing or call fails)
# ---------------------------------------------------------------------------

_FALLBACK_SUMMARY = (
    "AlphaQuant 风控报告摘要（本地回退）：本报告基于离线合成样本生成，"
    "包含因子选股、风险平价优化、VaR/CVaR 风险度量和 Brinson 归因分析。"
    "风险平价策略在样本内夏普优于等权基准。注意：此为演示系统，非实盘交易。"
)

_FALLBACK_VOICE_TEXT = (
    "AlphaQuant 是基于因子增强与风险平价的智能资产配置演示平台。"
    "核心能力包括十二因子选股、风险平价优化、三种 VaR 风控、"
    "Brinson 归因和投资适当性匹配。当前为离线演示模式。"
)

_FALLBACK_IMAGE_PROMPT = (
    "A professional financial technology dashboard showing "
    "factor analysis, risk parity optimization, and VaR metrics"
)


# ---------------------------------------------------------------------------
# Public API -- five capabilities
# ---------------------------------------------------------------------------


def step_text(
    prompt: str,
    *,
    system: str = "You are a financial report assistant.",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout: float | None = None,
) -> str:
    """1. StepFun text generation (step-3.7-flash).

    Non-strategy use: report summaries, FAQ assistance.
    """
    _check_scope(prompt)
    if not STEP_API_KEY:
        logger.warning("STEP_API_KEY not set, returning fallback text")
        return _FALLBACK_SUMMARY
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    try:
        result = _chat_completions(
            STEP_BASE_URL,
            STEP_API_KEY,
            STEP_MODEL_PRIMARY,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("StepFun text failed (%s), trying fallback model", exc)
        try:
            result = _chat_completions(
                STEP_BASE_URL,
                STEP_API_KEY,
                STEP_MODEL_FALLBACK1,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            return result["choices"][0]["message"]["content"]
        except Exception as exc2:
            logger.error("StepFun fallback also failed: %s", exc2)
            return _FALLBACK_SUMMARY


def step_vision(
    image_b64: str,
    *,
    prompt: str = "Describe this financial chart.",
    temperature: float = 0.3,
    max_tokens: int = 512,
    timeout: float | None = None,
) -> str:
    """2. StepFun vision understanding (step-router-v1).

    Non-strategy use: describing charts/screenshots for documentation.
    """
    _check_scope(prompt)
    if not STEP_API_KEY:
        return "Vision API not configured (STEP_API_KEY missing)."
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ],
        }
    ]
    # .env may store comma-separated model list; use first as primary
    vision_model = STEP_MODEL_VISION.split(",")[0].strip()
    try:
        result = _chat_completions(
            STEP_BASE_URL,
            STEP_API_KEY,
            vision_model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("StepFun vision failed: %s", exc)
        return f"Vision API error: {exc}"


def step_voice(
    text: str,
    *,
    voice: str = "default",
    timeout: float | None = None,
) -> bytes:
    """3. StepFun TTS (stepaudio-2.5-tts).

    Non-strategy use: project voice intro for presentations.
    """
    if not STEP_API_KEY:
        raise RuntimeError("STEP_API_KEY not configured")
    _check_scope(text)
    voice_model = STEP_MODEL_VOICE.split(",")[0].strip()
    return _audio_speech(
        STEP_BASE_URL,
        STEP_API_KEY,
        voice_model,
        text,
        voice=voice,
        timeout=timeout,
    )


def sensenova_text(
    prompt: str,
    *,
    system: str = "You are a financial report assistant.",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout: float | None = None,
) -> str:
    """4. SenseNova text generation (sensenova-6.8-flash-lite).

    Non-strategy use: report summaries, FAQ assistance.
    """
    _check_scope(prompt)
    if not SENSENOVA_API_KEY:
        logger.warning("SENSENOVA_API_KEY not set, returning fallback text")
        return _FALLBACK_SUMMARY
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    try:
        result = _chat_completions(
            SENSENOVA_BASE_URL,
            SENSENOVA_API_KEY,
            SENSENOVA_MODEL_ID,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("SenseNova text failed: %s", exc)
        return _FALLBACK_SUMMARY


def sensenova_vision(
    image_b64: str,
    *,
    prompt: str = "Describe this financial chart.",
    temperature: float = 0.3,
    max_tokens: int = 512,
    timeout: float | None = None,
) -> str:
    """6. SenseNova vision understanding (sensenova-6.8-flash-lite).

    The text model sensenova-6.8-flash-lite is a multimodal agent model
    that supports image input via image_url content blocks through
    chat/completions. The image model sensenova-u1.5-lite only supports
    image generation, NOT vision understanding.

    Non-strategy use: describing charts/screenshots for documentation.
    """
    _check_scope(prompt)
    if not SENSENOVA_API_KEY:
        return "Vision API not configured (SENSENOVA_API_KEY missing)."
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ],
        }
    ]
    try:
        result = _chat_completions(
            SENSENOVA_BASE_URL,
            SENSENOVA_API_KEY,
            SENSENOVA_MODEL_ID,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("SenseNova vision failed: %s", exc)
        return f"Vision API error: {exc}"


def sensenova_image(
    prompt: str,
    *,
    size: str = "1024x1024",
    n: int = 1,
    timeout: float | None = None,
) -> dict[str, Any]:
    """5. SenseNova image generation (sensenova-u1.5-lite).

    Non-strategy use: document illustrations, presentation slides.
    """
    _check_scope(prompt)
    if not SENSENOVA_IMAGE_API_KEY:
        logger.warning("SENSENOVA_IMAGE_API_KEY not set, returning fallback")
        return {"fallback": True, "prompt": prompt or _FALLBACK_IMAGE_PROMPT}
    try:
        return _images_generate(
            SENSENOVA_IMAGE_BASE_URL,
            SENSENOVA_IMAGE_API_KEY,
            SENSENOVA_IMAGE_MODEL_ID,
            prompt or _FALLBACK_IMAGE_PROMPT,
            size=size,
            n=n,
            timeout=timeout,
        )
    except Exception as exc:
        logger.error("SenseNova image failed: %s", exc)
        return {"fallback": True, "error": str(exc), "prompt": prompt}


# ---------------------------------------------------------------------------
# Qiji (OpenAI-compatible relay) -- text + image
# ---------------------------------------------------------------------------


def qiji_text(
    prompt: str,
    *,
    system: str = "You are a financial report assistant.",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout: float | None = None,
) -> str:
    """7. Qiji text generation (gpt-5.6-sol).

    OpenAI-compatible relay. Non-strategy use: report summaries, FAQ.
    """
    _check_scope(prompt)
    if not QIJI_API_KEY:
        logger.warning("QIJI_API_KEY not set, returning fallback text")
        return _FALLBACK_SUMMARY
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    try:
        result = _chat_completions(
            QIJI_BASE_URL,
            QIJI_API_KEY,
            QIJI_MODEL_TEXT,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("Qiji text failed: %s", exc)
        return _FALLBACK_SUMMARY


def qiji_image(
    prompt: str,
    *,
    size: str = "1024x1024",
    n: int = 1,
    timeout: float | None = None,
) -> dict[str, Any]:
    """8. Qiji image generation (gpt-image-2-vip).

    OpenAI-compatible relay, per-call billing. Non-strategy use: document
    illustrations, presentation slides.
    """
    _check_scope(prompt)
    if not QIJI_IMAGE_API_KEY:
        logger.warning("QIJI_IMAGE_API_KEY not set, returning fallback")
        return {"fallback": True, "prompt": prompt or _FALLBACK_IMAGE_PROMPT}
    try:
        return _images_generate(
            QIJI_IMAGE_BASE_URL,
            QIJI_IMAGE_API_KEY,
            QIJI_IMAGE_MODEL_ID,
            prompt or _FALLBACK_IMAGE_PROMPT,
            size=size,
            n=n,
            timeout=timeout,
        )
    except Exception as exc:
        logger.error("Qiji image failed: %s", exc)
        return {"fallback": True, "error": str(exc), "prompt": prompt}


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------


def llm_status() -> dict[str, Any]:
    """Return current LLM configuration status (no secrets)."""
    return {
        "enabled": LLM_ENABLED,
        "providers": {
            "stepfun": {
                "configured": bool(STEP_API_KEY),
                "base_url": STEP_BASE_URL,
                "models": {
                    "text": STEP_MODEL_PRIMARY,
                    "vision": STEP_MODEL_VISION,
                    "voice": STEP_MODEL_VOICE,
                    "fallback": STEP_MODEL_FALLBACK1,
                },
            },
            "sensenova_text": {
                "configured": bool(SENSENOVA_API_KEY),
                "base_url": SENSENOVA_BASE_URL,
                "model": SENSENOVA_MODEL_ID,
            },
            "sensenova_image": {
                "configured": bool(SENSENOVA_IMAGE_API_KEY),
                "base_url": SENSENOVA_IMAGE_BASE_URL,
                "model": SENSENOVA_IMAGE_MODEL_ID,
                "capabilities": ["image_generation", "vision_understanding"],
            },
            "qiji_text": {
                "configured": bool(QIJI_API_KEY),
                "base_url": QIJI_BASE_URL,
                "model": QIJI_MODEL_TEXT,
                "billing": "per_token",
            },
            "qiji_image": {
                "configured": bool(QIJI_IMAGE_API_KEY),
                "base_url": QIJI_IMAGE_BASE_URL,
                "model": QIJI_IMAGE_MODEL_ID,
                "billing": "per_call",
            },
        },
        "scope_guard": "LLM used for report summaries, FAQ, illustrations, TTS only. Strategy generation is blocked.",
        "timeout_sec": LLM_TIMEOUT_SEC,
    }
