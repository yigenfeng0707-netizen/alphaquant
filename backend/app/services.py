from __future__ import annotations

import pandas as pd

from app.config import CASE1_TOP_N, CASE2_NOTIONAL, DEFAULT_CAPITAL, DEFAULT_COST
from app.data.provider import MarketData, daily_returns, get_market
from app.engines.attribution import brinson_fachler, multi_period_brinson
from app.engines.backtest import (
    backtest_all,
    run_strategy,
    equal_weight_index,
    walk_forward_backtest,
)
from app.engines.factors import screen_stocks
from app.engines.optimizer import optimize_basket
from app.engines.report import build_risk_report_doc, export_report
from app.engines.risk import risk_report
from app.engines.suitability import (
    append_audit,
    build_audit_record,
    match_portfolio,
    questionnaire,
    read_audit,
    score_answers,
)
from app.llm_client import (
    llm_status,
    qiji_image,
    qiji_text,
    sensenova_image,
    sensenova_text,
    sensenova_vision,
    step_text,
    step_voice,
    step_vision,
)
from app.utils import json_safe


def _close_df(m: MarketData, cols: list[str]) -> pd.DataFrame:
    """Type-safe column selection from close prices.

    pyright/pandas-stubs flag ``df[list]`` and ``df.reindex(columns=list)``
    as ``Series | DataFrame``.  This helper confines the type-ignore to a
    single place so all call sites stay clean.
    """
    return m.close.reindex(columns=cols)  # type: ignore[return-value]


def envelope(
    data: dict, market_source: str, disclaimer: str, extra: dict | None = None
) -> dict:
    body = {
        "ok": True,
        "data_source": market_source,
        "disclaimer": disclaimer,
        "data": data,
    }
    if extra:
        body.update(extra)
    return json_safe(body)


def run_screen(source: str, top_n: int = 10) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    payload = screen_stocks(m, top_n=top_n)
    return envelope(payload, m.source, m.disclaimer)


def run_backtest(source: str, strategy: str, cost: float) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    idx = equal_weight_index(m.close)
    one = run_strategy(idx, strategy, cost, data=m)
    all_s = backtest_all(m.close, cost, data=m)
    return envelope({"selected": one, "all": all_s}, m.source, m.disclaimer)


def run_walk_forward(
    source: str = "offline", train_ratio: float = 0.714, cost: float = DEFAULT_COST
) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    wf = walk_forward_backtest(m, train_ratio=train_ratio, cost=cost)
    return envelope(wf, m.source, m.disclaimer)


def _name_map(m) -> dict[str, str]:
    if "name" not in m.universe.columns:
        return {}
    return {str(r["code"]): str(r["name"]) for _, r in m.universe.iterrows()}


def run_optimize(
    source: str,
    codes: list[str] | None,
    top_n: int,
    sector_neutral: bool = False,
) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    if not codes:
        picks = screen_stocks(m, top_n=top_n)["picks"]
        codes = [p["code"] for p in picks]
    cols = [c for c in codes if c in m.close.columns]
    if len(cols) < 3:
        cols = list(m.close.columns)[: max(top_n, 3)]
    rets = daily_returns(_close_df(m, cols))
    opt = optimize_basket(
        rets,
        names=_name_map(m),
        universe=m.universe,
        sector_neutral=sector_neutral,
    )
    opt["codes"] = cols
    return envelope(opt, m.source, m.disclaimer)


def run_risk(source: str, codes: list[str] | None, method: str, top_n: int) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    if not codes:
        picks = screen_stocks(m, top_n=top_n)["picks"]
        codes = [p["code"] for p in picks]
    cols = [c for c in codes if c in m.close.columns]
    rets = daily_returns(_close_df(m, cols))
    opt = optimize_basket(rets, names=_name_map(m))
    method = method if method in opt["methods"] else "risk_parity"
    wtab = opt["methods"][method]["weights"]
    weights = pd.Series({row["code"]: row["weight"] for row in wtab})
    report = risk_report(rets, weights, _close_df(m, cols))
    report["method"] = method
    report["weights"] = wtab
    return envelope(report, m.source, m.disclaimer)


