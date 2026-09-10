"""Tests for suitability engine: scoring, profile matching, portfolio blocking."""

from __future__ import annotations

import pytest

from app.engines.suitability import (
    PRESETS,
    PROFILE_RULES,
    PROFILES,
    match_portfolio,
    score_answers,
)


class TestScoreAnswers:
    def test_preset_profiles_match_expected_score_range(self):
        """Each preset should score into its corresponding profile."""
        for profile_id, answers in PRESETS.items():
            result = score_answers(answers)
            assert result["profile_id"] == profile_id, (
                f"preset {profile_id} scored as {result['profile_id']} "
                f"(score={result['score']})"
            )
            # Score should be in the profile's range
            for pid, label, lo, hi in PROFILES:
                if pid == profile_id:
                    assert lo <= result["score"] <= hi

    def test_all_ones_is_conservative_all_fives_is_aggressive(self):
        """Minimum answers (all 1) -> conservative; maximum (all 5) -> aggressive."""
        min_answers = {f"q{i}": 1 for i in range(1, 9)}
        max_answers = {f"q{i}": 5 for i in range(1, 9)}

        min_result = score_answers(min_answers)
        max_result = score_answers(max_answers)

        assert min_result["profile_id"] == "conservative"
        assert min_result["score"] == 8  # 8 questions * 1
        assert max_result["profile_id"] == "aggressive"
        assert max_result["score"] == 40  # 8 questions * 5

    def test_invalid_score_raises(self):
        """Score value outside 1-5 should raise ValueError."""
        bad_answers = {f"q{i}": 3 for i in range(1, 9)}
        bad_answers["q1"] = 0
        with pytest.raises(ValueError):
            score_answers(bad_answers)

        bad_answers["q1"] = 6
        with pytest.raises(ValueError):
            score_answers(bad_answers)


class TestMatchPortfolio:
    def test_conservative_blocks_max_sharpe(self):
        """Conservative profile should block max_sharpe (not in allowed_methods)."""
        metrics = {"volatility": 0.10, "max_drawdown": -0.05}
        weights = [{"code": "A", "weight": 0.1}, {"code": "B", "weight": 0.1}]
        result = match_portfolio(
            "conservative", "max_sharpe", metrics, weights, equity_weight=1.0
        )

        assert result["decision"] == "拦截"
        assert result["blocked"] is True
        assert result["ok"] is False
        assert result["suggested_method"] == "min_variance"

    def test_balanced_passes_risk_parity(self):
        """Balanced profile with low vol/dd should pass risk_parity."""
        metrics = {"volatility": 0.12, "max_drawdown": -0.08}
        weights = [{"code": "A", "weight": 0.1}] * 10
        result = match_portfolio(
            "balanced", "risk_parity", metrics, weights, equity_weight=1.0
        )

        assert result["decision"] == "通过"
        assert result["ok"] is True
        assert result["blocked"] is False
        assert result["method"] == "risk_parity"

    def test_volatility_exceeding_limit_blocks(self):
        """Volatility exceeding profile limit should block."""
        # Steady profile: max_ann_vol = 0.22
        metrics = {"volatility": 0.30, "max_drawdown": -0.10}
        weights = [{"code": "A", "weight": 0.1}] * 10
        result = match_portfolio(
            "steady", "risk_parity", metrics, weights, equity_weight=1.0
        )

        assert result["decision"] == "拦截"
        assert any("波动" in r for r in result["reasons"])
