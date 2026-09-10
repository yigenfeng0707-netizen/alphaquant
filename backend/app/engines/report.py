"""Standardized demo risk report JSON + compact md/html export."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.config import REPORTS_DIR
from app.utils import json_safe


def build_risk_report_doc(
    *,
    data_source: str,
    disclaimer: str,
    notional: float,
    picks: list[dict],
    method: str,
    method_label: str,
    metrics: dict,
    weights: list[dict],
    var_cvar: dict,
    stress: list,
    attribution: dict,
    batch_strategies: list[dict] | None = None,
) -> dict:
    return json_safe(
        {
            "title": "AlphaQuant 标准化风控报告（演示）",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "data_source": data_source,
            "disclaimer": disclaimer,
            "scenario": "小型私募量化研究流程演示，不是已管理实盘规模。",
            "notional": {
                "amount": notional,
                "label": f"名义本金 {notional:,.0f} 元（演示口径，不是已管理 1 亿实盘）",
            },
            "portfolio": {
                "method": method,
                "method_label": method_label,
                "picks": picks,
                "weights": weights,
                "metrics": metrics,
            },
            "var_cvar": var_cvar,
            "stress": stress,
            "attribution": {
                "allocation": attribution.get("allocation"),
                "selection": attribution.get("selection"),
                "interaction": attribution.get("interaction"),
                "excess_return": attribution.get("excess_return"),
                "explain": attribution.get("explain"),
                "sectors": attribution.get("sectors"),
            },
            "batch_backtest": batch_strategies or [],
            "limits_note": "本报告为研究演示输出，不可替代监管报备、托管估值或投资建议。",
        }
    )


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{float(v) * 100:.2f}%"


def to_markdown(doc: dict) -> str:
    m = doc.get("portfolio", {}).get("metrics") or {}
    attr = doc.get("attribution") or {}
    lines = [
        f"# {doc.get('title')}",
        "",
        f"- 生成时间：{doc.get('generated_at')}",
        f"- 数据源：{doc.get('data_source')}",
        f"- {doc.get('notional', {}).get('label')}",
        f"- {doc.get('disclaimer')}",
        "",
        "## 组合",
        f"- 方法：{doc.get('portfolio', {}).get('method_label')}",
        f"- 年化：{_pct(m.get('annual_return'))}；夏普：{m.get('sharpe')}",
        f"- 最大回撤：{_pct(m.get('max_drawdown'))}；波动：{_pct(m.get('volatility'))}",
        "",
        "## Brinson 归因",
        f"- 配置效应：{_pct(attr.get('allocation'))}",
        f"- 选择效应：{_pct(attr.get('selection'))}",
        f"- 交互效应：{_pct(attr.get('interaction'))}",
        f"- 超额：{_pct(attr.get('excess_return'))}",
        "",
        str(attr.get("explain") or ""),
        "",
        "## 压力测试（摘要）",
    ]
    for row in doc.get("stress") or []:
        lines.append(f"- {row.get('label')}：{_pct(row.get('loss'))}")
    lines.extend(["", "## 声明", doc.get("limits_note") or "", ""])
    return "\n".join(lines)


def to_html(doc: dict) -> str:
    md = to_markdown(doc).replace("&", "&amp;").replace("<", "&lt;")
    body = "<br/>\n".join(md.split("\n"))
    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'/>"
        f"<title>{doc.get('title')}</title></head><body>"
        f"<pre style='font-family:Microsoft YaHei,sans-serif;white-space:pre-wrap'>{body}</pre>"
        "</body></html>"
    )


def export_report(doc: dict, fmt: str = "md") -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fmt = "html" if fmt == "html" else "md"
    name = f"case2-risk-{stamp}.{fmt}"
    path: Path = REPORTS_DIR / name
    text = to_html(doc) if fmt == "html" else to_markdown(doc)
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "filename": name, "format": fmt, "bytes": path.stat().st_size}
