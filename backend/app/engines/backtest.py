"""Four strategies, six metrics, transaction cost NAV backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import DEFAULT_COST, TRADING_DAYS
from app.utils import json_safe

STRATEGIES = [
    ("ma_cross", "双均线"),
    ("mean_reversion", "均值回归"),
    ("momentum", "动量"),
    ("multi_factor", "多因子合成"),
]


def _metrics(nav: pd.Series, rets: pd.Series, n_trades: int) -> dict:
    if len(nav) < 5:
        return {
            "annual_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "win_rate": 0.0,
            "calmar": 0.0,
            "total_return": 0.0,
            "trades": n_trades,
        }
    years = max(len(nav) / TRADING_DAYS, 1e-9)
    total = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    annual = float((nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0)
    vol = float(rets.std(ddof=0) * np.sqrt(TRADING_DAYS)) if len(rets) else 0.0
    sharpe = float(rets.mean() / rets.std(ddof=0) * np.sqrt(TRADING_DAYS)) if rets.std(ddof=0) > 1e-12 else 0.0
    peak = nav.cummax()
    dd = float((nav / peak - 1.0).min())
    calmar = float(annual / abs(dd)) if dd < 0 else 0.0
    win = float((rets > 0).mean()) if len(rets) else 0.0
    return {
        "annual_return": annual,
        "sharpe": sharpe,
        "max_drawdown": dd,
        "volatility": vol,
        "win_rate": win,
        "calmar": calmar,
        "total_return": total,
        "trades": int(n_trades),
    }


def nav_from_weights(asset_rets: pd.DataFrame, weights: pd.Series, cost: float = DEFAULT_COST) -> tuple[pd.Series, pd.Series, int]:
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    if w.sum() <= 0:
        w = pd.Series(1.0 / len(asset_rets.columns), index=asset_rets.columns)
    else:
        w = w / w.sum()
    port = asset_rets.fillna(0.0).dot(w)
    # 期初建仓一次成本
    nav = (1.0 + port).cumprod()
    nav.iloc[0] = nav.iloc[0] * (1.0 - cost)
    nav = nav / nav.iloc[0]
    return nav, port, 1


def _signal_nav(close: pd.Series, signal: pd.Series, cost: float) -> tuple[pd.Series, pd.Series, int]:
    pos = signal.shift(1).fillna(0.0).clip(0.0, 1.0)
    r = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    net = pos * r - turnover * cost
    nav = (1.0 + net).cumprod()
    nav = nav / nav.iloc[0]
    trades = int((turnover > 1e-9).sum())
    return nav, net, trades


def _ma_cross(close: pd.Series) -> pd.Series:
    ma_s = close.rolling(20).mean()
    ma_l = close.rolling(60).mean()
    return (ma_s > ma_l).astype(float)


def _mean_reversion(close: pd.Series) -> pd.Series:
    z = (close - close.rolling(20).mean()) / close.rolling(20).std(ddof=0).replace(0, np.nan)
    sig = pd.Series(0.0, index=close.index)
    sig[z < -1.2] = 1.0
    sig[z > 1.2] = 0.0
    return sig.replace(0.0, np.nan).ffill().fillna(0.0)


def _momentum(close: pd.Series) -> pd.Series:
    mom = close.pct_change(60)
    return (mom > 0).astype(float)


def _multi_factor(close: pd.Series) -> pd.Series:
    mom = close.pct_change(60)
    ma = close.rolling(20).mean()
    vol = close.pct_change().rolling(20).std()
    score = 0.45 * (mom > 0).astype(float) + 0.35 * (close > ma).astype(float) + 0.20 * (vol < vol.median()).astype(float)
    return (score >= 0.5).astype(float)


def run_strategy(close: pd.Series, strategy: str, cost: float = DEFAULT_COST) -> dict:
    px = close.dropna()
    if strategy == "ma_cross":
        sig = _ma_cross(px)
        label = "双均线"
    elif strategy == "mean_reversion":
        sig = _mean_reversion(px)
        label = "均值回归"
    elif strategy == "momentum":
        sig = _momentum(px)
        label = "动量"
    else:
        sig = _multi_factor(px)
        label = "多因子合成"
        strategy = "multi_factor"
    nav, rets, trades = _signal_nav(px, sig, cost)
    metrics = _metrics(nav, rets.iloc[1:], trades)
    return json_safe(
        {
            "strategy": strategy,
            "label": label,
            "cost": cost,
            "metrics": metrics,
            "nav": [{"date": str(i.date()), "nav": float(v)} for i, v in nav.items()],
        }
    )


def equal_weight_index(close: pd.DataFrame) -> pd.Series:
    r = close.pct_change().fillna(0.0)
    nav = (1.0 + r.mean(axis=1)).cumprod()
    return nav / nav.iloc[0]


def backtest_all(close: pd.DataFrame, cost: float = DEFAULT_COST) -> dict:
    idx = equal_weight_index(close)
    results = []
    for sid, label in STRATEGIES:
        results.append(run_strategy(idx, sid, cost))
        results[-1]["label"] = label
        results[-1]["benchmark"] = "universe_equal_weight_index"
    bh_rets = idx.pct_change().dropna()
    bh = {
        "strategy": "buy_hold_index",
        "label": "等权指数持有（对照）",
        "metrics": _metrics(idx, bh_rets, 1),
    }
    return json_safe(
        {
            "period": {"start": str(close.index[0].date()), "end": str(close.index[-1].date())},
            "cost": cost,
            "note": "策略作用在股票池等权指数上，样本内模拟，含双边成本近似。",
            "strategies": results,
            "benchmark": bh,
        }
    )
