"""Equal weight, risk parity, min variance, max Sharpe (SciPy)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.config import TRADING_DAYS
from app.engines.backtest import _metrics, nav_from_weights
from app.utils import json_safe

METHODS = ("equal_weight", "risk_parity", "min_variance", "max_sharpe")

SECTOR_LIMIT = 0.05  # each sector deviation from benchmark <= 5%


def _cov_mu(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    r = returns.dropna(how="all").fillna(0.0)
    cols = [str(c) for c in r.columns]
    mu = r.mean().to_numpy() * TRADING_DAYS
    cov = r.cov().to_numpy() * TRADING_DAYS
    # positive-definite
    cov = cov + np.eye(len(cols)) * 1e-8
    return mu, cov, cols


# ---------------------------------------------------------------------------
# Sector helpers
# ---------------------------------------------------------------------------


def _sector_map(universe: pd.DataFrame, cols: list[str]) -> dict[str, str]:
    """Return {code: sector} for codes in cols."""
    if universe is None or universe.empty:
        return {c: "\u672a\u5206\u7ec4" for c in cols}
    col_map = {str(c).lower(): c for c in universe.columns}
    code_c = col_map.get("code") or list(universe.columns)[0]
    sec_c = col_map.get("sector") or col_map.get("industry")
    out = {}
    for _, row in universe.iterrows():
        code = str(row[code_c])
        if code in cols:
            out[code] = str(row[sec_c]) if sec_c else "\u672a\u5206\u7ec4"
    for c in cols:
        if c not in out:
            out[c] = "\u672a\u5206\u7ec4"
    return out


def _make_upper_con(indices: list[int], bench_sector: float, limit: float):
    """Constraint: bench_sector + limit - sum(w_i) >= 0."""

    def con(w):
        return float(bench_sector + limit - sum(w[i] for i in indices))

    return con


def _make_lower_con(indices: list[int], bench_sector: float, limit: float):
    """Constraint: sum(w_i) - (bench_sector - limit) >= 0."""

    def con(w):
        return float(sum(w[i] for i in indices) - (bench_sector - limit))

    return con


def _sector_exposure_constraints(
    sectors: dict[str, str], cols: list[str], limit: float = SECTOR_LIMIT
) -> list[dict]:
    """Build SLSQP inequality constraints: |w_sector - bench_sector| <= limit."""
    bench_w = 1.0 / len(cols)
    groups: dict[str, list[int]] = {}
    for i, c in enumerate(cols):
        groups.setdefault(sectors.get(c, "\u672a\u5206\u7ec4"), []).append(i)
    cons: list[dict] = []
    for sector, indices in groups.items():
        bench_sector = bench_w * len(indices)
        cons.append(
            {"type": "ineq", "fun": _make_upper_con(indices, bench_sector, limit)}
        )
        cons.append(
            {"type": "ineq", "fun": _make_lower_con(indices, bench_sector, limit)}
        )
    return cons


def _sector_weights(
    sectors: dict[str, str], cols: list[str], weights: np.ndarray
) -> list[dict]:
    """Return per-sector weight summary for reporting."""
    bench_w = 1.0 / len(cols)
    groups: dict[str, list[int]] = {}
    for i, c in enumerate(cols):
        groups.setdefault(sectors.get(c, "\u672a\u5206\u7ec4"), []).append(i)
    rows = []
    for sector, indices in sorted(groups.items()):
        pw = float(sum(weights[i] for i in indices))
        bw = float(bench_w * len(indices))
        rows.append(
            {
                "sector": sector,
                "port_weight": pw,
                "bench_weight": bw,
                "deviation": pw - bw,
                "within_limit": abs(pw - bw) <= SECTOR_LIMIT + 1e-6,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Optimisation methods
# ---------------------------------------------------------------------------


def equal_weight(n: int) -> np.ndarray:
    return np.ones(n) / n


def risk_parity(
    cov: np.ndarray, extra_cons: list[dict] | None = None
) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    w0 = equal_weight(n)

    def obj(w):
        sw = cov @ w
        rc = w * sw
        target = np.sum(rc) / n
        return float(np.sum((rc - target) ** 2))

    cons: list[dict] = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    if extra_cons:
        cons.extend(extra_cons)
    bounds = [(1e-6, 1.0)] * n
    res = minimize(
        obj,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 400, "ftol": 1e-14},
    )
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def min_variance(
    cov: np.ndarray, extra_cons: list[dict] | None = None
) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    w0 = equal_weight(n)

    def obj(w):
        return float(w @ cov @ w)

    cons: list[dict] = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    if extra_cons:
        cons.extend(extra_cons)
    bounds = [(0.0, 1.0)] * n
    res = minimize(
        obj,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 400},
    )
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def max_sharpe(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float = 0.02,
    extra_cons: list[dict] | None = None,
) -> tuple[np.ndarray, bool]:
    n = len(mu)
    w0 = equal_weight(n)

    def obj(w):
        vol = float(np.sqrt(w @ cov @ w))
        if vol < 1e-12:
            return 0.0
        return -float((w @ mu - rf) / vol)

    cons: list[dict] = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    if extra_cons:
        cons.extend(extra_cons)
    bounds = [(0.0, 1.0)] * n
    res = minimize(
        obj,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 400},
    )
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    sw = cov @ weights
    port_var = float(weights @ sw)
    if port_var <= 0:
        return np.full_like(weights, 1.0 / len(weights))
    return weights * sw / port_var


def optimize_basket(
    returns: pd.DataFrame,
    names: dict[str, str] | None = None,
    universe: pd.DataFrame | None = None,
    sector_neutral: bool = False,
) -> dict:
    mu, cov, cols = _cov_mu(returns)
    n = len(cols)

    # Build sector exposure constraints if requested
    extra_cons: list[dict] | None = None
    sector_info: dict | None = None
    if sector_neutral and universe is not None:
        sectors = _sector_map(universe, cols)
        extra_cons = _sector_exposure_constraints(sectors, cols, limit=SECTOR_LIMIT)

    bundles = {}
    w_eq = equal_weight(n)
    w_rp, ok_rp = risk_parity(cov, extra_cons=extra_cons)
    w_mv, ok_mv = min_variance(cov, extra_cons=extra_cons)
    w_ms, ok_ms = max_sharpe(mu, cov, extra_cons=extra_cons)
    table = {
        "equal_weight": (w_eq, True),
        "risk_parity": (w_rp, ok_rp),
        "min_variance": (w_mv, ok_mv),
        "max_sharpe": (w_ms, ok_ms),
    }
    labels = {
        "equal_weight": "\u7b49\u6743",
        "risk_parity": "\u98ce\u9669\u5e73\u4ef7",
        "min_variance": "\u6700\u5c0f\u65b9\u5dee",
        "max_sharpe": "\u6700\u5927\u590f\u666e",
    }
    names = names or {}

    if sector_neutral and universe is not None:
        sectors = _sector_map(universe, cols)

    for method, (w, ok) in table.items():
        wser = pd.Series(w, index=cols)
        nav, pret, trades = nav_from_weights(returns.fillna(0.0), wser)
        rc = risk_contributions(w, cov)
        bundle = {
            "label": labels[method],
            "success": ok,
            "weights": [
                {
                    "code": c,
                    "name": names.get(c, c),
                    "weight": float(wser[c]),
                    "risk_contrib": float(rc[i]),
                }
                for i, c in enumerate(cols)
            ],
            "metrics": _metrics(nav, pret.iloc[1:], trades),
            "nav": [{"date": str(i.date()), "nav": float(v)} for i, v in nav.items()],
        }
        # Attach sector exposure info
        if sector_neutral and universe is not None:
            bundle["sector_exposure"] = _sector_weights(sectors, cols, w)
        bundles[method] = bundle

    rp_s = bundles["risk_parity"]["metrics"]["sharpe"]
    eq_s = bundles["equal_weight"]["metrics"]["sharpe"]

    result = {
        "methods": bundles,
        "sharpe_rp": rp_s,
        "sharpe_eq": eq_s,
        "sharpe_rp_better": bool(rp_s > eq_s),
        "sector_neutral": sector_neutral,
        "note": "\u6743\u91cd\u57fa\u4e8e\u6837\u672c\u534f\u65b9\u5dee/\u5747\u503c\u7684\u5386\u53f2\u6a21\u62df\uff0cSciPy SLSQP\uff1b\u975e\u672a\u6765\u6536\u76ca\u4fdd\u8bc1\u3002",
    }
    if sector_neutral:
        result["sector_note"] = (
            f"\u884c\u4e1a\u4e2d\u6027\u7ea6\u675f\uff1a\u6bcf\u4e2a\u884c\u4e1a\u6743\u91cd\u504f\u79bb\u7b49\u6743\u57fa\u51c6\u4e0d\u8d85\u8fc7 \u00b1{SECTOR_LIMIT:.0%}\u3002"
        )
    return json_safe(result)
