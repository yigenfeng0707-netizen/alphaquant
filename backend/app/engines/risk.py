"""Historical VaR / CVaR and extreme-window stress tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils import json_safe


def portfolio_returns(asset_rets: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    if w.sum() <= 0:
        w = pd.Series(1.0 / max(len(asset_rets.columns), 1), index=asset_rets.columns)
    else:
        w = w / w.sum()
    return asset_rets.fillna(0.0).dot(w)


def var_cvar(returns: pd.Series, alpha: float = 0.95) -> dict:
    r = returns.dropna()
    losses = -r
    if len(losses) < 20:
        return {"alpha": alpha, "var": 0.0, "cvar": 0.0, "n": int(len(losses))}
    var = float(np.quantile(losses, alpha))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if len(tail) else var
    return {"alpha": alpha, "var": var, "cvar": cvar, "n": int(len(losses))}


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


def stress_tests(asset_rets: pd.DataFrame, weights: pd.Series, close: pd.DataFrame) -> list[dict]:
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
    items.append({"label": "全市场-10%冲击", "type": "scenario", "loss": shock, "start": None, "end": None, "window": None})

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


def risk_report(asset_rets: pd.DataFrame, weights: pd.Series, close: pd.DataFrame) -> dict:
    port = portfolio_returns(asset_rets, weights)
    return json_safe(
        {
            "var_cvar": {
                "d1_95": var_cvar(port, 0.95),
                "d1_99": var_cvar(port, 0.99),
            },
            "stress": stress_tests(asset_rets, weights, close),
            "note": "历史模拟 VaR/CVaR 与情景冲击，不是监管报备口径，亦非实时风控。",
        }
    )
