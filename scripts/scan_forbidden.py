"""Scan submission texts/PDF/PPTX XML for contest forbidden phrases."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDLES = [
    "QuantInsight",
    "永字",
    "HS300 8.56",
    "沪深300 8.56",
    "AFAC",
    "已接入大模型",
    "已有 10 万用户",
    "已有10万用户",
    "真·持仓",
    "已管理 1 亿",
    "已管理1亿",
    "慧点资本",
    "TenderPilot",
]


def read_pdf(p: Path) -> str:
    import fitz

    doc = fitz.open(p)
    return "\n".join(page.get_text() for page in doc)


def read_pptx(p: Path) -> str:
    parts = []
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            if name.startswith("ppt/slides/") and name.endswith(".xml"):
                parts.append(z.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(parts)


def scan(label: str, text: str) -> list[str]:
    hits = []
    for n in NEEDLES:
        if n.lower() in text.lower() if n.isascii() else n in text:
            hits.append(n)
    if hits:
        print(f"[HIT] {label}: {hits}")
    else:
        print(f"[CLEAN] {label}")
    return hits


def main() -> int:
    hits_all: list[str] = []
    files = [
        ROOT / "docs" / "bp" / "AlphaQuant-项目申报书.md",
        ROOT / "docs" / "bp" / f"AlphaQuant-项目申报书-20260910.pdf",
        ROOT / "docs" / "pitch" / "AlphaQuant-路演PPT-20260910.pptx",
        ROOT / "docs" / "冲击冠军计划.md",
        ROOT / "delivery" / "00_README_交付总览.md",
        ROOT / "demo.storyboard.json",
    ]
    extra = sys.argv[1:]
    for p in list(files) + [Path(x) for x in extra]:
        if not p.exists():
            print(f"[SKIP] {p}")
            continue
        if p.suffix.lower() == ".pdf":
            text = read_pdf(p)
        elif p.suffix.lower() == ".pptx":
            text = read_pptx(p)
        else:
            text = p.read_text(encoding="utf-8", errors="ignore")
        hits_all.extend(scan(str(p), text))
    return 1 if hits_all else 0


if __name__ == "__main__":
    raise SystemExit(main())
