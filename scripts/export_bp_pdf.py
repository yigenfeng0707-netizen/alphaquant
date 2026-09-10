"""Export AlphaQuant 申报书 Markdown -> print HTML -> Playwright PDF."""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "bp" / "AlphaQuant-项目申报书.md"
OUT_DIR = ROOT / "docs" / "bp"
DATE = "20260910"


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def md_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*-+", lines[i + 1]):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                if re.match(r"^\|?\s*-+", raw):
                    i += 1
                    continue
                cells = [c.strip() for c in raw.strip("|").split("|")]
                rows.append(cells)
                i += 1
            if rows:
                out.append("<table>")
                head, *body = rows
                out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>")
                out.append("<tbody>")
                for r in body:
                    out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
                out.append("</tbody></table>")
            continue

        if stripped == "---":
            close_lists()
            out.append("<hr/>")
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + "<br/>".join(inline(q) for q in quote) + "</blockquote>")
            continue

        if re.match(r"^[-*]\s+", stripped):
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(re.sub(r'^[-*]\\s+', '', stripped))}</li>")
            i += 1
            continue

        if re.match(r"^\d+\.\s+", stripped):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline(re.sub(r'^\\d+\\.\\s+', '', stripped))}</li>")
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        close_lists()
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt.startswith("|")
                or nxt.startswith(">")
                or nxt == "---"
                or re.match(r"^[-*]\s+", nxt)
                or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para.append(nxt)
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")

    close_lists()
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
* { box-sizing: border-box; }
html, body {
  font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", sans-serif;
  color: #1b2433;
  font-size: 11.5pt;
  line-height: 1.55;
  margin: 0;
}
.banner {
  background: #0b1220;
  color: #f5efe0;
  padding: 22px 24px 18px;
  margin: -8px -8px 20px;
  border-bottom: 5px solid #c9a227;
}
.banner .brand { color: #c9a227; font-weight: 800; letter-spacing: 0.08em; font-size: 12pt; }
.banner h1 { color: #fff; font-size: 18pt; margin: 8px 0 6px; border: 0; padding: 0; }
.banner .meta { color: #b8c3d6; font-size: 10pt; }
h1 { font-size: 16pt; color: #0b1220; border-bottom: 2px solid #c9a227; padding-bottom: 6px; margin: 22px 0 10px; }
h2 { font-size: 13.5pt; color: #0b1220; margin: 18px 0 8px; }
h3 { font-size: 12pt; color: #243049; margin: 14px 0 6px; }
p { margin: 8px 0; }
blockquote {
  background: #fff8e8;
  border-left: 4px solid #c9a227;
  margin: 12px 0;
  padding: 8px 12px;
  color: #3a3018;
}
table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 10.5pt; }
th { background: #0b1220; color: #c9a227; text-align: left; padding: 6px 8px; }
td { border: 1px solid #d7deea; padding: 6px 8px; vertical-align: top; }
tr:nth-child(even) td { background: #f6f8fb; }
code { background: #eef2f7; padding: 1px 4px; font-size: 10pt; }
ul, ol { margin: 6px 0 10px 1.2em; }
hr { border: 0; border-top: 1px solid #d7deea; margin: 16px 0; }
.foot {
  margin-top: 24px;
  font-size: 9.5pt;
  color: #5b6b82;
  border-top: 1px solid #d7deea;
  padding-top: 8px;
}
"""


def wrap_document(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>AlphaQuant 项目申报书</title>
<style>{CSS}</style>
</head>
<body>
<div class="banner">
  <div class="brand">ALPHAQUANT · 金融科技赛道</div>
  <h1>AlphaQuant — 基于因子增强与风险平价的智能资产配置平台</h1>
  <div class="meta">2026 上海（长三角）中青年工程师创新创业大赛 · 黄浦承办 · 导出日期 2026-09-10 · 演示非实盘</div>
</div>
{body}
<div class="foot">
  本稿由 Markdown 源导出。2027 年大模型策略与 10 万用户目标均为规划，不是已交付。
  扫描件旧稿勿提交。身份证 / 推荐表不随本 PDF 附带。
</div>
</body>
</html>
"""


def export_pdf(src: Path, pdf_path: Path, html_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    md = src.read_text(encoding="utf-8")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(wrap_document(md_to_html(md)), encoding="utf-8")

    with sync_playwright() as p:
        browser = None
        for launcher in (
            lambda: p.chromium.launch(headless=True, channel="msedge"),
            lambda: p.chromium.launch(headless=True, channel="chrome"),
            lambda: p.chromium.launch(headless=True),
        ):
            try:
                browser = launcher()
                break
            except Exception:
                continue
        if browser is None:
            raise RuntimeError("无法启动 Chromium/Edge/Chrome")
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
        )
        browser.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--pdf", default=str(OUT_DIR / f"AlphaQuant-项目申报书-{DATE}.pdf"))
    args = ap.parse_args()
    src = Path(args.src)
    pdf_path = Path(args.pdf)
    html_path = pdf_path.with_suffix(".html")
    export_pdf(src, pdf_path, html_path)
    size = pdf_path.stat().st_size
    print(f"PDF {pdf_path} ({size} bytes)")
    print(f"HTML {html_path}")
    if size < 10_000:
        raise SystemExit("PDF too small")


if __name__ == "__main__":
    main()
