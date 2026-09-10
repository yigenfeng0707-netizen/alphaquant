"""Tests for optimizer: weight constraints, sector neutral, risk parity balance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data.provider import MarketData, daily_returns
from app.engines.optimizer import (
    METHODS,
    SECTOR_LIMIT,
    optimize_basket,
    risk_contributions,
)


class TestOptimizeBasket:
    def test_all_methods_weights_sum_to_one(self, synthetic_returns: pd.DataFrame):
        """All four optimization methods produce weights that sum to 1.0."""
        result = optimize_basket(synthetic_returns, names={})

        for method in METHODS:
            assert method in result["methods"]
            weights = result["methods"][method]["weights"]
            total = sum(w["weight"] for w in weights)
            assert abs(total - 1.0) < 1e-6, f"{method} weights sum={total}"

            # All weights non-negative
            for w in weights:
                assert w["weight"] >= -1e-9, (
                    f"{method} has negative weight: {w['weight']}"
                )

    def test_risk_contributions_are_positive(self, synthetic_returns: pd.DataFrame):
        """Risk contributions should be non-negative and sum to ~1.0."""
        result = optimize_basket(synthetic_returns, names={})
        rp_bundle = result["methods"]["risk_parity"]
        rc_values = [w["risk_contrib"] for w in rp_bundle["weights"]]

        for rc in rc_values:
            assert rc >= -1e-9, f"negative risk contribution: {rc}"
        total_rc = sum(rc_values)
        assert abs(total_rc - 1.0) < 1e-6, f"risk contributions sum={total_rc}"


class TestSectorNeutral:
    def test_sector_deviation_within_limit(self, synthetic_data: MarketData):
        """With sector_neutral=True, each sector's deviation from benchmark <= SECTOR_LIMIT."""
        returns = daily_returns(synthetic_data.close)
        result = optimize_basket(
            returns,
            names={},
            universe=synthetic_data.universe,
            sector_neutral=True,
        )

        assert result["sector_neutral"] is True
        assert "sector_note" in result

        for method in METHODS:
            bundle = result["methods"][method]
            if "sector_exposure" not in bundle:
                continue
            for row in bundle["sector_exposure"]:
                assert row["within_limit"] is True, (
                    f"{method} sector '{row['sector']}' deviation "
                    f"{row['deviation']:.4f} exceeds {SECTOR_LIMIT}"
                )
                assert abs(row["deviation"]) <= SECTOR_LIMIT + 1e-6
