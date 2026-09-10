"""Single-period Brinson-Fachler attribution vs equal-weight benchmark."""
from __future__ import annotations

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

    sectors = _sector_map(universe) if universe is not None else {c: "未分组" for c in cols}
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
