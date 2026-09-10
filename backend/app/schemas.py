from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceMode = Literal["auto", "offline"]


class SourceQuery(BaseModel):
    source: SourceMode = "offline"
    top_n: int = Field(10, ge=3, le=12)
    cost: float = Field(0.0015, ge=0.0, le=0.02)
    capital: float = Field(100_000, gt=0)
    strategy: str = "multi_factor"
    method: str = "risk_parity"
    codes: list[str] | None = None


class SuitabilityEvaluateIn(BaseModel):
    answers: dict[str, int]
    source: SourceMode = "offline"
    method: str = "risk_parity"
    session_label: str = Field("本地演示", max_length=32)
    top_n: int = Field(10, ge=3, le=12)


class Case2ExportIn(BaseModel):
    source: SourceMode = "offline"
    fmt: Literal["md", "html"] = "md"
    top_n: int = Field(10, ge=3, le=12)
    cost: float = Field(0.0015, ge=0.0, le=0.02)
    notional: float = Field(100_000_000, gt=0)
