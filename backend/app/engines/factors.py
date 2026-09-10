"""Cross-sectional factors, IC/IR, dynamic weights, decay flags."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.provider import MarketData, daily_returns
from app.utils import json_safe, zscore_cs

FACTOR_SPECS = [
    ("mom_20", "20日动量", "high"),
    ("mom_60", "60日动量", "high"),
    ("rev_5", "5日反转", "high"),
    ("low_vol_20", "20日低波动", "high"),
    ("ma_gap_20", "均线偏离", "high"),
    ("rsi_14", "RSI中性偏离", "high"),
    ("liq_logvol", "成交额流动性", "high"),
    ("turnover_proxy", "换手代理", "high"),
    ("size", "市值（小盘）", "high"),
    ("value_pe", "估值PE", "high"),
    ("value_pb", "估值PB", "high"),
    ("quality_roe", "盈利质量ROE", "high"),
]


def _rsi(close: pd.Series, window: int = 14) -> float:
    d = close.diff()
    gain = d.clip(lower=0).rolling(window).mean()
    loss = (-d.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    v = rsi.iloc[-1]
    return float(v) if pd.notna(v) else 50.0


def _snapshot_raw(data: MarketData) -> pd.DataFrame:
    close = data.close
    volume = data.volume.reindex_like(close).fillna(0.0)
    rets = daily_returns(close)
    uni = data.universe.set_index("code")
    rows = []
    for code in close.columns:
        px = close[code].dropna()
        if len(px) < 60:
            continue
        r = rets[code].dropna() if code in rets.columns else px.pct_change().dropna()
        vol20 = float(r.tail(20).std()) if len(r) >= 20 else np.nan
        logvol = float(np.log(max(volume[code].tail(20).mean(), 1.0)))
        mcap = float(uni.loc[code, "mcap"]) if code in uni.index and "mcap" in uni.columns else np.nan
        pe = float(uni.loc[code, "pe"]) if code in uni.index and "pe" in uni.columns else np.nan
        pb = float(uni.loc[code, "pb"]) if code in uni.index and "pb" in uni.columns else np.nan
        roe = float(uni.loc[code, "roe"]) if code in uni.index and "roe" in uni.columns else np.nan
        name = str(uni.loc[code, "name"]) if code in uni.index and "name" in uni.columns else code
        sector = str(uni.loc[code, "sector"]) if code in uni.index and "sector" in uni.columns else ""
        rows.append(
            {
                "code": str(code),
                "name": name,
                "sector": sector,
                "last_close": float(px.iloc[-1]),
                "mom_20": float(px.iloc[-1] / px.iloc[-21] - 1) if len(px) > 21 else np.nan,
                "mom_60": float(px.iloc[-1] / px.iloc[-61] - 1) if len(px) > 61 else np.nan,
                "rev_5": float(-(px.iloc[-1] / px.iloc[-6] - 1)) if len(px) > 6 else np.nan,
                "low_vol_20": float(-vol20) if pd.notna(vol20) else np.nan,
                "ma_gap_20": float(px.iloc[-1] / px.tail(20).mean() - 1),
                "rsi_14": -abs(_rsi(px) - 50.0),
                "liq_logvol": logvol,
                "turnover_proxy": float(np.log(max(volume[code].iloc[-1], 1.0)) - np.log(max(mcap / 1e8, 1.0))),
                "size": float(-np.log(max(mcap, 1.0))),
                "value_pe": float(-pe) if pd.notna(pe) else np.nan,
                "value_pb": float(-pb) if pd.notna(pb) else np.nan,
                "quality_roe": roe,
            }
        )
    return pd.DataFrame(rows)


def _factor_at(code: str, factor: str, hist: pd.Series, t, data: MarketData, uni: pd.DataFrame) -> float:
    vol = data.volume[code].loc[:t] if code in data.volume.columns else pd.Series(dtype=float)
    if factor == "mom_20":
        return float(hist.iloc[-1] / hist.iloc[-21] - 1) if len(hist) > 21 else np.nan
    if factor == "mom_60":
        return float(hist.iloc[-1] / hist.iloc[-61] - 1) if len(hist) > 61 else np.nan
    if factor == "rev_5":
        return float(-(hist.iloc[-1] / hist.iloc[-6] - 1)) if len(hist) > 6 else np.nan
    if factor == "low_vol_20":
        return float(-hist.pct_change().tail(20).std())
    if factor == "ma_gap_20":
        return float(hist.iloc[-1] / hist.tail(20).mean() - 1)
    if factor == "rsi_14":
        return -abs(_rsi(hist) - 50.0)
    if factor == "liq_logvol":
        return float(np.log(max(vol.tail(20).mean() if len(vol) else 1.0, 1.0)))
    if factor == "turnover_proxy":
        mcap = float(uni.loc[code, "mcap"]) if code in uni.index and "mcap" in uni.columns else 1.0
        last_v = float(vol.iloc[-1]) if len(vol) else 1.0
        return float(np.log(max(last_v, 1.0)) - np.log(max(mcap / 1e8, 1.0)))
    if factor == "size":
        mcap = float(uni.loc[code, "mcap"]) if code in uni.index and "mcap" in uni.columns else np.nan
        return float(-np.log(max(mcap, 1.0))) if pd.notna(mcap) else np.nan
    if factor == "value_pe":
        return -float(uni.loc[code, "pe"]) if code in uni.index and "pe" in uni.columns else np.nan
    if factor == "value_pb":
        return -float(uni.loc[code, "pb"]) if code in uni.index and "pb" in uni.columns else np.nan
    if factor == "quality_roe":
        return float(uni.loc[code, "roe"]) if code in uni.index and "roe" in uni.columns else np.nan
    return np.nan


def _ic_series(data: MarketData, factor: str, horizon: int = 20, step: int = 21) -> pd.Series:
    close = data.close
    uni = data.universe.set_index("code")
    dates = close.index
    ics = []
    idx = []
    start = 60
    while start + horizon < len(dates):
        t = dates[start]
        t2 = dates[start + horizon]
        xs = []
        ys = []
        for code in close.columns:
            px = close[code]
            if pd.isna(px.loc[t]) or pd.isna(px.loc[t2]):
                continue
            hist = px.loc[:t].dropna()
            if len(hist) < 60:
                continue
            x = _factor_at(str(code), factor, hist, t, data, uni)
            y = float(px.loc[t2] / px.loc[t] - 1)
            if pd.notna(x) and pd.notna(y):
                xs.append(float(x))
                ys.append(y)
        if len(xs) >= 6:
            ic = pd.Series(xs).corr(pd.Series(ys), method="spearman")
            if pd.notna(ic):
                ics.append(float(ic))
                idx.append(t)
        start += step
    return pd.Series(ics, index=pd.DatetimeIndex(idx), name=factor)


_DIAG_CACHE: dict[tuple, dict] = {}


def factor_diagnostics(data: MarketData) -> dict:
    key = (data.source, str(data.close.index[-1].date()), tuple(data.close.columns), int(data.close.shape[0]))
    hit = _DIAG_CACHE.get(key)
    if hit is not None:
        return hit
    names = [f[0] for f in FACTOR_SPECS]
    ic_map = {}
    ir_map = {}
    decay = []
    for fname, cname, _ in FACTOR_SPECS:
        s = _ic_series(data, fname)
        ic_map[fname] = {
            "label": cname,
            "mean_ic": float(s.mean()) if len(s) else 0.0,
            "ir": float(s.mean() / s.std(ddof=0)) if len(s) > 2 and s.std(ddof=0) > 1e-9 else 0.0,
            "n": int(len(s)),
        }
        ir_map[fname] = ic_map[fname]["ir"]
        if len(s) >= 8:
            recent = s.tail(3).mean()
            prior = s.iloc[:-3].mean()
            if recent < 0 and prior > 0.02:
                decay.append(
                    {
                        "factor": fname,
                        "label": cname,
                        "recent_ic": float(recent),
                        "prior_ic": float(prior),
                        "message": f"{cname} 近窗 IC 转负，疑似衰减",
                    }
                )
    raw_ir = np.array([max(ir_map[n], 0.0) for n in names], dtype=float)
    if raw_ir.sum() <= 1e-12:
        weights = {n: 1.0 / len(names) for n in names}
        weight_mode = "equal_fallback"
    else:
        w = raw_ir / raw_ir.sum()
        weights = {n: float(w[i]) for i, n in enumerate(names)}
        weight_mode = "ir_positive"
    result = {
        "ic": ic_map,
        "dynamic_weights": weights,
        "weight_mode": weight_mode,
        "decay_alerts": decay,
    }
    _DIAG_CACHE[key] = result
    return result


def screen_stocks(data: MarketData, top_n: int = 10) -> dict:
    raw = _snapshot_raw(data)
    diag = factor_diagnostics(data)
    weights = diag["dynamic_weights"]
    scored = raw.copy()
    parts = []
    for fname, _, _ in FACTOR_SPECS:
        z = zscore_cs(scored[fname])
        scored[f"z_{fname}"] = z
        parts.append(z * weights[fname])
    scored["composite"] = sum(parts)
    scored["rank"] = scored["composite"].rank(ascending=False).astype(int)
    scored = scored.sort_values("composite", ascending=False).reset_index(drop=True)
    picks = scored.head(top_n)
    return json_safe(
        {
            "asof": str(data.close.index[-1].date()),
            "factor_count": len(FACTOR_SPECS),
            "factors": [{"id": a, "label": b} for a, b, _ in FACTOR_SPECS],
            "diagnostics": diag,
            "picks": picks.to_dict(orient="records"),
            "universe_scored": scored.to_dict(orient="records"),
        }
    )
