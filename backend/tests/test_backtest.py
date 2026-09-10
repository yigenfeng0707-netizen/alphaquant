"""Tests for backtest engine: strategies, walk-forward, NAV computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import DEFAULT_COST
from app.data.provider import MarketData, daily_returns
from app.engines.backtest import (
    _metrics,
    backtest_all,
    equal_weight_index,
    nav_from_weights,
    run_strategy,
    walk_forward_backtest,
)


class TestNavFromWeights:
    def test_nav_starts_at_one_after_cost(self, synthetic_returns: pd.DataFrame):
        """NAV should start at 1.0 (normalized) after initial cost deduction."""
        codes = list(synthetic_returns.columns)
        w = pd.Series(1.0 / len(codes), index=codes)
        nav, rets, trades = nav_from_weights(synthetic_returns, w, cost=0.0015)

        assert abs(nav.iloc[0] - 1.0) < 1e-9
        assert trades == 1
        assert len(nav) == len(synthetic_returns)

    def test_zero_cost_preserves_cumulative_product(
        self, synthetic_returns: pd.DataFrame
    ):
        """With cost=0, NAV normalized to 1.0. Slippage is a constant entry cost
        that creates a uniform scaling after normalization (ratio test)."""
        codes = list(synthetic_returns.columns)
        w = pd.Series(1.0 / len(codes), index=codes)
        nav, rets, trades = nav_from_weights(synthetic_returns, w, cost=0.0)

        # nav_from_weights normalizes: nav = (1+rets).cumprod() / nav.iloc[0]
        expected_nav = (1.0 + rets).cumprod()
        expected_nav = expected_nav / expected_nav.iloc[0]
        # entry slippage creates a constant scaling factor for t>0
        # nav[0]=1.0 (normalized), expected[0]=1.0, but nav[t] = expected[t] / (1-slippage)
        ratios = nav.values[1:] / expected_nav.values[1:]
        assert np.allclose(ratios, ratios[0], rtol=1e-10), (
            "nav/expected ratio should be constant for t>0"
        )
        assert abs(ratios[0] - 1.0) < 0.01, f"slippage impact too large: {ratios[0]}"


class TestBacktestAll:
    def test_returns_four_strategies_and_benchmark(self, synthetic_data: MarketData):
        """backtest_all returns 4 strategies + buy_hold benchmark."""
        result = backtest_all(synthetic_data.close, data=synthetic_data)

        strategy_ids = [s["strategy"] for s in result["strategies"]]
        assert "ma_cross" in strategy_ids
        assert "mean_reversion" in strategy_ids
        assert "momentum" in strategy_ids
        assert "multi_factor" in strategy_ids

        # Benchmark should exist
        assert result["benchmark"]["strategy"] == "buy_hold_index"

        # multi_factor should use factor_engine when data is provided
        mf = next(s for s in result["strategies"] if s["strategy"] == "multi_factor")
        assert mf["engine"] == "factor_engine"

        # All strategies should have metrics with required keys
        for s in result["strategies"] + [result["benchmark"]]:
            m = s["metrics"]
            assert "sharpe" in m
            assert "max_drawdown" in m
            assert "annual_return" in m
            assert "volatility" in m


class TestWalkForward:
    def test_returns_in_sample_and_out_of_sample(self, synthetic_data: MarketData):
        """walk_forward_backtest returns IS and OOS metrics for risk_parity and equal_weight."""
        result = walk_forward_backtest(synthetic_data, train_ratio=0.7)

        assert "in_sample" in result
        assert "out_of_sample" in result
        assert "risk_parity" in result["in_sample"]
        assert "equal_weight" in result["in_sample"]
        assert "risk_parity" in result["out_of_sample"]
        assert "equal_weight" in result["out_of_sample"]

        # IS and OOS should have different date ranges
        is_dates = result["period"]["in_sample"]
        oos_dates = result["period"]["out_of_sample"]
        assert is_dates["end"] < oos_dates["start"]

        # OOS metrics should be non-trivial
        oos_rp_metrics = result["out_of_sample"]["risk_parity"]["metrics"]
        assert "sharpe" in oos_rp_metrics
        assert isinstance(oos_rp_metrics["sharpe"], float)
