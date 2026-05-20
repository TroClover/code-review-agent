"""Tests for the LLM client (with mocked API calls)."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from breview.llm.client import (
    LLMClient,
    LLMResponse,
    OpenAIProvider,
    AnthropicProvider,
    create_llm_client,
)
from breview.config.schema import BreviewConfig, LLMConfig


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_create_response(self):
        resp = LLMResponse(
            content="Hello",
            model="gpt-4",
            provider="openai",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=0.001,
        )
        assert resp.content == "Hello"
        assert resp.total_tokens == 15


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_estimate_cost(self):
        provider = OpenAIProvider(api_key="test", base_url=None)
        cost = provider.estimate_cost(1000, 500, "gpt-4")
        assert cost > 0

    def test_estimate_cost_deepseek(self):
        provider = OpenAIProvider(api_key="test", base_url=None)
        cost = provider.estimate_cost(1000, 500, "deepseek-v4-flash")
        assert cost > 0

    def test_estimate_cost_unknown_model(self):
        provider = OpenAIProvider(api_key="test", base_url=None)
        cost = provider.estimate_cost(1000, 500, "unknown-model")
        assert cost > 0  # Falls back to default pricing


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    def test_estimate_cost(self):
        provider = AnthropicProvider(api_key="test")
        cost = provider.estimate_cost(1000, 500, "claude-3-sonnet-20240229")
        assert cost > 0


class TestLLMClient:
    """Tests for the unified LLM client."""

    @pytest.mark.asyncio
    async def test_cost_limit(self):
        mock_provider = MagicMock()
        mock_provider.complete_sync.return_value = LLMResponse(
            content="ok", model="m", provider="p",
            input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=0.5,
        )
        client = LLMClient(provider=mock_provider, max_cost_per_review=0.3)

        # First call succeeds but cost accumulates to 0.5 > 0.3
        await client.complete(
            messages=[{"role": "user", "content": "test"}],
            model="m",
            retries=1,
        )
        assert client.total_cost == pytest.approx(0.5)

        # Second call should be blocked
        with pytest.raises(RuntimeError, match="Cost limit"):
            await client.complete(
                messages=[{"role": "user", "content": "test"}],
                model="m",
                retries=1,
            )

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        mock_provider = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return LLMResponse(
                content="ok", model="m", provider="p",
                input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=0.0,
            )

        mock_provider.complete_sync = side_effect
        client = LLMClient(provider=mock_provider, max_cost_per_review=1.0)

        response = await client.complete(
            messages=[{"role": "user", "content": "test"}],
            model="m",
            retries=3,
        )
        assert response.content == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        mock_provider = MagicMock()
        mock_provider.complete_sync.side_effect = ConnectionError("Always fail")
        client = LLMClient(provider=mock_provider, max_cost_per_review=1.0)

        with pytest.raises(ConnectionError):
            await client.complete(
                messages=[{"role": "user", "content": "test"}],
                model="m",
                retries=2,
            )

    @pytest.mark.asyncio
    async def test_tracks_cost(self):
        mock_provider = MagicMock()
        mock_provider.complete_sync.return_value = LLMResponse(
            content="ok", model="m", provider="p",
            input_tokens=100, output_tokens=50, total_tokens=150, cost_usd=0.01,
        )
        client = LLMClient(provider=mock_provider, max_cost_per_review=10.0)

        await client.complete(
            messages=[{"role": "user", "content": "test"}],
            model="m",
            retries=1,
        )
        assert client.total_cost == pytest.approx(0.01)
        assert client.total_tokens == 150


class TestCreateLLMClient:
    """Tests for the client factory function."""

    def test_create_with_config_key(self):
        config = BreviewConfig(llm=LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-test-key",
            base_url="https://api.example.com",
        ))
        client = create_llm_client(config)
        assert isinstance(client, LLMClient)
        assert isinstance(client.provider, OpenAIProvider)
        assert client.provider.api_key == "sk-test-key"
        assert client.provider.base_url == "https://api.example.com"

    def test_create_with_env_key(self, monkeypatch):
        monkeypatch.setenv("BREVIEW_LLM_API_KEY", "env-key-123")
        config = BreviewConfig(llm=LLMConfig(provider="openai", model="gpt-4"))
        client = create_llm_client(config)
        assert client.provider.api_key == "env-key-123"

    def test_create_no_key_raises(self, monkeypatch):
        monkeypatch.delenv("BREVIEW_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = BreviewConfig(llm=LLMConfig(provider="openai", model="gpt-4"))
        with pytest.raises(ValueError, match="No API key"):
            create_llm_client(config)

    def test_create_anthropic(self):
        config = BreviewConfig(llm=LLMConfig(
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="sk-ant-test",
        ))
        client = create_llm_client(config)
        assert isinstance(client.provider, AnthropicProvider)
