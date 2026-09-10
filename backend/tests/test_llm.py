"""Tests for LLM client and LLM service endpoints.

All tests use mocks -- no real API calls are made.
Tests cover: scope guard, fallback degradation, endpoint responses.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.llm_client import (
    _FALLBACK_SUMMARY,
    _check_scope,
    llm_status,
    qiji_image,
    qiji_text,
    sensenova_image,
    sensenova_text,
    sensenova_vision,
    step_text,
    step_vision,
    step_voice,
)


# ---------------------------------------------------------------------------
# 1. SCOPE guard tests
# ---------------------------------------------------------------------------


class TestScopeGuard:
    """SCOPE.md red line: LLM must not generate trading strategies."""

    def test_blocks_strategy_generation(self):
        with pytest.raises(ValueError, match="SCOPE ALERT"):
            _check_scope("Please generate a trading strategy for AAPL")

    def test_blocks_signal_prediction(self):
        with pytest.raises(ValueError, match="SCOPE ALERT"):
            _check_scope("Predict buy signals for tomorrow")

    def test_allows_report_summary(self):
        # Should not raise -- summarizing is a non-strategy use
        _check_scope("Summarize this risk report with VaR metrics")

    def test_allows_faq_assistance(self):
        _check_scope("What is risk parity optimization?")

    def test_allows_voice_intro(self):
        _check_scope("AlphaQuant is a factor-based asset allocation demo platform")


# ---------------------------------------------------------------------------
# 2. Fallback degradation tests (no API keys)
# ---------------------------------------------------------------------------


class TestFallbackDegradation:
    """When API keys are missing, functions return fallback text gracefully."""

    def test_step_text_fallback(self):
        with patch("app.llm_client.STEP_API_KEY", ""):
            result = step_text("Summarize this risk report")
            assert "AlphaQuant" in result
            assert "回退" in result or "fallback" in result.lower()

    def test_sensenova_text_fallback(self):
        with patch("app.llm_client.SENSENOVA_API_KEY", ""):
            result = sensenova_text("Summarize this risk report")
            assert "AlphaQuant" in result

    def test_sensenova_image_fallback(self):
        with patch("app.llm_client.SENSENOVA_IMAGE_API_KEY", ""):
            result = sensenova_image("a financial chart")
            assert result.get("fallback") is True

    def test_step_vision_fallback(self):
        with patch("app.llm_client.STEP_API_KEY", ""):
            result = step_vision("dGVzdA==", prompt="describe chart")
            assert "not configured" in result.lower() or "missing" in result.lower()

    def test_sensenova_vision_fallback(self):
        with patch("app.llm_client.SENSENOVA_API_KEY", ""):
            result = sensenova_vision("dGVzdA==", prompt="describe chart")
            assert "not configured" in result.lower() or "missing" in result.lower()

    def test_step_voice_raises_without_key(self):
        with patch("app.llm_client.STEP_API_KEY", ""):
            with pytest.raises(RuntimeError, match="STEP_API_KEY not configured"):
                step_voice("test text")

    def test_qiji_text_fallback(self):
        with patch("app.llm_client.QIJI_API_KEY", ""):
            result = qiji_text("Summarize this risk report")
            assert "AlphaQuant" in result
            assert "回退" in result or "fallback" in result.lower()

    def test_qiji_image_fallback(self):
        with patch("app.llm_client.QIJI_IMAGE_API_KEY", ""):
            result = qiji_image("a financial chart")
            assert result.get("fallback") is True


# ---------------------------------------------------------------------------
# 3. Mocked API call tests (simulate real API responses)
# ---------------------------------------------------------------------------


class TestMockedApiCalls:
    """Mock httpx.Client to simulate real API responses."""

    def test_step_text_mocked(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Mocked LLM summary"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.llm_client.STEP_API_KEY", "fake-key-12345"):
            with patch(
                "app.llm_client._chat_completions",
                return_value=mock_response.json.return_value,
            ):
                result = step_text("Summarize this risk report")
                assert result == "Mocked LLM summary"

    def test_sensenova_text_mocked(self):
        mock_response = {"choices": [{"message": {"content": "SenseNova summary"}}]}

        with patch("app.llm_client.SENSENOVA_API_KEY", "fake-key"):
            with patch("app.llm_client._chat_completions", return_value=mock_response):
                result = sensenova_text("Summarize report")
                assert result == "SenseNova summary"

    def test_step_voice_mocked(self):
        fake_audio = b"fake mp3 audio bytes"

        with patch("app.llm_client.STEP_API_KEY", "fake-key"):
            with patch("app.llm_client._audio_speech", return_value=fake_audio):
                result = step_voice("project intro text")
                assert result == fake_audio

    def test_sensenova_image_mocked(self):
        mock_image_response = {"data": [{"url": "https://example.com/image.png"}]}

        with patch("app.llm_client.SENSENOVA_IMAGE_API_KEY", "fake-key"):
            with patch(
                "app.llm_client._images_generate", return_value=mock_image_response
            ):
                result = sensenova_image("financial dashboard")
                assert "data" in result
                assert len(result["data"]) == 1

    def test_step_text_api_error_fallback(self):
        with patch("app.llm_client.STEP_API_KEY", "fake-key"):
            with patch(
                "app.llm_client._chat_completions", side_effect=Exception("API timeout")
            ):
                with patch("app.llm_client.STEP_MODEL_FALLBACK1", "fallback-model"):
                    result = step_text("Summarize report")
                    # Both primary and fallback fail -> returns fallback text
                    assert "AlphaQuant" in result

    def test_sensenova_vision_mocked(self):
        mock_response = {
            "choices": [{"message": {"content": "Chart shows VaR metrics"}}]
        }

        with patch("app.llm_client.SENSENOVA_API_KEY", "fake-key"):
            with patch("app.llm_client._chat_completions", return_value=mock_response):
                result = sensenova_vision("iVBORw0KGgo=", prompt="Describe this chart")
                assert result == "Chart shows VaR metrics"

    def test_qiji_text_mocked(self):
        mock_response = {"choices": [{"message": {"content": "Qiji LLM summary"}}]}

        with patch("app.llm_client.QIJI_API_KEY", "fake-key"):
            with patch("app.llm_client._chat_completions", return_value=mock_response):
                result = qiji_text("Summarize report")
                assert result == "Qiji LLM summary"

    def test_qiji_image_mocked(self):
        mock_image_response = {"data": [{"url": "https://example.com/qiji.png"}]}

        with patch("app.llm_client.QIJI_IMAGE_API_KEY", "fake-key"):
            with patch(
                "app.llm_client._images_generate", return_value=mock_image_response
            ):
                result = qiji_image("financial dashboard")
                assert "data" in result
                assert len(result["data"]) == 1

    def test_qiji_text_api_error_fallback(self):
        with patch("app.llm_client.QIJI_API_KEY", "fake-key"):
            with patch(
                "app.llm_client._chat_completions", side_effect=Exception("API timeout")
            ):
                result = qiji_text("Summarize report")
                assert "AlphaQuant" in result


# ---------------------------------------------------------------------------
# 4. llm_status tests
# ---------------------------------------------------------------------------


class TestLlmStatus:
    """Status endpoint returns config without secrets."""

    def test_status_structure(self):
        with patch("app.llm_client.STEP_API_KEY", "fake"):
            with patch("app.llm_client.SENSENOVA_API_KEY", "fake"):
                with patch("app.llm_client.SENSENOVA_IMAGE_API_KEY", "fake"):
                    with patch("app.llm_client.QIJI_API_KEY", "fake"):
                        with patch("app.llm_client.QIJI_IMAGE_API_KEY", "fake"):
                            status = llm_status()
                            assert "enabled" in status
                            assert "providers" in status
                            assert "stepfun" in status["providers"]
                            assert "sensenova_text" in status["providers"]
                            assert "sensenova_image" in status["providers"]
                            assert (
                                "capabilities" in status["providers"]["sensenova_image"]
                            )
                            assert "qiji_text" in status["providers"]
                            assert "qiji_image" in status["providers"]
                            assert "billing" in status["providers"]["qiji_text"]
                            assert "billing" in status["providers"]["qiji_image"]
                            assert "scope_guard" in status
                            assert "timeout_sec" in status

    def test_status_no_secrets(self):
        with patch("app.llm_client.STEP_API_KEY", "secret-key-12345"):
            status = llm_status()
            status_str = json.dumps(status)
            assert "secret-key-12345" not in status_str
            assert "sk-" not in status_str


# ---------------------------------------------------------------------------
# 5. API endpoint integration tests (via TestClient)
# ---------------------------------------------------------------------------


class TestLlmEndpoints:
    """Test LLM API endpoints with TestClient (no real API calls)."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app

        return TestClient(app)

    def test_status_endpoint(self, client):
        r = client.get("/api/llm/status")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "enabled" in data["data"]

    def test_summary_endpoint_fallback(self, client):
        with patch("app.llm_client.STEP_API_KEY", ""):
            r = client.get("/api/llm/summary?source=offline")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert "summary" in data["data"]
            assert "scope_note" in data["data"]

    def test_summary_endpoint_mocked(self, client):
        with patch("app.llm_client.STEP_API_KEY", "fake-key"):
            with patch(
                "app.llm_client._chat_completions",
                return_value={
                    "choices": [
                        {"message": {"content": "Mocked summary from endpoint"}}
                    ]
                },
            ):
                r = client.get("/api/llm/summary?source=offline&provider=stepfun")
                assert r.status_code == 200
                data = r.json()
                assert "Mocked summary" in data["data"]["summary"]

    def test_voice_endpoint_text_fallback(self, client):
        r = client.post(
            "/api/llm/voice", json={"text": "intro", "provider": "sensenova"}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "text" in data["data"]

    def test_illustration_endpoint_fallback(self, client):
        with patch("app.llm_client.SENSENOVA_IMAGE_API_KEY", ""):
            r = client.post("/api/llm/illustration", json={"prompt": "chart"})
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True

    def test_vision_endpoint_fallback(self, client):
        with patch("app.llm_client.STEP_API_KEY", ""):
            r = client.post(
                "/api/llm/vision", json={"image_b64": "dGVzdA==", "prompt": "test"}
            )
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert "description" in data["data"]

    def test_summary_invalid_provider_defaults(self, client):
        r = client.get("/api/llm/summary?source=offline&provider=invalid_provider")
        assert r.status_code == 200

    def test_summary_qiji_fallback(self, client):
        with patch("app.llm_client.QIJI_API_KEY", ""):
            r = client.get("/api/llm/summary?source=offline&provider=qiji")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert "summary" in data["data"]
            assert data["data"]["provider"] == "qiji"

    def test_illustration_qiji_fallback(self, client):
        with patch("app.llm_client.QIJI_IMAGE_API_KEY", ""):
            r = client.post(
                "/api/llm/illustration",
                json={"prompt": "chart", "provider": "qiji_image"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert data["provider"] == "qiji_image"

    def test_illustration_invalid_provider_defaults(self, client):
        with patch("app.llm_client.SENSENOVA_IMAGE_API_KEY", ""):
            r = client.post(
                "/api/llm/illustration",
                json={"prompt": "chart", "provider": "invalid"},
            )
            assert r.status_code == 200
            assert r.json()["provider"] == "sensenova_image"
