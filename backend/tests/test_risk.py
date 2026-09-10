"""Tests for risk engine: VaR/CVaR three methods, stress tests, risk report."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data.provider import MarketData, daily_returns
from app.engines.risk import (
    portfolio_returns,
    risk_report,
    stress_tests,
    var_cvar,
    var_cvar_montecarlo,
    var_cvar_parametric,
)


class TestVarCvarMethods:
    def test_historical_var_positive_and_cvar_geq_var(
        self, synthetic_returns: pd.DataFrame
    ):
        """Historical VaR should be positive (losses); CVaR >= VaR."""
        weights = pd.Series(
            1.0 / len(synthetic_returns.columns), index=synthetic_returns.columns
        )
        port = portfolio_returns(synthetic_returns, weights)

        result_95 = var_cvar(port, alpha=0.95)
        result_99 = var_cvar(port, alpha=0.99)

        assert result_95["n"] > 0
        assert result_95["var"] > 0, (
            f"VaR_95 should be positive, got {result_95['var']}"
        )
        assert result_95["cvar"] >= result_95["var"]

        # 99% VaR should be >= 95% VaR (deeper tail)
        assert result_99["var"] >= result_95["var"]

    def test_parametric_var_close_to_historical(self, synthetic_returns: pd.DataFrame):
        """Parametric VaR should be within 50% of historical VaR (same distribution family)."""
        weights = pd.Series(
            1.0 / len(synthetic_returns.columns), index=synthetic_returns.columns
        )
        port = portfolio_returns(synthetic_returns, weights)

        hist = var_cvar(port, alpha=0.95)
        para = var_cvar_parametric(port, alpha=0.95)

        assert para["n"] == hist["n"]
        assert para["var"] > 0

        # Parametric (normal assumption) should be reasonably close to historical
        ratio = para["var"] / hist["var"] if hist["var"] > 0 else 0
        assert 0.5 < ratio < 2.0, f"parametric/historical ratio={ratio:.3f} too far"

    def test_montecarlo_var_reproducible(self, synthetic_returns: pd.DataFrame):
        """Monte Carlo VaR is reproducible due to fixed RNG_SEED."""
        weights = pd.Series(
            1.0 / len(synthetic_returns.columns), index=synthetic_returns.columns
        )

        result1 = var_cvar_montecarlo(
            synthetic_returns, weights, alpha=0.95, n_sims=5000
        )
        result2 = var_cvar_montecarlo(
            synthetic_returns, weights, alpha=0.95, n_sims=5000
        )

        assert result1["n_sims"] == 5000
        assert result1["var"] > 0
        # Same seed -> identical results
        assert abs(result1["var"] - result2["var"]) < 1e-12


class TestRiskReport:
    def test_report_has_three_methods(self, synthetic_data: MarketData):
        """risk_report contains historical, parametric, montecarlo in methods_comparison."""
        returns = daily_returns(synthetic_data.close)
        weights = pd.Series(1.0 / len(returns.columns), index=returns.columns)
        report = risk_report(returns, weights, synthetic_data.close)

        assert "var_cvar" in report
        assert "methods_comparison" in report
        assert "stress" in report

        mc = report["methods_comparison"]
        assert "historical" in mc
        assert "parametric" in mc
        assert "montecarlo" in mc

        # Each method has d1_95 and d1_99
        for method_name, method_data in mc.items():
            assert "d1_95" in method_data
            assert "d1_99" in method_data
            assert method_data["d1_95"]["var"] > 0
            assert method_data["d1_99"]["var"] > 0

        # Stress tests should have at least 3 items
        assert len(report["stress"]) >= 3
