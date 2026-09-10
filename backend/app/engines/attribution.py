"""Single-period and multi-period Brinson-Fachler attribution vs equal-weight benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils import json_safe


def _sector_map(universe: pd.DataFrame) -> dict[str, str]:
    if universe is None or universe.empty:
        return {}
    cols = {str(c).lower(): c for c in universe.columns}
    code_c = cols.get("code") or list(universe.columns)[0]
    sec_c = cols.get("sector") or cols.get("industry")
    out = {}
    for _, row in universe.iterrows():
        code = str(row[code_c])
        sector = str(row[sec_c]) if sec_c else "未分组"
        out[code] = sector
    return out


def _period_returns(close: pd.DataFrame) -> pd.Series:
    px = close.dropna(how="all")
    if len(px) < 2:
        return pd.Series(0.0, index=px.columns)
    first = px.iloc[0].replace(0, pd.NA)
    last = px.iloc[-1]
    r = (last / first) - 1.0
    return r.fillna(0.0)


def brinson_fachler(
    close: pd.DataFrame,
    port_weights: pd.Series,
    bench_weights: pd.Series | None = None,
    universe: pd.DataFrame | None = None,
    names: dict[str, str] | None = None,
) -> dict:
    """Arithmetic one-period Brinson: allocation + selection + interaction."""
    cols = [str(c) for c in close.columns]
    r = _period_returns(close).reindex(cols).fillna(0.0)
    wp = port_weights.reindex(cols).fillna(0.0).astype(float)
    if wp.sum() <= 0:
        wp = pd.Series(1.0 / max(len(cols), 1), index=cols)
    else:
        wp = wp / wp.sum()
    if bench_weights is None:
        wb = pd.Series(1.0 / len(cols), index=cols)
    else:
        wb = bench_weights.reindex(cols).fillna(0.0).astype(float)
        wb = wb / wb.sum() if wb.sum() > 0 else pd.Series(1.0 / len(cols), index=cols)

    sectors = (
        _sector_map(universe) if universe is not None else {c: "未分组" for c in cols}
    )
    names = names or {}
    groups: dict[str, list[str]] = {}
    for c in cols:
        groups.setdefault(sectors.get(c, "未分组"), []).append(c)

    rows = []
    alloc = sel = inter = 0.0
    for sector, members in sorted(groups.items()):
        w_p_s = float(wp[members].sum())
        w_b_s = float(wb[members].sum())
        if w_b_s > 1e-12:
            r_b_s = float((wb[members] * r[members]).sum() / w_b_s)
        else:
            r_b_s = float(r[members].mean()) if members else 0.0
        if w_p_s > 1e-12:
            r_p_s = float((wp[members] * r[members]).sum() / w_p_s)
        else:
            r_p_s = 0.0
        a = (w_p_s - w_b_s) * r_b_s
        s = w_b_s * (r_p_s - r_b_s)
        i = (w_p_s - w_b_s) * (r_p_s - r_b_s)
        alloc += a
        sel += s
        inter += i
        rows.append(
            {
                "sector": sector,
                "weight_port": w_p_s,
                "weight_bench": w_b_s,
                "return_port": r_p_s,
                "return_bench": r_b_s,
                "allocation": a,
                "selection": s,
                "interaction": i,
                "names": [names.get(c, c) for c in members],
                "codes": members,
            }
        )

    r_p = float((wp * r).sum())
    r_b = float((wb * r).sum())
    total_effects = alloc + sel + inter
    recon_error = r_p - r_b - total_effects

    stock_rows = []
    for c in cols:
        stock_rows.append(
            {
                "code": c,
                "name": names.get(c, c),
                "sector": sectors.get(c, "未分组"),
                "weight_port": float(wp[c]),
                "weight_bench": float(wb[c]),
                "period_return": float(r[c]),
                "contrib_port": float(wp[c] * r[c]),
                "contrib_bench": float(wb[c] * r[c]),
            }
        )

    start = str(pd.Timestamp(close.index[0]).date()) if len(close) else None
    end = str(pd.Timestamp(close.index[-1]).date()) if len(close) else None
    return json_safe(
        {
            "model": "Brinson-Fachler",
            "period": {"start": start, "end": end, "kind": "single_period_arithmetic"},
            "portfolio_return": r_p,
            "benchmark_return": r_b,
            "excess_return": r_p - r_b,
            "allocation": alloc,
            "selection": sel,
            "interaction": inter,
            "recon_error": recon_error,
            "explain": (
                f"超额 {r_p - r_b:.2%} ≈ 配置 {alloc:.2%} + 选择 {sel:.2%} + 交互 {inter:.2%} "
                f"（复核对账误差 {recon_error:.2e}）。配置=超配/低配行业相对基准行业收益；"
                "选择=行业内选股相对该行业基准；交互=配置差×选择差。样本期算术归因，不是 GIPS 官方报告。"
            ),
            "sectors": rows,
            "stocks": stock_rows,
            "benchmark": "equal_weight_same_basket",
            "note": "组合相对等权篮子的单期归因；用于解释超额来源，不是收益承诺。",
        }
    )


def _single_period_effects(
    close_sub: pd.DataFrame,
    wp: pd.Series,
    wb: pd.Series,
    sectors: dict[str, str],
) -> dict:
    """Compute single-period Brinson-Fachler effects for a sub-period."""
    cols = [str(c) for c in close_sub.columns]
    r = _period_returns(close_sub).reindex(cols).fillna(0.0)

    alloc = sel = inter = 0.0
    sector_rows = []
    groups: dict[str, list[str]] = {}
    for c in cols:
        groups.setdefault(sectors.get(c, "\u672a\u5206\u7ec4"), []).append(c)
    for sector, members in sorted(groups.items()):
        w_p_s = float(wp[members].sum())
        w_b_s = float(wb[members].sum())
        if w_b_s > 1e-12:
            r_b_s = float((wb[members] * r[members]).sum() / w_b_s)
        else:
            r_b_s = float(r[members].mean()) if members else 0.0
        if w_p_s > 1e-12:
            r_p_s = float((wp[members] * r[members]).sum() / w_p_s)
        else:
            r_p_s = 0.0
        a = (w_p_s - w_b_s) * r_b_s
        s = w_b_s * (r_p_s - r_b_s)
        i = (w_p_s - w_b_s) * (r_p_s - r_b_s)
        alloc += a
        sel += s
        inter += i
        sector_rows.append(
            {
                "sector": sector,
                "allocation": a,
                "selection": s,
                "interaction": i,
            }
        )
    r_p = float((wp * r).sum())
    r_b = float((wb * r).sum())
    return {
        "r_p": r_p,
        "r_b": r_b,
        "allocation": alloc,
        "selection": sel,
        "interaction": inter,
        "excess": r_p - r_b,
        "sectors": sector_rows,
    }


def multi_period_brinson(
    close: pd.DataFrame,
    port_weights: pd.Series,
    bench_weights: pd.Series | None = None,
    universe: pd.DataFrame | None = None,
    names: dict[str, str] | None = None,
    n_periods: int = 4,
) -> dict:
    """Multi-period Brinson-Fachler with Frongello linking.

    Splits the sample into n_periods sub-periods, computes single-period
    effects for each, then links them using the Frongello (1995) method:
      linked_effect = sum_t [ w_t * effect_t ]
    where w_t = (1 + cum_R_p_through_t) / (1 + total_R_p).
    The linking residual captures the geometric vs arithmetic difference.
    """
    px = close.dropna(how="all")
    T = len(px)
    if T < 10 or len(px.columns) < 2:
        return brinson_fachler(close, port_weights, bench_weights, universe, names)

    cols = [str(c) for c in px.columns]
    wp = port_weights.reindex(cols).fillna(0.0).astype(float)
    if wp.sum() <= 0:
        wp = pd.Series(1.0 / max(len(cols), 1), index=cols)
    else:
        wp = wp / wp.sum()
    if bench_weights is None:
        wb = pd.Series(1.0 / len(cols), index=cols)
    else:
        wb = bench_weights.reindex(cols).fillna(0.0).astype(float)
        wb = wb / wb.sum() if wb.sum() > 0 else pd.Series(1.0 / len(cols), index=cols)

    sectors = (
        _sector_map(universe)
        if universe is not None
        else {c: "\u672a\u5206\u7ec4" for c in cols}
    )

    # Split into roughly equal sub-periods
    boundaries = np.array_split(np.arange(T), n_periods)

    period_results = []
    cum_rp = 1.0  # cumulative portfolio return product
    cum_rb = 1.0
    for idx_arr in boundaries:
        if len(idx_arr) < 3:
            continue
        sub = px.iloc[idx_arr]
        eff = _single_period_effects(sub, wp, wb, sectors)
        eff["start"] = str(pd.Timestamp(sub.index[0]).date())
        eff["end"] = str(pd.Timestamp(sub.index[-1]).date())
        eff["cum_rp"] = cum_rp
        period_results.append(eff)
        cum_rp *= 1.0 + eff["r_p"]
        cum_rb *= 1.0 + eff["r_b"]

    total_rp = cum_rp - 1.0
    total_rb = cum_rb - 1.0
    total_excess = total_rp - total_rb

    # Frongello linking: w_t = (1 + cum_R_p_through_t) / (1 + total_R_p)
    # But we need to use the portfolio return *before* period t
    linked_alloc = 0.0
    linked_sel = 0.0
    linked_inter = 0.0
    prev_cum_rp = 1.0
    for eff in period_results:
        if abs(1.0 + total_rp) < 1e-12:
            w = 0.0
        else:
            w = prev_cum_rp / (1.0 + total_rp)
        linked_alloc += w * eff["allocation"]
        linked_sel += w * eff["selection"]
        linked_inter += w * eff["interaction"]
        prev_cum_rp *= 1.0 + eff["r_p"]

    linked_total = linked_alloc + linked_sel + linked_inter
    linking_residual = total_excess - linked_total

    # Aggregate sector-level effects across periods (simple sum)
    sector_agg: dict[str, dict] = {}
    for eff in period_results:
        for sr in eff["sectors"]:
            s = sr["sector"]
            if s not in sector_agg:
                sector_agg[s] = {
                    "allocation": 0.0,
                    "selection": 0.0,
                    "interaction": 0.0,
                }
            sector_agg[s]["allocation"] += sr["allocation"]
            sector_agg[s]["selection"] += sr["selection"]
            sector_agg[s]["interaction"] += sr["interaction"]

    sector_summary = [
        {
            "sector": s,
            "allocation": v["allocation"],
            "selection": v["selection"],
            "interaction": v["interaction"],
            "total": v["allocation"] + v["selection"] + v["interaction"],
        }
        for s, v in sorted(sector_agg.items())
    ]

    start = str(pd.Timestamp(px.index[0]).date())
    end = str(pd.Timestamp(px.index[-1]).date())

    return json_safe(
        {
            "model": "Brinson-Fachler (multi-period, Frongello linked)",
            "period": {
                "start": start,
                "end": end,
                "kind": "multi_period_linked",
                "n_sub_periods": len(period_results),
            },
            "portfolio_return": total_rp,
            "benchmark_return": total_rb,
            "excess_return": total_excess,
            "allocation": linked_alloc,
            "selection": linked_sel,
            "interaction": linked_inter,
            "linking_residual": linking_residual,
            "recon_error": abs(linking_residual),
            "sub_periods": [
                {
                    "start": p["start"],
                    "end": p["end"],
                    "portfolio_return": p["r_p"],
                    "benchmark_return": p["r_b"],
                    "excess": p["excess"],
                    "allocation": p["allocation"],
                    "selection": p["selection"],
                    "interaction": p["interaction"],
                }
                for p in period_results
            ],
            "sectors": sector_summary,
            "explain": (
                f"\u6837\u672c\u533a\u95f4 {start} \u2013 {end} \u62c6\u5206 {len(period_results)} \u4e2a\u5b50\u671f\u95f4\uff0c"
                f"\u51e0\u4f55\u94fe\u63a5\u8d85\u989d {total_excess:.2%} \u2248 "
                f"\u914d\u7f6e {linked_alloc:.2%} + \u9009\u62e9 {linked_sel:.2%} + "
                f"\u4ea4\u4e92 {linked_inter:.2%}\uff08\u94fe\u63a5\u6b8b\u5dee {linking_residual:.2e}\uff09\u3002"
                "\u914d\u7f6e=\u8d85\u914d/\u4f4e\u914d\u884c\u4e1a\u76f8\u5bf9\u57fa\u51c6\u6536\u76ca\uff1b"
                "\u9009\u62e9=\u884c\u4e1a\u5185\u9009\u80a1\u76f8\u5bf9\u884c\u4e1a\u57fa\u51c6\uff1b"
                "\u4ea4\u4e92=\u914d\u7f6e\u5dee\u00d7\u9009\u62e9\u5dee\u3002"
                "\u591a\u671f\u94fe\u63a5\u91c7\u7528 Frongello \u65b9\u6cd5\uff0c\u975e GIPS \u5b98\u65b9\u62a5\u544a\u3002"
            ),
            "benchmark": "equal_weight_same_basket",
            "note": "\u591a\u671f Brinson-Fachler \u94fe\u63a5\u5f52\u56e0\uff1b\u7528\u4e8e\u89c2\u5bdf\u65f6\u95f4\u5e8f\u5217\u4e0a\u7684\u6548\u5e94\u53d8\u5316\uff0c\u4e0d\u662f GIPS \u6210\u7ee9\u62a5\u544a\u3002",
        }
    )