def run_case1(
    source: str = "offline",
    top_n: int = CASE1_TOP_N,
    capital: float = DEFAULT_CAPITAL,
    cost: float = DEFAULT_COST,
) -> dict:
    m = get_market(source)  # type: ignore[arg-type]
    screen = screen_stocks(m, top_n=top_n)
    codes = [p["code"] for p in screen["picks"]]
    rets = daily_returns(_close_df(m, codes))
    opt = optimize_basket(rets, names=_name_map(m))
    w_rp = pd.Series(
        {r["code"]: r["weight"] for r in opt["methods"]["risk_parity"]["weights"]}
    )
    risk = risk_report(rets, w_rp, _close_df(m, codes))
    rp = opt["methods"]["risk_parity"]["metrics"]
    eq = opt["methods"]["equal_weight"]["metrics"]
    notional = {
        "capital": capital,
        "cost": cost,
        "rp_end_value": capital * (1.0 + rp["total_return"]),
        "eq_end_value": capital * (1.0 + eq["total_return"]),
    }
    data = {
        "story": "持有10万元闲置资金：因子选股 → 风险平价 → VaR/压力测试。夏普对比为样本内历史模拟。",
        "picks": screen["picks"],
        "factor_count": screen["factor_count"],
        "diagnostics": screen["diagnostics"],
        "optimize": opt,
        "risk": risk,
        "notional": notional,
        "sharpe_rp": opt["sharpe_rp"],
        "sharpe_eq": opt["sharpe_eq"],
        "sharpe_rp_better": opt["sharpe_rp_better"],
    }
    return envelope(data, m.source, m.disclaimer)


def _basket(
    source: str, codes: list[str] | None, top_n: int, sector_neutral: bool = False
):
    m = get_market(source)  # type: ignore[arg-type]
    screen = screen_stocks(m, top_n=top_n)
    if not codes:
        codes = [p["code"] for p in screen["picks"]]
    cols = [c for c in codes if c in m.close.columns]
    if len(cols) < 3:
        cols = list(m.close.columns)[: max(top_n, 3)]
    rets = daily_returns(_close_df(m, cols))
    opt = optimize_basket(
        rets,
        names=_name_map(m),
        universe=m.universe,
        sector_neutral=sector_neutral,
    )
    return m, screen, cols, rets, opt


def run_brinson(
    source: str,
    method: str = "risk_parity",
    top_n: int = 10,
    codes: list[str] | None = None,
) -> dict:
    m, screen, cols, rets, opt = _basket(source, codes, top_n)
    method = method if method in opt["methods"] else "risk_parity"
    wtab = opt["methods"][method]["weights"]
    wp = pd.Series({r["code"]: r["weight"] for r in wtab})
    eq = opt["methods"]["equal_weight"]["weights"]
    wb = pd.Series({r["code"]: r["weight"] for r in eq})
    attr = brinson_fachler(
        _close_df(m, cols),
        wp,
        wb,
        universe=m.universe,
        names=_name_map(m),
    )
    attr["method"] = method
    attr["method_label"] = opt["methods"][method]["label"]
    attr["picks"] = screen["picks"]
    return envelope(attr, m.source, m.disclaimer, extra={"implemented": True})


def run_brinson_multi(
    source: str,
    method: str = "risk_parity",
    top_n: int = 10,
    codes: list[str] | None = None,
    n_periods: int = 4,
) -> dict:
    m, screen, cols, rets, opt = _basket(source, codes, top_n)
    method = method if method in opt["methods"] else "risk_parity"
    wtab = opt["methods"][method]["weights"]
    wp = pd.Series({r["code"]: r["weight"] for r in wtab})
    eq = opt["methods"]["equal_weight"]["weights"]
    wb = pd.Series({r["code"]: r["weight"] for r in eq})
    attr = multi_period_brinson(
        _close_df(m, cols),
        wp,
        wb,
        universe=m.universe,
        names=_name_map(m),
        n_periods=n_periods,
    )
    attr["method"] = method
    attr["method_label"] = opt["methods"][method]["label"]
    attr["picks"] = screen["picks"]
    return envelope(attr, m.source, m.disclaimer, extra={"implemented": True})


def run_suitability_get(source: str = "offline", top_n: int = 10) -> dict:
    q = questionnaire()
    return {
        "ok": True,
        "implemented": True,
        "disclaimer": "适当性为本地演示规则，不含证件号，不构成正式合规认定。",
        "questionnaire": q,
        "evaluate_path": "POST /api/suitability/evaluate",
        "recent_logs": read_audit(12),
    }


