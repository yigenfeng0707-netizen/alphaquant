"""Verify delivery pack files, sizes, PDF pages, PPTX slides."""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "delivery"


def main() -> None:
    import fitz
    from pptx import Presentation

    pdf = ROOT / "docs" / "bp" / "AlphaQuant-项目申报书-20260910.pdf"
    pptx = ROOT / "docs" / "pitch" / "AlphaQuant-路演PPT-20260910.pptx"
    mp4 = ROOT / "docs" / "demo" / "AlphaQuant-演示-20260910.mp4"
    doc = fitz.open(pdf)
    print(f"PDF pages={doc.page_count} size={pdf.stat().st_size}")
    print("PDF p1 excerpt:", doc[0].get_text()[:400].replace("\n", " | "))
    prs = Presentation(str(pptx))
    print(f"PPTX slides={len(prs.slides)} size={pptx.stat().st_size}")
    print(f"MP4 size={mp4.stat().st_size}")
    print("--- delivery tree ---")
    missing = []
    for p in sorted(DEST.rglob("*")):
        if p.is_file():
            rel = p.relative_to(DEST)
            print(f"{p.stat().st_size:10d}  {rel}")
    readme = (DEST / "00_README_交付总览.md").read_text(encoding="utf-8")
    for name in [
        "01_申报书",
        "02_PPT",
        "03_Demo说明",
        "04_视频",
        "05_手册",
        "06_仓库说明",
        "07_冲击冠军计划",
        "DEMO_URL_待填.txt",
        "AlphaQuant-项目申报书-20260910.pdf",
        "AlphaQuant-路演PPT-20260910.pptx",
    ]:
        ok = (DEST / name).exists() or any(DEST.rglob(name))
        print(f"link {name}: {'OK' if ok else 'MISSING'}")
        if not ok:
            missing.append(name)
    srt = ROOT / "demo-output" / "subtitles.srt"
    if srt.exists():
        text = srt.read_text(encoding="utf-8")
        bad = [n for n in ["QuantInsight", "已接入大模型", "已有 10 万用户", "已管理 1 亿"] if n in text]
        print("subs hits:", bad or "none")
    if missing:
        raise SystemExit(1)
    print("VERIFY_OK")


if __name__ == "__main__":
    main()
