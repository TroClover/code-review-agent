"""Unified LLM client supporting multiple providers.

Uses synchronous SDK calls in a thread pool to avoid async httpx connection issues.
The diagnostic script confirmed sync OpenAI client works reliably with DeepSeek.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Shared thread pool for all LLM calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


class LLMResponse(BaseModel):
    """Standardized LLM response."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        ...


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible API provider (works with OpenAI, DeepSeek, etc.)."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client: Any = None

    def _get_client(self):
        """Lazy-init a single reusable sync client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=120,
            )
        return self._client

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._get_client()
        logger.info(f"LLM call: model={model}, base_url={self.base_url}, messages={len(messages)}")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = self.estimate_cost(input_tokens, output_tokens, model)

        content = choice.message.content or ""
        logger.info(f"LLM response: {input_tokens} in / {output_tokens} out tokens")
        if not content:
            logger.warning(f"LLM response content is empty! finish_reason={choice.finish_reason}")

        return LLMResponse(
            content=content,
            model=model,
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = {
            "gpt-4": (0.03, 0.06),
            "gpt-4-turbo": (0.01, 0.03),
            "gpt-4o": (0.005, 0.015),
            "gpt-4o-mini": (0.00015, 0.0006),
            "deepseek-chat": (0.00014, 0.00028),
            "deepseek-v4-flash": (0.00014, 0.00028),
            "deepseek-v4-pro": (0.0005, 0.0018),
            "deepseek-reasoner": (0.0005, 0.0018),
        }
        input_rate, output_rate = pricing.get(model, (0.01, 0.03))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1000


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        client = self._get_client()

        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append(msg)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=anthropic_messages,
        )

        content = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self.estimate_cost(input_tokens, output_tokens, model)

        return LLMResponse(
            content=content,
            model=model,
            provider="anthropic",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = {
            "claude-3-opus-20240229": (0.015, 0.075),
            "claude-3-sonnet-20240229": (0.003, 0.015),
            "claude-3-haiku-20240307": (0.00025, 0.00125),
        }
        input_rate, output_rate = pricing.get(model, (0.003, 0.015))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1000


class LLMClient:
    """Unified LLM client.

    All calls run synchronously in a shared thread pool,
    allowing multiple agents to call the LLM concurrently
    without async httpx issues.
    """

    def __init__(self, provider: BaseLLMProvider, max_cost_per_review: float = 1.0):
        self.provider = provider
        self.max_cost_per_review = max_cost_per_review
        self._total_cost = 0.0
        self._total_tokens = 0

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> LLMResponse:
        """Complete a chat. Runs sync provider in thread pool with retries."""
        if self._total_cost >= self.max_cost_per_review:
            raise RuntimeError(
                f"Cost limit reached: ${self._total_cost:.4f} >= ${self.max_cost_per_review:.4f}"
            )

        last_error = None
        for attempt in range(retries):
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    lambda: self.provider.complete_sync(messages, model, temperature, max_tokens),
                )
                self._total_cost += response.cost_usd
                self._total_tokens += response.total_tokens
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise last_error  # type: ignore

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


def create_llm_client(config: Any) -> LLMClient:
    """Create an LLM client from configuration."""
    llm_config = config.llm if hasattr(config, "llm") else config

    provider_name = getattr(llm_config, "provider", "openai")
    api_key = getattr(llm_config, "api_key", None)
    base_url = getattr(llm_config, "base_url", None)
    model = getattr(llm_config, "model", "deepseek-v4-flash")

    if not api_key or "set via" in str(api_key):
        import os
        api_key = os.environ.get("BREVIEW_LLM_API_KEY")
        if not api_key:
            if provider_name == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY")
            else:
                api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(f"No API key configured for {provider_name}. Set it in config or environment.")

    logger.info(f"Creating LLM client: provider={provider_name}, model={model}, base_url={base_url}")

    if provider_name == "anthropic":
        provider = AnthropicProvider(api_key=api_key)
    else:
        provider = OpenAIProvider(api_key=api_key, base_url=base_url)

    return LLMClient(
        provider=provider,
        max_cost_per_review=getattr(llm_config, "max_cost_per_review", 1.0),
    )
