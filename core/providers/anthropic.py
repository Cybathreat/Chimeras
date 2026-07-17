"""
Chimeras v1.0 — Anthropic Provider

Claude Opus, Sonnet, and Haiku models via Anthropic API.
Supports custom base_url for Anthropic-compatible proxies and gateways.
"""

from typing import Optional, AsyncIterator
import asyncio

from core.llm_router import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider.

    Supports both official Anthropic and any Anthropic-compatible proxy
    via base_url.
    """

    def __init__(self, model: str = "claude-opus-4-6-20250929", api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = AsyncAnthropic(**kwargs)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    async def stream(self, prompt: str, system: Optional[str] = None,
                     max_tokens: int = 4096, **kwargs) -> AsyncIterator[str]:
        """Stream Claude response token by token."""
        client = self._get_client()

        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a cybersecurity assistant.",
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def generate(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 4096, **kwargs) -> str:
        """Generate complete Claude response."""
        client = self._get_client()

        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a cybersecurity assistant.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text