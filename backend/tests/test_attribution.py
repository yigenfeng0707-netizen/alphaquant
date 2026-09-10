"""Tests for attribution engine: single-period and multi-period Brinson-Fachler."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data.provider import MarketData
from app.engines.attribution import brinson_fachler, multi_period_brinson


class TestBrinsonFachler:
    def test_recon_error_near_zero(self, synthetic_data: MarketData):
        """Single-period Brinson reconciliation error should be near zero."""
        close = synthetic_data.close
        cols = list(close.columns)
        n = len(cols)

        # Portfolio: tilt toward first half
        wp = pd.Series(0.0, index=cols)
        wp.iloc[: n // 2] = 2.0 / n
        wp.iloc[n // 2 :] = 0.0
        # Benchmark: equal weight
        wb = pd.Series(1.0 / n, index=cols)

        result = brinson_fachler(close, wp, wb, universe=synthetic_data.universe)

        assert result["model"] == "Brinson-Fachler"
        assert abs(result["recon_error"]) < 1e-10, (
            f"recon_error={result['recon_error']}"
        )
        # Allocation + selection + interaction should reconstruct excess return
        total_effects = (
            result["allocation"] + result["selection"] + result["interaction"]
        )
        excess = result["portfolio_return"] - result["benchmark_return"]
        assert abs(total_effects - excess) < 1e-10

    def test_equal_weights_produce_zero_excess(self, synthetic_data: MarketData):
        """When portfolio weights equal benchmark (equal weight), excess return = 0."""
        close = synthetic_data.close
        cols = list(close.columns)
        wb = pd.Series(1.0 / len(cols), index=cols)

        result = brinson_fachler(close, wb, wb, universe=synthetic_data.universe)

        assert abs(result["excess_return"]) < 1e-12
        assert abs(result["allocation"]) < 1e-12
        assert abs(result["selection"]) < 1e-12
        assert abs(result["interaction"]) < 1e-12


class TestMultiPeriodBrinson:
    def test_returns_sub_periods_and_linked_effects(self, synthetic_data: MarketData):
        """Multi-period Brinson returns n sub-periods with Frongello-linked effects."""
        close = synthetic_data.close
        cols = list(close.columns)
        n = len(cols)

        # Portfolio: tilt toward financials
        wp = pd.Series(1.0 / n, index=cols)
        wp.loc[["600036", "601318", "000001"]] = 0.15
        wp = wp / wp.sum()
        wb = pd.Series(1.0 / n, index=cols)

        result = multi_period_brinson(
            close, wp, wb, universe=synthetic_data.universe, n_periods=4
        )

        assert result["model"] == "Brinson-Fachler (multi-period, Frongello linked)"
        assert result["period"]["n_sub_periods"] >= 1
        assert "linking_residual" in result
        assert "sub_periods" in result
        assert len(result["sub_periods"]) >= 1

        # Each sub-period should have the three effects
        for sp in result["sub_periods"]:
            assert "allocation" in sp
            assert "selection" in sp
            assert "interaction" in sp
            assert "portfolio_return" in sp
            assert "benchmark_return" in sp

        # Linked total should approximate excess return (within linking residual)
        linked_total = (
            result["allocation"] + result["selection"] + result["interaction"]
        )
        excess = result["excess_return"]
        residual = excess - linked_total
        assert abs(residual - result["linking_residual"]) < 1e-10
