"""Equal weight, risk parity, min variance, max Sharpe (SciPy)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.config import TRADING_DAYS
from app.engines.backtest import _metrics, nav_from_weights
from app.utils import json_safe

METHODS = ("equal_weight", "risk_parity", "min_variance", "max_sharpe")


def _cov_mu(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    r = returns.dropna(how="all").fillna(0.0)
    cols = [str(c) for c in r.columns]
    mu = r.mean().to_numpy() * TRADING_DAYS
    cov = r.cov().to_numpy() * TRADING_DAYS
    # 保证正定
    cov = cov + np.eye(len(cols)) * 1e-8
    return mu, cov, cols


def equal_weight(n: int) -> np.ndarray:
    return np.ones(n) / n


def risk_parity(cov: np.ndarray) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    w0 = equal_weight(n)

    def obj(w):
        sw = cov @ w
        rc = w * sw
        target = np.sum(rc) / n
        return float(np.sum((rc - target) ** 2))

    cons = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}
    bounds = [(1e-6, 1.0)] * n
    res = minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 400, "ftol": 1e-14})
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def min_variance(cov: np.ndarray) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    w0 = equal_weight(n)

    def obj(w):
        return float(w @ cov @ w)

    cons = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}
    bounds = [(0.0, 1.0)] * n
    res = minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 400})
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def max_sharpe(mu: np.ndarray, cov: np.ndarray, rf: float = 0.02) -> tuple[np.ndarray, bool]:
    n = len(mu)
    w0 = equal_weight(n)

    def obj(w):
        vol = float(np.sqrt(w @ cov @ w))
        if vol < 1e-12:
            return 0.0
        return -float((w @ mu - rf) / vol)

    cons = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}
    bounds = [(0.0, 1.0)] * n
    res = minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 400})
    w = np.clip(res.x, 0.0, 1.0)
    w = w / w.sum()
    return w, bool(res.success)


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    sw = cov @ weights
    port_var = float(weights @ sw)
    if port_var <= 0:
        return np.full_like(weights, 1.0 / len(weights))
    return weights * sw / port_var


def optimize_basket(returns: pd.DataFrame, names: dict[str, str] | None = None) -> dict:
    mu, cov, cols = _cov_mu(returns)
    n = len(cols)
    bundles = {}
    w_eq = equal_weight(n)
    w_rp, ok_rp = risk_parity(cov)
    w_mv, ok_mv = min_variance(cov)
    w_ms, ok_ms = max_sharpe(mu, cov)
    table = {
        "equal_weight": (w_eq, True),
        "risk_parity": (w_rp, ok_rp),
        "min_variance": (w_mv, ok_mv),
        "max_sharpe": (w_ms, ok_ms),
    }
    labels = {
        "equal_weight": "等权",
        "risk_parity": "风险平价",
        "min_variance": "最小方差",
        "max_sharpe": "最大夏普",
    }
    names = names or {}
    for method, (w, ok) in table.items():
        wser = pd.Series(w, index=cols)
        nav, pret, trades = nav_from_weights(returns.fillna(0.0), wser)
        rc = risk_contributions(w, cov)
        bundles[method] = {
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
    rp_s = bundles["risk_parity"]["metrics"]["sharpe"]
    eq_s = bundles["equal_weight"]["metrics"]["sharpe"]
    return json_safe(
        {
            "methods": bundles,
            "sharpe_rp": rp_s,
            "sharpe_eq": eq_s,
            "sharpe_rp_better": bool(rp_s > eq_s),
            "note": "权重基于样本协方差/均值的历史模拟，SciPy SLSQP；非未来收益保证。",
        }
    )
