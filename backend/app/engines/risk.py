"""Historical / Parametric / Monte-Carlo VaR-CVaR and extreme-window stress tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from app.config import RNG_SEED
from app.utils import json_safe


def portfolio_returns(asset_rets: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    if w.sum() <= 0:
        w = pd.Series(1.0 / max(len(asset_rets.columns), 1), index=asset_rets.columns)
    else:
        w = w / w.sum()
    return asset_rets.fillna(0.0).dot(w)


def var_cvar(returns: pd.Series, alpha: float = 0.95) -> dict:
    """Historical simulation VaR / CVaR."""
    r = returns.dropna()
    losses = -r
    if len(losses) < 20:
        return {"alpha": alpha, "var": 0.0, "cvar": 0.0, "n": int(len(losses))}
    var = float(np.quantile(losses, alpha))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if len(tail) else var
    return {"alpha": alpha, "var": var, "cvar": cvar, "n": int(len(losses))}


def var_cvar_parametric(returns: pd.Series, alpha: float = 0.95) -> dict:
    """Parametric (variance-covariance) VaR / CVaR assuming normal distribution.

    VaR_alpha = -mu + z_alpha * sigma
    CVaR_alpha = -mu + phi(z_alpha) / (1-alpha) * sigma
    where z_alpha = norm.ppf(alpha), phi = standard normal PDF.
    """
    r = returns.dropna()
    if len(r) < 20:
        return {"alpha": alpha, "var": 0.0, "cvar": 0.0, "n": int(len(r))}
    mu = float(r.mean())
    sigma = float(r.std(ddof=1))
    if sigma < 1e-12:
        return {"alpha": alpha, "var": 0.0, "cvar": 0.0, "n": int(len(r))}
    z = float(stats.norm.ppf(alpha))
    var = float(-mu + z * sigma)
    pdf_z = float(stats.norm.pdf(z))
    cvar = float(-mu + pdf_z / (1.0 - alpha) * sigma)
    return {"alpha": alpha, "var": var, "cvar": cvar, "n": int(len(r))}


def var_cvar_montecarlo(
    asset_rets: pd.DataFrame,
    weights: pd.Series,
    alpha: float = 0.95,
    n_sims: int = 10000,
) -> dict:
    """Monte Carlo VaR / CVaR via multivariate normal simulation.

    Uses sample mean vector and covariance matrix, generates n_sims scenarios
    via Cholesky decomposition, computes portfolio return for each scenario.
    """
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    if w.sum() <= 0:
        w = pd.Series(1.0 / max(len(asset_rets.columns), 1), index=asset_rets.columns)
    else:
        w = w / w.sum()
    r = asset_rets.fillna(0.0)
    if len(r) < 20:
        return {
            "alpha": alpha,
            "var": 0.0,
            "cvar": 0.0,
            "n": int(len(r)),
            "n_sims": n_sims,
        }
    mu_vec = r.mean().to_numpy()
    cov = r.cov().to_numpy()
    n_assets = len(mu_vec)
    # Ensure positive-definite
    cov = cov + np.eye(n_assets) * 1e-8
    rng = np.random.default_rng(RNG_SEED)
    try:
        L = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        # Fallback: use eigen-decomposition
        vals, vecs = np.linalg.eigh(cov)
        vals = np.clip(vals, 1e-8, None)
        L = vecs @ np.diag(np.sqrt(vals))
    z = rng.standard_normal((n_sims, n_assets))
    sims = mu_vec + z @ L.T
    port_sims = sims @ w.to_numpy()
    losses = -port_sims
    var = float(np.quantile(losses, alpha))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if len(tail) else var
    return {
        "alpha": alpha,
        "var": var,
        "cvar": cvar,
        "n": int(len(r)),
        "n_sims": n_sims,
    }


def _window_loss(nav: pd.Series, window: int) -> dict:
    if len(nav) <= window:
        return {"window": window, "start": None, "end": None, "loss": 0.0}
    roll = nav / nav.shift(window) - 1.0
    idx = roll.idxmin()
    loss = float(roll.min())
    end = idx
    start = nav.index[nav.index.get_loc(end) - window]
    return {
        "window": window,
        "start": str(pd.Timestamp(start).date()),
        "end": str(pd.Timestamp(end).date()),
        "loss": loss,
    }


def stress_tests(
    asset_rets: pd.DataFrame, weights: pd.Series, close: pd.DataFrame
) -> list[dict]:
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    w = w / w.sum() if w.sum() else w
    port = portfolio_returns(asset_rets, w)
    nav = (1.0 + port).cumprod()
    nav = nav / nav.iloc[0]
    items = []
    for win, label in ((5, "最差5日"), (20, "最差20日")):
        row = _window_loss(nav, win)
        row["label"] = label
        row["type"] = "historical_window"
        items.append(row)

    # 均匀冲击
    shock = float((w * -0.10).sum())
    items.append(
        {
            "label": "全市场-10%冲击",
            "type": "scenario",
            "loss": shock,
            "start": None,
            "end": None,
            "window": None,
        }
    )

    # 高波动资产额外冲击：对样本波动最高的 1/3 再打 -15%
    vol = asset_rets.std()
    hi = set(vol.nlargest(max(len(vol) // 3, 1)).index)
    extra = 0.0
    for c, wi in w.items():
        extra += wi * (-0.08 if c not in hi else -0.22)
    items.append(
        {
            "label": "高波动资产加深冲击",
            "type": "scenario",
            "loss": float(extra),
            "start": None,
            "end": None,
            "window": None,
            "high_vol_names": [str(x) for x in hi],
        }
    )
    # 嵌入样本的连续下跌段
    worst = port.rolling(15).sum().idxmin()
    if pd.notna(worst):
        loc = port.index.get_loc(worst)
        start = port.index[max(loc - 14, 0)]
        items.append(
            {
                "label": "样本内连续15日最差累计",
                "type": "historical_window",
                "window": 15,
                "start": str(pd.Timestamp(start).date()),
                "end": str(pd.Timestamp(worst).date()),
                "loss": float(port.loc[start:worst].sum()),
            }
        )
    return items


def risk_report(
    asset_rets: pd.DataFrame, weights: pd.Series, close: pd.DataFrame
) -> dict:
    port = portfolio_returns(asset_rets, weights)
    return json_safe(
        {
            "var_cvar": {
                "d1_95": var_cvar(port, 0.95),
                "d1_99": var_cvar(port, 0.99),
            },
            "methods_comparison": {
                "historical": {
                    "d1_95": var_cvar(port, 0.95),
                    "d1_99": var_cvar(port, 0.99),
                },
                "parametric": {
                    "d1_95": var_cvar_parametric(port, 0.95),
                    "d1_99": var_cvar_parametric(port, 0.99),
                },
                "montecarlo": {
                    "d1_95": var_cvar_montecarlo(asset_rets, weights, 0.95),
                    "d1_99": var_cvar_montecarlo(asset_rets, weights, 0.99),
                },
            },
            "stress": stress_tests(asset_rets, weights, close),
            "note": (
                "VaR/CVaR \u5bf9\u6bd4\u4e09\u79cd\u65b9\u6cd5\uff1a\u5386\u53f2\u6a21\u62df\uff08\u5206\u4f4d\u6570\uff09\u3001\u53c2\u6570\u6cd5\uff08\u65b9\u5dee-\u534f\u65b9\u5dee\u6b63\u6001\u5047\u8bbe\uff09\u3001"
                "\u8499\u7279\u5361\u6d1b\uff08Cholesky \u591a\u5143\u6b63\u6001\u6a21\u62df 10000 \u6b21\uff09\u3002\u5747\u4e3a\u6f14\u793a\u53e3\u5f84\uff0c"
                "\u975e\u76d1\u7ba1\u62a5\u5907\u53e3\u5f84\uff0c\u4ea6\u975e\u5b9e\u65f6\u98ce\u63a7\u3002"
            ),
        }
    )
