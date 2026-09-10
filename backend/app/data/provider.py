"""Market data: AKShare with timeout, then offline synthetic demo panel."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from app.config import (
    AKSHARE_FUND_SEC,
    AKSHARE_OVERALL_SEC,
    AKSHARE_TIMEOUT_SEC,
    OFFLINE_DIR,
)

logger = logging.getLogger("alphaquant.data")

SourceMode = Literal["auto", "offline"]

LIVE_UNIVERSE = [
    ("600036", "招商银行", "金融"),
    ("601318", "中国平安", "金融"),
    ("600519", "贵州茅台", "消费"),
    ("000858", "五粮液", "消费"),
    ("000333", "美的集团", "制造"),
    ("600276", "恒瑞医药", "医药"),
    ("601012", "隆基绿能", "制造"),
    ("002475", "立讯精密", "制造"),
    ("300750", "宁德时代", "制造"),
    ("601899", "紫金矿业", "能源"),
    ("600900", "长江电力", "能源"),
    ("000001", "平安银行", "金融"),
]


@dataclass
class MarketData:
    close: pd.DataFrame
    volume: pd.DataFrame
    universe: pd.DataFrame
    source: str
    disclaimer: str
    note: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def codes(self) -> list[str]:
        return [str(c) for c in self.close.columns]


def _offline_disclaimer() -> str:
    return "当前为离线合成演示样本，不是交易所实盘行情，也不是真实持仓。"


def _akshare_disclaimer() -> str:
    return "当前为 AKShare 公开历史行情演示，延迟与缺测以数据源为准，不是实盘交易。"


def load_offline() -> MarketData:
    prices = pd.read_csv(OFFLINE_DIR / "prices.csv", parse_dates=["date"])
    universe = pd.read_csv(OFFLINE_DIR / "universe.csv")
    meta_path = OFFLINE_DIR / "meta.json"
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    )
    close = prices.pivot(index="date", columns="code", values="close").sort_index()
    volume = prices.pivot(index="date", columns="code", values="volume").sort_index()
    close.columns = [str(c) for c in close.columns]
    volume.columns = [str(c) for c in volume.columns]
    logger.info(
        "data_source=offline_synthetic_demo rows=%s names=%s",
        len(close),
        close.shape[1],
    )
    return MarketData(
        close=close,
        volume=volume.reindex(columns=close.columns),
        universe=universe,
        source="offline_synthetic_demo",
        disclaimer=_offline_disclaimer(),
        note=str(meta.get("note", "")),
        meta=meta,
    )


def _fetch_one_ak(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    import akshare as ak

    kwargs = dict(
        symbol=symbol,
        period="daily",
        start_date=start,
        end_date=end,
        adjust="qfq",
    )
    try:
        df = ak.stock_zh_a_hist(timeout=AKSHARE_TIMEOUT_SEC, **kwargs)
    except TypeError:
        df = ak.stock_zh_a_hist(**kwargs)
    if df is None or df.empty:
        return None
    col_map = {"日期": "date", "收盘": "close", "成交量": "volume"}
    df = df.rename(columns=col_map)
    if "date" not in df.columns or "close" not in df.columns:
        return None
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"]),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df.get("volume", 0), errors="coerce"),
        }
    )
    out["code"] = symbol
    return out.dropna(subset=["close"])


def _fetch_fundamentals_ak(code: str) -> tuple[float, float, float]:
    """Fetch PE / PB / ROE for a single stock from AKShare.

    Returns (pe, pb, roe) where roe is in decimal (e.g. 0.12 = 12%).
    On any failure returns (nan, nan, nan).
    """
    import akshare as ak

    pe = pb = roe = float("nan")

    # --- PE (TTM) ---
    try:
        df_pe = ak.stock_zh_valuation_baidu(
            symbol=code,
            indicator="\u5e02\u76c8\u7387(TTM)",
            period="\u8fd1\u4e00\u5e74",
        )
        if df_pe is not None and len(df_pe) > 0:
            v = df_pe.iloc[-1]["value"]
            if pd.notna(v) and float(v) > 0:
                pe = float(v)
    except Exception as exc:
        logger.debug("akshare PE fetch %s failed: %s", code, exc)

    # --- PB ---
    try:
        df_pb = ak.stock_zh_valuation_baidu(
            symbol=code, indicator="\u5e02\u51c0\u7387", period="\u8fd1\u4e00\u5e74"
        )
        if df_pb is not None and len(df_pb) > 0:
            v = df_pb.iloc[-1]["value"]
            if pd.notna(v) and float(v) > 0:
                pb = float(v)
    except Exception as exc:
        logger.debug("akshare PB fetch %s failed: %s", code, exc)

    # --- ROE (from financial abstract) ---
    try:
        df_fin = ak.stock_financial_abstract(symbol=code)
        if df_fin is not None and len(df_fin) > 0:
            # Find row containing ROE
            mask = (
                df_fin["\u6307\u6807"]
                .astype(str)
                .str.contains("\u51c0\u8d44\u4ea7\u6536\u76ca\u7387", na=False)
            )
            if mask.any():
                row = df_fin.loc[mask].iloc[0]
                # Scan date columns left-to-right for the first non-NaN
                date_cols = [
                    c
                    for c in df_fin.columns
                    if c not in ("\u9009\u9879", "\u6307\u6807")
                ]
                for dc in date_cols:
                    v = row[dc]
                    if pd.notna(v) and float(v) != 0:
                        roe = float(v) / 100.0  # percentage -> decimal
                        break
    except Exception as exc:
        logger.debug("akshare ROE fetch %s failed: %s", code, exc)

    return pe, pb, roe


def try_akshare() -> MarketData | None:
    t0 = time.time()
    frames: list[pd.DataFrame] = []
    names = []
    try:
        import akshare as ak  # noqa: F401
    except Exception as exc:
        logger.warning("akshare import failed: %s", exc)
        return None

    end = pd.Timestamp.today().strftime("%Y%m%d")
    start = (pd.Timestamp.today() - pd.Timedelta(days=800)).strftime("%Y%m%d")
    for code, name, sector in LIVE_UNIVERSE:
        if time.time() - t0 > AKSHARE_OVERALL_SEC:
            logger.warning("akshare overall timeout, abort live fetch")
            return None
        try:
            part = _fetch_one_ak(code, start, end)
        except Exception as exc:
            logger.warning("akshare fetch %s failed: %s", code, exc)
            part = None
        if part is None or len(part) < 120:
            continue
        frames.append(part)
        names.append({"code": code, "name": name, "sector": sector})
    if len(frames) < 6:
        logger.warning("akshare insufficient names=%s", len(frames))
        return None
    prices = pd.concat(frames, ignore_index=True)
    close = prices.pivot(index="date", columns="code", values="close").sort_index()
    volume = prices.pivot(index="date", columns="code", values="volume").sort_index()
    close = close.dropna(how="any")
    if len(close) < 120:
        return None
    volume = volume.reindex(index=close.index, columns=close.columns)
    universe = pd.DataFrame(names)
    last = close.iloc[-1]
    universe["pe"] = np.nan
    universe["pb"] = np.nan
    universe["roe"] = np.nan
    universe["mcap"] = last.reindex(universe["code"]).to_numpy() * 1e9

    # --- Fetch fundamentals (PE / PB / ROE) with separate timeout budget ---
    fund_t0 = time.time()
    fund_ok = 0
    for i, row in universe.iterrows():
        if time.time() - fund_t0 > AKSHARE_FUND_SEC:
            logger.warning(
                "akshare fundamentals timeout at %s (%d/%d done)",
                row["code"],
                fund_ok,
                len(universe),
            )
            break
        try:
            pe, pb, roe = _fetch_fundamentals_ak(str(row["code"]))
        except Exception as exc:
            logger.warning("akshare fundamentals %s failed: %s", row["code"], exc)
            pe = pb = roe = float("nan")
        if pd.notna(pe):
            universe.loc[i, "pe"] = pe
        if pd.notna(pb):
            universe.loc[i, "pb"] = pb
        if pd.notna(roe):
            universe.loc[i, "roe"] = roe
        if pd.notna(pe) and pd.notna(pb) and pd.notna(roe):
            fund_ok += 1
    logger.info(
        "akshare fundamentals: %d/%d stocks have full PE+PB+ROE", fund_ok, len(universe)
    )
    logger.info("data_source=akshare rows=%s names=%s", len(close), close.shape[1])
    return MarketData(
        close=close,
        volume=volume,
        universe=universe,
        source="akshare",
        disclaimer=_akshare_disclaimer(),
        note="公开前复权日线，仅供演示。",
        meta={"fetched_at": pd.Timestamp.now().isoformat(timespec="seconds")},
    )


_CACHE: dict[str, tuple[float, MarketData]] = {}
_CACHE_TTL = 300.0


def get_market(source: SourceMode = "offline") -> MarketData:
    key = source
    hit = _CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    if source == "offline":
        data = load_offline()
    else:
        live = try_akshare()
        data = live if live is not None else load_offline()
        if live is None:
            logger.info("akshare unavailable, fallback offline_synthetic_demo")
    _CACHE[key] = (now, data)
    return data


def daily_returns(close: pd.DataFrame) -> pd.DataFrame:
    return close.pct_change().dropna(how="all")
