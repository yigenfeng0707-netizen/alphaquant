"""Shared fixtures: synthetic MarketData for all engine tests.

No network, no file I/O -- deterministic and fast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import RNG_SEED
from app.data.provider import MarketData, daily_returns

# -- universe definition (mirrors LIVE_UNIVERSE) -----------------------------------

_CODES = [
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

N_DAYS = 150  # enough for 60-day lookback + 20-day forward IC + walk-forward


def _make_panel(
    n_days: int = N_DAYS, seed: int = RNG_SEED
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic close, volume, universe DataFrames."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2025-01-02", periods=n_days)
    cols = [c[0] for c in _CODES]

    # Random walk prices starting from sector-typical levels
    base_prices = {
        "600036": 35.0,
        "601318": 45.0,
        "600519": 1600.0,
        "000858": 140.0,
        "000333": 60.0,
        "600276": 40.0,
        "601012": 20.0,
        "002475": 32.0,
        "300750": 180.0,
        "601899": 12.0,
        "600900": 25.0,
        "000001": 11.0,
    }
    # Different drift/vol per stock to create factor differentiation
    drifts = rng.normal(0.0002, 0.0003, len(cols))
    vols = rng.uniform(0.012, 0.025, len(cols))

    close_data = {}
    vol_data = {}
    for i, code in enumerate(cols):
        rets = rng.normal(drifts[i], vols[i], n_days)
        px = base_prices[code] * np.cumprod(1 + rets)
        close_data[code] = px
        vol_data[code] = rng.integers(5_000_000, 50_000_000, n_days).astype(float)

    close = pd.DataFrame(close_data, index=dates)
    volume = pd.DataFrame(vol_data, index=dates)

    # Universe metadata
    uni_rows = []
    for code, name, sector in _CODES:
        uni_rows.append(
            {
                "code": code,
                "name": name,
                "sector": sector,
                "mcap": float(
                    np.random.default_rng(seed + hash(code) % 1000).uniform(5e10, 3e12)
                ),
                "pe": float(
                    np.random.default_rng(seed + hash(code) % 999).uniform(5.0, 40.0)
                ),
                "pb": float(
                    np.random.default_rng(seed + hash(code) % 998).uniform(0.5, 8.0)
                ),
                "roe": float(
                    np.random.default_rng(seed + hash(code) % 997).uniform(0.03, 0.25)
                ),
            }
        )
    universe = pd.DataFrame(uni_rows)

    return close, volume, universe


@pytest.fixture(scope="session")
def synthetic_data() -> MarketData:
    """Session-scoped synthetic MarketData for all tests."""
    close, volume, universe = _make_panel()
    return MarketData(
        close=close,
        volume=volume,
        universe=universe,
        source="test_synthetic",
        disclaimer="synthetic test data",
    )


@pytest.fixture(scope="session")
def synthetic_returns(synthetic_data: MarketData) -> pd.DataFrame:
    """Daily returns DataFrame aligned with close."""
    return daily_returns(synthetic_data.close)
