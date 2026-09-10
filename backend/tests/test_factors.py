"""Tests for factor engine: IC diagnostics, stock screening, composite scores."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.engines.factors import (
    FACTOR_SPECS,
    factor_diagnostics,
    screen_stocks,
)
from app.data.provider import MarketData


class TestFactorDiagnostics:
    def test_ic_map_has_all_12_factors(self, synthetic_data: MarketData):
        """factor_diagnostics returns IC stats for every FACTOR_SPEC entry."""
        diag = factor_diagnostics(synthetic_data)
        ic_map = diag["ic"]

        assert len(ic_map) == len(FACTOR_SPECS)
        for fname, label, _ in FACTOR_SPECS:
            assert fname in ic_map, f"factor {fname} missing from ic map"
            entry = ic_map[fname]
            assert "mean_ic" in entry
            assert "ir" in entry
            assert "n" in entry
            assert entry["label"] == label
            assert isinstance(entry["n"], int)
            assert entry["n"] >= 0

    def test_dynamic_weights_sum_to_one(self, synthetic_data: MarketData):
        """Dynamic weights derived from IR should sum to ~1.0."""
        diag = factor_diagnostics(synthetic_data)
        weights = diag["dynamic_weights"]

        assert len(weights) == len(FACTOR_SPECS)
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"weights sum={total}, expected 1.0"
        # All weights non-negative
        for fname, w in weights.items():
            assert w >= 0.0, f"negative weight for {fname}: {w}"
        # Weight mode should be one of known modes
        assert diag["weight_mode"] in ("ir_positive", "equal_fallback")


class TestScreenStocks:
    def test_picks_have_composite_and_rank(self, synthetic_data: MarketData):
        """screen_stocks returns top_n picks with composite scores and ranks."""
        result = screen_stocks(synthetic_data, top_n=5)

        assert result["factor_count"] == len(FACTOR_SPECS)
        picks = result["picks"]
        assert len(picks) == 5

        # Picks should be sorted by composite descending
        composites = [p["composite"] for p in picks]
        assert composites == sorted(composites, reverse=True)

        # Each pick should have essential fields
        for p in picks:
            assert "code" in p
            assert "name" in p
            assert "sector" in p
            assert "composite" in p
            assert "rank" in p

    def test_universe_scored_contains_all_stocks(self, synthetic_data: MarketData):
        """universe_scored should contain all stocks that had enough data."""
        result = screen_stocks(synthetic_data, top_n=3)
        scored = result["universe_scored"]

        # With 150 days and 60-day minimum, all 12 stocks should be scored
        assert len(scored) == 12

        # Ranks should be 1..12 (unique)
        ranks = sorted([s["rank"] for s in scored])
        assert ranks == list(range(1, 13))
