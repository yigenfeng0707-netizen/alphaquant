"""Four strategies, six metrics, transaction cost NAV backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import DEFAULT_COST, SLIPPAGE_COEF, TRADING_DAYS
from app.data.provider import MarketData, daily_returns
from app.engines.factors import screen_stocks
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
    sharpe = (
        float(rets.mean() / rets.std(ddof=0) * np.sqrt(TRADING_DAYS))
        if rets.std(ddof=0) > 1e-12
        else 0.0
    )
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


def nav_from_weights(
    asset_rets: pd.DataFrame, weights: pd.Series, cost: float = DEFAULT_COST
) -> tuple[pd.Series, pd.Series, int]:
    w = weights.reindex(asset_rets.columns).fillna(0.0)
    if w.sum() <= 0:
        w = pd.Series(1.0 / len(asset_rets.columns), index=asset_rets.columns)
    else:
        w = w / w.sum()
    port = asset_rets.fillna(0.0).dot(w)
    # static weights -> only initial position change; sqrt-impact slippage on entry
    entry_turnover = float(w.abs().sum())
    slippage = SLIPPAGE_COEF * np.sqrt(entry_turnover)
    nav = (1.0 + port).cumprod()
    nav.iloc[0] = nav.iloc[0] * (1.0 - cost - slippage)
    nav = nav / nav.iloc[0]
    return nav, port, 1


def _signal_nav(
    close: pd.Series, signal: pd.Series, cost: float
) -> tuple[pd.Series, pd.Series, int]:
    pos = signal.shift(1).fillna(0.0).clip(0.0, 1.0)
    r = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.iloc[0])
    # sqrt-impact slippage: market impact proportional to sqrt(turnover)
    slippage = SLIPPAGE_COEF * np.sqrt(turnover.clip(lower=0.0))
    net = pos * r - turnover * cost - slippage
    nav = (1.0 + net).cumprod()
    nav = nav / nav.iloc[0]
    trades = int((turnover > 1e-9).sum())
    return nav, net, trades


def _ma_cross(close: pd.Series) -> pd.Series:
    ma_s = close.rolling(20).mean()
    ma_l = close.rolling(60).mean()
    return (ma_s > ma_l).astype(float)


def _mean_reversion(close: pd.Series) -> pd.Series:
    z = (close - close.rolling(20).mean()) / close.rolling(20).std(ddof=0).replace(
        0, np.nan
    )
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
    score = (
        0.45 * (mom > 0).astype(float)
        + 0.35 * (close > ma).astype(float)
        + 0.20 * (vol < vol.median()).astype(float)
    )
    return (score >= 0.5).astype(float)


def _multi_factor_from_engine(
    data: MarketData, cost: float = DEFAULT_COST
) -> tuple[pd.Series, pd.Series, int]:
    result = screen_stocks(data, top_n=len(data.close.columns))
    picks = result.get("picks") or []
    if not picks:
        cols = list(data.close.columns)
        w = pd.Series(1.0 / len(cols), index=cols)
    else:
        codes = [str(p["code"]) for p in picks]
        scores = np.array(
            [max(float(p.get("composite", 0.0)), 0.0) for p in picks], dtype=float
        )
        if scores.sum() > 1e-12:
            w = pd.Series(scores / scores.sum(), index=codes)
        else:
            w = pd.Series(1.0 / len(codes), index=codes)
    available = [c for c in w.index if c in data.close.columns]
    if len(available) < len(w):
        w = w[available]
        w = (
            w / w.sum()
            if w.sum() > 0
            else pd.Series(1.0 / max(len(available), 1), index=available)
        )
    asset_rets = daily_returns(data.close[list(w.index)])
    return nav_from_weights(asset_rets, w, cost)


def run_strategy(
    close: pd.Series,
    strategy: str,
    cost: float = DEFAULT_COST,
    data: MarketData | None = None,
) -> dict:
    px = close.dropna()
    if strategy == "ma_cross":
        sig = _ma_cross(px)
        label = "\u53cc\u5747\u7ebf"
        nav, rets, trades = _signal_nav(px, sig, cost)
    elif strategy == "mean_reversion":
        sig = _mean_reversion(px)
        label = "\u5747\u503c\u56de\u5f52"
        nav, rets, trades = _signal_nav(px, sig, cost)
    elif strategy == "momentum":
        sig = _momentum(px)
        label = "\u52a8\u91cf"
        nav, rets, trades = _signal_nav(px, sig, cost)
    else:
        label = "\u591a\u56e0\u5b50\u5408\u6210"
        strategy = "multi_factor"
        if data is not None:
            nav, rets, trades = _multi_factor_from_engine(data, cost)
        else:
            sig = _multi_factor(px)
            nav, rets, trades = _signal_nav(px, sig, cost)
    metrics = _metrics(nav, rets.iloc[1:] if len(rets) > 1 else rets, trades)
    return json_safe(
        {
            "strategy": strategy,
            "label": label,
            "cost": cost,
            "engine": "factor_engine"
            if strategy == "multi_factor" and data is not None
            else "signal",
            "metrics": metrics,
            "nav": [{"date": str(i.date()), "nav": float(v)} for i, v in nav.items()],
        }
    )


def equal_weight_index(close: pd.DataFrame) -> pd.Series:
    r = close.pct_change().fillna(0.0)
    nav = (1.0 + r.mean(axis=1)).cumprod()
    return nav / nav.iloc[0]


def backtest_all(
    close: pd.DataFrame, cost: float = DEFAULT_COST, data: MarketData | None = None
) -> dict:
    idx = equal_weight_index(close)
    results = []
    for sid, label in STRATEGIES:
        results.append(run_strategy(idx, sid, cost, data=data))
        results[-1]["label"] = label
        results[-1]["benchmark"] = "universe_equal_weight_index"
    bh_rets = idx.pct_change().dropna()
    bh = {
        "strategy": "buy_hold_index",
        "label": "\u7b49\u6743\u6307\u6570\u6301\u6709\uff08\u5bf9\u7167\uff09",
        "metrics": _metrics(idx, bh_rets, 1),
    }
    return json_safe(
        {
            "period": {
                "start": str(close.index[0].date()),
                "end": str(close.index[-1].date()),
            },
            "cost": cost,
            "note": "\u7b56\u7565\u4f5c\u7528\u5728\u80a1\u7968\u6c60\u7b49\u6743\u6307\u6570\u4e0a\uff0c\u6837\u672c\u5185\u6a21\u62df\uff0c\u542b\u53cc\u8fb9\u6210\u672c\u8fd1\u4f3c\u3002",
            "strategies": results,
            "benchmark": bh,
        }
    )


def walk_forward_backtest(
    data: MarketData,
    train_ratio: float = 0.714,
    cost: float = DEFAULT_COST,
) -> dict:
    """Walk-forward: train on first portion, test OOS on remainder.

    Splits the data into in-sample (train) and out-of-sample (test) windows.
    On train: factor screening + IC/IR weighting -> composite scores -> weights.
    On test: apply those weights to OOS returns, compute metrics.
    Also runs an equal-weight benchmark on both windows for comparison.
    """
    from app.engines.factors import screen_stocks
    from app.engines.optimizer import optimize_basket

    close = data.close
    n = len(close)
    split = int(n * train_ratio)
    if split < 60 or (n - split) < 20:
        return json_safe(
            {
                "error": "Insufficient data for walk-forward split",
                "n_total": n,
                "n_train": split,
                "n_test": n - split,
            }
        )

    train_close = close.iloc[:split]
    test_close = close.iloc[split:]
    train_vol = data.volume.iloc[:split] if data.volume is not None else None
    test_vol = data.volume.iloc[split:] if data.volume is not None else None

    from dataclasses import replace

    train_data = replace(
        data,
        close=train_close,
        volume=train_vol if train_vol is not None else data.volume,
    )
    test_data = replace(
        data, close=test_close, volume=test_vol if test_vol is not None else data.volume
    )

    # In-sample: factor screening on train window
    screen_train = screen_stocks(train_data, top_n=len(train_close.columns))
    picks = screen_train.get("picks") or []
    codes = [str(p["code"]) for p in picks] if picks else list(train_close.columns)

    # In-sample: optimize weights on train returns
    train_rets = daily_returns(train_close[codes])
    opt_train = optimize_basket(train_rets, names={})
    rp_weights_tab = opt_train["methods"]["risk_parity"]["weights"]
    rp_w = pd.Series({r["code"]: r["weight"] for r in rp_weights_tab})
    eq_w = pd.Series(1.0 / len(codes), index=codes)

    # In-sample NAV (risk parity)
    is_nav, is_rets, is_trades = nav_from_weights(train_rets, rp_w, cost)
    is_eq_nav, is_eq_rets, is_eq_trades = nav_from_weights(train_rets, eq_w, cost)
    is_metrics = _metrics(
        is_nav, is_rets.iloc[1:] if len(is_rets) > 1 else is_rets, is_trades
    )
    is_eq_metrics = _metrics(
        is_eq_nav,
        is_eq_rets.iloc[1:] if len(is_eq_rets) > 1 else is_eq_rets,
        is_eq_trades,
    )

    # Out-of-sample: apply train-derived weights to test returns
    test_codes = [c for c in rp_w.index if c in test_close.columns]
    if len(test_codes) < 3:
        test_codes = list(test_close.columns)[: max(len(test_codes), 3)]
        rp_w = pd.Series(1.0 / len(test_codes), index=test_codes)
    test_rets = daily_returns(test_close[test_codes])
    oos_nav, oos_rets, oos_trades = nav_from_weights(test_rets, rp_w[test_codes], cost)
    oos_eq_nav, oos_eq_rets, oos_eq_trades = nav_from_weights(
        test_rets, eq_w[test_codes], cost
    )
    oos_metrics = _metrics(
        oos_nav, oos_rets.iloc[1:] if len(oos_rets) > 1 else oos_rets, oos_trades
    )
    oos_eq_metrics = _metrics(
        oos_eq_nav,
        oos_eq_rets.iloc[1:] if len(oos_eq_rets) > 1 else oos_eq_rets,
        oos_eq_trades,
    )

    # Equal-weight index benchmark on both windows
    is_idx = equal_weight_index(train_close)
    oos_idx = equal_weight_index(test_close)
    is_idx_metrics = _metrics(is_idx, is_idx.pct_change().dropna(), 1)
    oos_idx_metrics = _metrics(oos_idx, oos_idx.pct_change().dropna(), 1)

    return json_safe(
        {
            "method": "walk_forward_70_30",
            "train_ratio": train_ratio,
            "period": {
                "in_sample": {
                    "start": str(train_close.index[0].date()),
                    "end": str(train_close.index[-1].date()),
                    "n_days": len(train_close),
                },
                "out_of_sample": {
                    "start": str(test_close.index[0].date()),
                    "end": str(test_close.index[-1].date()),
                    "n_days": len(test_close),
                },
            },
            "in_sample": {
                "risk_parity": {
                    "metrics": is_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in is_nav.items()
                    ],
                },
                "equal_weight": {
                    "metrics": is_eq_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in is_eq_nav.items()
                    ],
                },
                "benchmark": {
                    "metrics": is_idx_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in is_idx.items()
                    ],
                },
            },
            "out_of_sample": {
                "risk_parity": {
                    "metrics": oos_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in oos_nav.items()
                    ],
                },
                "equal_weight": {
                    "metrics": oos_eq_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in oos_eq_nav.items()
                    ],
                },
                "benchmark": {
                    "metrics": oos_idx_metrics,
                    "nav": [
                        {"date": str(i.date()), "nav": float(v)}
                        for i, v in oos_idx.items()
                    ],
                },
            },
            "weights": rp_weights_tab,
            "disclaimer": "Walk-forward: train on first 70%, test OOS on last 30%. Weights fixed from train, no refit. Not a return promise.",
        }
    )