def run_suitability_evaluate(
    answers: dict,
    source: str = "offline",
    method: str = "risk_parity",
    session_label: str = "本地演示",
    top_n: int = 10,
    write_audit: bool = True,
) -> dict:
    scored = score_answers(answers)
    m, screen, cols, rets, opt = _basket(source, None, top_n)
    method = method if method in opt["methods"] else "risk_parity"
    bundle = opt["methods"][method]
    match = match_portfolio(
        scored["profile_id"],
        method,
        bundle["metrics"],
        bundle["weights"],
        equity_weight=1.0,
    )
    rec = build_audit_record(
        scored=scored,
        match=match,
        session_label=session_label,
        data_source=m.source,
        method=method,
    )
    audit_file = append_audit(rec) if write_audit else None
    data = {
        "score": scored["score"],
        "profile_id": scored["profile_id"],
        "profile_label": scored["profile_label"],
        "answers_summary": rec["answers_summary"],
        "match": match,
        "portfolio_method": method,
        "metrics": bundle["metrics"],
        "weights": bundle["weights"],
        "picks": screen["picks"],
        "audit": rec,
        "audit_file": audit_file,
        "story": "问卷分档 → 与风险平价/波动/仓位规则匹配；拦截时不得假装产品适合。",
    }
    return envelope(data, m.source, m.disclaimer, extra={"implemented": True})


def run_case2(
    source: str = "offline",
    top_n: int = 10,
    cost: float = DEFAULT_COST,
    notional: float = CASE2_NOTIONAL,
    export_fmt: str | None = None,
) -> dict:
    m, screen, cols, rets, opt = _basket(source, None, top_n)
    batch = backtest_all(m.close, cost, data=m)
    rp = opt["methods"]["risk_parity"]
    wp = pd.Series({r["code"]: r["weight"] for r in rp["weights"]})
    wb = pd.Series(
        {r["code"]: r["weight"] for r in opt["methods"]["equal_weight"]["weights"]}
    )
    attr = brinson_fachler(
        _close_df(m, cols), wp, wb, universe=m.universe, names=_name_map(m)
    )
    risk = risk_report(rets, wp, _close_df(m, cols))
    scaled = []
    for s in batch["strategies"]:
        tot = float((s.get("metrics") or {}).get("total_return") or 0.0)
        scaled.append(
            {
                "strategy": s["strategy"],
                "label": s["label"],
                "metrics": s["metrics"],
                "notional_end": notional * (1.0 + tot),
            }
        )
    doc = build_risk_report_doc(
        data_source=m.source,
        disclaimer=m.disclaimer,
        notional=notional,
        picks=screen["picks"],
        method="risk_parity",
        method_label=rp["label"],
        metrics=rp["metrics"],
        weights=rp["weights"],
        var_cvar=risk["var_cvar"],
        stress=risk["stress"],
        attribution=attr,
        batch_strategies=scaled,
    )
    exported = export_report(doc, export_fmt) if export_fmt else None
    data = {
        "story": "小型私募量化研究：批量回测 + Brinson + 标准化风控报告。名义 1 亿元为演示口径，不是已管理实盘。",
        "notional": {
            "amount": notional,
            "label": f"名义本金 {notional:,.0f} 元（演示口径，不是已管理 1 亿实盘）",
        },
        "picks": screen["picks"],
        "batch": batch,
        "scaled": scaled,
        "optimize": {
            "methods": {
                k: {"label": v["label"], "metrics": v["metrics"]}
                for k, v in opt["methods"].items()
            }
        },
        "brinson": attr,
        "risk": risk,
        "report": doc,
        "export": exported,
        "sharpe_rp": opt["sharpe_rp"],
        "sharpe_eq": opt["sharpe_eq"],
    }
    return envelope(data, m.source, m.disclaimer, extra={"implemented": True})


# ---------------------------------------------------------------------------
# LLM 编排函数（非策略用途：报告摘要 / FAQ 辅助 / 配图 / 语音合成）
# SCOPE.md 红线：禁止 LLM 生成交易策略、禁止支付计费、禁止实盘交易。
# 以下函数仅用于：风控报告摘要、项目语音简介、文档配图。
# ---------------------------------------------------------------------------


def run_llm_status() -> dict:
    """返回 LLM 配置状态（不含密钥）。"""
    return {"ok": True, "data": llm_status()}


def generate_report_summary(
    source: str = "offline",
    *,
    provider: str = "stepfun",
) -> dict:
    """调 LLM 生成风控报告摘要（非策略用途）。

    先跑 case1 获取数据，再让 LLM 生成自然语言摘要。
    """
    case1 = run_case1(source)
    data = case1.get("data", {})
    sharpe_rp = data.get("sharpe_rp", 0.0)
    sharpe_eq = data.get("sharpe_eq", 0.0)
    picks = data.get("picks", [])
    risk = data.get("risk", {})
    var = risk.get("var_cvar", {}).get("d1_95", {})
    var95 = var.get("var", 0.0)

    prompt = (
        f"请为以下金融演示项目生成一段简短的风险报告摘要（150字以内）：\n"
        f"- 数据源：离线合成样本（504天/12只）\n"
        f"- 风险平价夏普：{sharpe_rp:.4f}\n"
        f"- 等权夏普：{sharpe_eq:.4f}\n"
        f"- 95% VaR：{var95:.4f}\n"
        f"- 选股数量：{len(picks)}\n"
        f"注意：这是演示系统，非实盘交易。请客观描述，不做收益承诺。"
    )

    system_msg = (
        "You are a financial report assistant. "
        "Generate concise summaries based on provided metrics. "
        "Never make return promises or investment recommendations."
    )

    if provider == "sensenova":
        summary = sensenova_text(prompt, system=system_msg)
    elif provider == "qiji":
        summary = qiji_text(prompt, system=system_msg)
    else:
        summary = step_text(prompt, system=system_msg)

    result = {
        "summary": summary,
        "metrics_used": {
            "sharpe_rp": round(sharpe_rp, 4),
            "sharpe_eq": round(sharpe_eq, 4),
            "var95": round(var95, 4),
            "picks_count": len(picks),
        },
        "provider": provider,
        "scope_note": "LLM 仅用于报告摘要生成，不参与策略生成。",
    }
    return envelope(
        result, case1.get("data_source", "offline"), case1.get("disclaimer", "")
    )


def generate_spoken_intro(
    *,
    text: str = "",
    provider: str = "stepfun",
) -> dict:
    """调 TTS 生成项目语音简介（非策略用途）。

    返回音频 bytes 或降级文本。
    """
    intro_text = text or (
        "AlphaQuant 是基于因子增强与风险平价的智能资产配置演示平台。"
        "核心能力包括十二因子选股、风险平价优化、三种 VaR 风控、"
        "Brinson 归因和投资适当性匹配。当前为离线演示模式，非实盘交易。"
    )

    if provider != "stepfun":
        return {
            "ok": True,
            "data": {
                "text": intro_text,
                "provider": provider,
                "note": "TTS 仅支持阶跃星辰 provider，回退为文本。",
            },
        }

    try:
        audio_bytes = step_voice(intro_text)
        return {
            "ok": True,
            "data": {
                "text": intro_text,
                "audio_size": len(audio_bytes),
                "audio_format": "mp3",
                "provider": "stepfun",
                "scope_note": "TTS 仅用于项目语音简介，不参与策略生成。",
            },
        }
    except Exception as exc:
        return {
            "ok": True,
            "data": {
                "text": intro_text,
                "provider": "stepfun",
                "error": str(exc),
                "note": "TTS 调用失败，回退为文本。",
            },
        }


def generate_doc_illustration(
    *,
    prompt: str = "",
    provider: str = "sensenova_image",
) -> dict:
    """调图像 API 生成文档配图（非策略用途）。

    支持商汤 sensenova_image 和奇绩算力 qiji_image 两个 provider。
    """
    illustration_prompt = (
        prompt or "financial technology dashboard with factor analysis"
    )
    if provider == "qiji_image":
        result = qiji_image(illustration_prompt)
    else:
        result = sensenova_image(illustration_prompt)
    return {
        "ok": True,
        "data": result,
        "provider": provider,
        "scope_note": "图像 API 仅用于文档配图，不参与策略生成。",
    }


def run_llm_vision(
    image_b64: str,
    *,
    prompt: str = "Describe this financial chart.",
) -> dict:
    """调商汤视觉模型描述图表（非策略用途）。

    sensenova-u1.5-lite 是原生理解生成统一模型，支持图像理解。
    """
    description = sensenova_vision(image_b64, prompt=prompt)
    return {
        "ok": True,
        "data": {
            "description": description,
            "scope_note": "视觉 API 仅用于图表描述，不参与策略生成。",
        },
    }
